<?php

namespace App\Http\Controllers\Checkout;

use App\Http\Controllers\Controller;
use App\Models\Business;
use App\Models\DtfOrder;
use App\Models\PaymentInfo;
use App\Models\PaymentMethod;
use App\Models\Setting;
use App\Models\ShippingAddress;
use App\Services\ShippoService;
use App\Services\QboService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Cache;
use Stripe\Stripe;
use Stripe\PaymentIntent;

class CheckoutController extends Controller
{
    protected $shippo;
    protected $qbo;

    public function __construct(ShippoService $shippo, QboService $qbo)
    {
        $this->shippo = $shippo;
        $this->qbo = $qbo;
    }

    public function index()
    {
        Log::debug('Checkout index requested');
        try {
            $user = Auth::user();
            $business = $user->business;

            if (!$business) {
                Log::warning('Checkout unavailable: no business found for authenticated user', [
                    'user_id' => $user->id ?? null,
                ]);
                return redirect()->route('home')->with('error', 'No business found or not logged in.');
            }

            $order = $business->dtfOrders()->where('status', 1)->first();
            if (!$order) {
                Log::warning('Checkout unavailable: no open order found', [
                    'business_id' => $business->id,
                ]);
                return redirect()->route('home')->with('error', 'No open order found.');
            }
        } catch (\Exception $e) {
            Log::error('Checkout database load failed', [
                'exception_type' => $e::class,
                'exception_code' => $e->getCode(),
            ]);
            return redirect()->route('home')->with('error', 'Database connection error. Please try again later.');
        }

        try {
            // Auto-populate shipping address from business if not exists
            if (!$order->shippingAddress) {
                ShippingAddress::create([
                    'order_id' => $order->id,
                    'name'     => $business->contact_name ?: $business->business_name,
                    'address1' => $business->address,
                    'address2' => $business->address2,
                    'city'     => $business->city,
                    'state'    => $business->state,
                    'zip'      => $business->zip,
                ]);
                $order->load('shippingAddress');
            }

            // Determine available payment methods
            $paymentMethods = $business->paymentMethods;
            if ($paymentMethods->isEmpty()) {
                $paymentMethods = PaymentMethod::all();
            }

            // Set default payment method: Priority is QB Invoices (invoice)
            $invoiceMethod = $paymentMethods->where('payment_controller', 'invoice')->first();
            $cardMethod = $paymentMethods->where('payment_controller', 'cardpayment')->first();

            if ($invoiceMethod && (!$order->payment_method_id || ($cardMethod && $order->payment_method_id == $cardMethod->id))) {
                // If invoice is available, and (no method set OR it was set to card), set it to invoice
                $order->update(['payment_method_id' => $invoiceMethod->id]);
                $order->load('paymentMethod');
            } elseif (!$order->payment_method_id && $cardMethod) {
                // Otherwise if nothing set and card is available, use card
                $order->update(['payment_method_id' => $cardMethod->id]);
                $order->load('paymentMethod');
            } elseif (!$order->payment_method_id && $paymentMethods->isNotEmpty()) {
                // Fallback to first available if still nothing set
                $order->update(['payment_method_id' => $paymentMethods->first()->id]);
                $order->load('paymentMethod');
            }

            // Recalculate order total (without shipping/tax yet)
            $orderPrice = $order->get_total();
            $order->update(['price' => $orderPrice]);

            // Get shipping rates if address is available
            $shippingAddress = $order->shippingAddress;
            $rates = [];
            $freeShippingThreshold = (float)Setting::get('free_shipping_threshold', 500);

            $weight = $order->calculate_weight();
            // Fallback to a minimum weight if calculation returns 0 or false, but images exist
            if (($weight === false || $weight <= 0) && $order->dtfImages->isNotEmpty()) {
                $weight = 1.8; // Default minimum weight in lbs (core weight)
                Log::warning('Checkout order weight was unavailable; using fallback weight', [
                    'order_id' => $order->id,
                    'fallback_weight_lbs' => $weight,
                ]);
            }

            Log::debug('Checkout shipping inputs evaluated', [
                'order_id' => $order->id,
                'weight_lbs' => $weight === false ? null : $weight,
                'shipping_address_present' => $shippingAddress !== null,
            ]);

            if ($shippingAddress && $weight !== false && $weight > 0) {
                try {
                    $toAddr = [
                        'name' => $shippingAddress->name,
                        'street1' => $shippingAddress->address1,
                        'street2' => $shippingAddress->address2,
                        'city' => $shippingAddress->city,
                        'state' => $shippingAddress->state,
                        'zip' => $shippingAddress->zip,
                    ];
                    $weightOz = $weight * 16; // lbs to oz
                    Log::debug('Checkout requesting shipping rates', [
                        'order_id' => $order->id,
                        'weight_oz' => $weightOz,
                    ]);
                    $quote = $this->shippo->quoteUpsRates($toAddr, $weightOz);
                    $rates = $quote['rates'];
                    Log::debug('Checkout shipping rates received', [
                        'order_id' => $order->id,
                        'rate_count' => count($rates),
                    ]);

                    // Free shipping logic
                    $freeShippingServices = json_decode(Setting::get('free_shipping_services', '["ups_ground", "ups_ground_saver"]'), true);
                    if ($orderPrice >= $freeShippingThreshold) {
                        foreach ($rates as &$rate) {
                            $token = strtolower((string)($rate['servicelevel']['token'] ?? $rate['service_token'] ?? ''));
                            if (in_array($token, $freeShippingServices)) {
                                $rate['amount'] = 0;
                                $rate['is_free'] = true;
                            }
                        }
                    }
                } catch (\Exception $e) {
                    Log::warning('Checkout shipping quote unavailable', [
                        'order_id' => $order->id,
                        'exception_type' => $e::class,
                        'exception_code' => $e->getCode(),
                    ]);
                }
            } else {
                Log::debug('Checkout shipping quote skipped', [
                    'order_id' => $order->id,
                    'shipping_address_present' => $shippingAddress !== null,
                    'weight_valid' => $weight !== false && $weight > 0,
                ]);
            }

            $pickupEnabled = Setting::get('shipping_pickup_enabled', '0');
            Log::debug('Checkout pickup setting evaluated', [
                'pickup_enabled' => $pickupEnabled == '1' || $pickupEnabled === true || $pickupEnabled == 'true',
            ]);
            // Add Pickup option if enabled as the first option
            // Even if Shippo fails, we want to show this if it is enabled.
            if ($pickupEnabled == '1' || $pickupEnabled === true || $pickupEnabled == 'true') {
                Log::debug('Checkout pickup option added');
                array_unshift($rates, [
                    'object_id' => 'pickup',
                    'provider' => 'Local',
                    'servicelevel' => ['name' => Setting::get('shipping_pickup_message', 'Local Pick-up')],
                    'amount' => 0,
                    'currency' => 'USD',
                    'duration_terms' => 'Available for local pickup',
                ]);
            }
            Log::debug('Checkout shipping options finalized', [
                'rate_count' => count($rates),
            ]);

            $estimatedSalesTaxRate = (bool)($business->tax_exempt ?? false)
                ? 0.0
                : $this->getSalesTaxRate($shippingAddress?->state ?? $business->state);

            return view('checkout.index', compact('order', 'business', 'rates', 'paymentMethods', 'estimatedSalesTaxRate'));
        } catch (\Exception $e) {
            Log::error('Checkout: Error during data processing: ' . $e->getMessage() . "\n" . $e->getTraceAsString());
            return redirect()->route('home')->with('error', 'An error occurred during checkout processing. Please try again.');
        }
    }

    public function updateShippingAddress(Request $request)
    {
        $user = Auth::user();
        $business = $user->business;
        $order = $business->dtfOrders()->where('status', 1)->firstOrFail();

        $validated = $request->validate([
            'name' => 'required|string|max:255',
            'address1' => 'required|string|max:255',
            'address2' => 'nullable|string|max:255',
            'city' => 'required|string|max:255',
            'state' => 'required|string|max:2',
            'zip' => 'required|string|max:10',
        ]);

        $shippingAddress = $order->shippingAddress;
        if ($shippingAddress) {
            $shippingAddress->update($validated);
        } else {
            $validated['order_id'] = $order->id;
            ShippingAddress::create($validated);
        }

        return response()->json(['success' => true]);
    }

    public function startPayment(Request $request)
    {
        Log::debug('Checkout payment initialization requested', [
            'user_id' => Auth::id(),
            'payment_method_id' => $request->input('payment_method_id'),
            'shipping_rate_selected' => $request->filled('shipping_rate_id'),
        ]);

        try {
            $user = Auth::user();
            $business = $user->business;
            $order = $business->dtfOrders()->where('status', 1)->firstOrFail();

            $fuelDb = env('FUEL_DB_CONNECTION', 'fuelmysql');
            // Validation for shipping method selection
            $request->validate([
                'shipping_rate_id' => 'required',
                'shipping_cost' => 'required|numeric',
                'payment_method_id' => "required|exists:{$fuelDb}.paymentmethods,id",
            ]);

            $paymentMethod = PaymentMethod::findOrFail($request->payment_method_id);

            $updateData = [
                'shipping_cost' => $request->shipping_cost,
                'payment_method_id' => $paymentMethod->id,
                'shipping_method_id' => is_numeric($request->shipping_rate_id) ? $request->shipping_rate_id : null,
                'shipping_method' => $request->shipping_service_name,
                'shippo_service_name' => $request->shipping_service_name,
            ];

            $columns = \Illuminate\Support\Facades\Schema::connection($fuelDb)->getColumnListing('dtforders');
            // 'shipping_method' and 'shippo_service_name' are already in updateData,
            // but we can keep the column checks for robustness if needed,
            // although they are now explicitly set.

            $order->update($updateData);

            $orderPrice = $order->get_total();
            $salesTax = $this->calculateSalesTax($order, $business, $orderPrice);
            $totalPrice = $orderPrice + $order->shipping_cost + $salesTax;
            $order->update(['price' => $orderPrice, 'total_price' => $totalPrice, 'sales_tax' => $salesTax]);

            // If it's an invoice, we redirect to the disclaimer page
            if ($paymentMethod->payment_controller === 'invoice') {
                return response()->json([
                    'requires_redirect' => true,
                    'redirect_url' => route('checkout.invoice.disclaimer', ['order' => $order->id]),
                ]);
            }

            // Stripe setup
            Stripe::setApiKey(config('services.stripe.secret'));

            $amountInCents = (int)round($totalPrice * 100);

            if ($amountInCents <= 0) {
                $order->finalizeMetrics();
                $order->update(['status' => 2]); // Status 2 = Paid/Processing
                return response()->json([
                    'requires_redirect' => true,
                    'redirect_url' => route('checkout.complete', ['pi' => 'free_order_' . $order->id]),
                ]);
            }

            $paymentIntent = PaymentIntent::create([
                'amount' => $amountInCents,
                'currency' => 'usd',
                'metadata' => [
                    'order_id' => $order->id,
                    'business_id' => $business->id,
                ],
            ]);

            return response()->json([
                'client_secret' => $paymentIntent->client_secret,
                'stripe_publishable_key' => config('services.stripe.key'),
            ]);

        } catch (\Illuminate\Validation\ValidationException $e) {
            return response()->json(['error' => 'Validation failed', 'messages' => $e->errors()], 422);
        } catch (\Exception $e) {
            Log::error('Checkout Payment Error: ' . $e->getMessage() . "\n" . $e->getTraceAsString());
            return response()->json(['error' => 'An error occurred during payment initialization: ' . $e->getMessage()], 500);
        }
    }

    public function invoiceDisclaimer(DtfOrder $order)
    {
        $user = Auth::user();
        $business = $user->business;

        // Security check
        if ($order->business_id !== $business->id) {
            abort(403);
        }

        if ($order->status != 1) {
            return redirect()->route('checkout.complete', ['pi' => 'invoice_' . $order->id]);
        }

        $order->load(['orderStatus', 'shippingAddress', 'paymentMethod', 'dtfImages']);

        return view('checkout.invoice_disclaimer', compact('order', 'business'));
    }

    private function calculateSalesTax(DtfOrder $order, Business $business, ?float $taxableAmount = null): float
    {
        if ((bool)($business->tax_exempt ?? false)) {
            return 0.0;
        }

        $state = $order->shippingAddress?->state ?: $business->state;
        $rate = $this->getSalesTaxRate($state);
        if ($rate <= 0) {
            return 0.0;
        }

        return round(($taxableAmount ?? (float)$order->price) * $rate, 2);
    }

    private function getSalesTaxRate(?string $state): float
    {
        $state = strtoupper(trim((string)$state));
        if ($state === '') {
            return 0.0;
        }

        $fuelDb = config('database.fuel_connection', env('FUEL_DB_CONNECTION', 'fuelmysql'));
        if ($fuelDb === 'remotefuel') {
            $fuelDb = 'fuelmysql';
        }

        $rate = \Illuminate\Support\Facades\DB::connection($fuelDb)
            ->table('states')
            ->where('code', $state)
            ->value('sales_tax');

        if ($rate === null) {
            return 0.0;
        }

        $rate = (float)$rate;

        return $rate > 1 ? $rate / 100 : $rate;
    }

    public function completeInvoiceOrder(DtfOrder $order)
    {
        $user = Auth::user();
        $business = $user->business;

        // Security check
        if ($order->business_id !== $business->id) {
            abort(403);
        }

        if ($order->status == 1) {
            try {
                // Check if auto-invoice is enabled for non-Stripe orders
                $autoInvoice = \App\Models\Setting::get('qbo_auto_invoice_on_checkout', '1') == '1';

                if ($autoInvoice) {
                    Log::info('DEBUG: Finalizing Invoice Order ' . $order->id . ' - Creating QBO Invoice');
                    $this->qbo->createInvoice($business, $order);
                    Log::info('DEBUG: QBO Invoice created for ' . $order->id);
                } else {
                    Log::info('DEBUG: Finalizing Invoice Order ' . $order->id . ' - Auto-invoice disabled, skipping QBO creation');
                }

                $order->finalizeMetrics();
                $order->update(['status' => 2]); // Status 2 = Paid/Processing
            } catch (\Exception $e) {
                // We log the error but still complete the order locally if the user insisted?
                // Actually, the user says "all that need to be done is to move the order status to 2"
                // But we should try QBO first.
                Log::error('QBO Invoice Error for Order ' . $order->id . ' (Finalize): ' . $e->getMessage());

                // Still mark as status 2 as requested by user even if QBO fails
                $order->finalizeMetrics();
                $order->update(['status' => 2]);
            }
        }

        return redirect()->route('checkout.complete', ['pi' => 'invoice_' . $order->id]);
    }

    public function complete(Request $request)
    {
        $paymentIntentId = $request->query('pi');
        if (!$paymentIntentId) {
            return redirect()->route('cart.index')->with('error', 'Payment failed or was cancelled.');
        }
        if (str_starts_with($paymentIntentId, 'free_order_')) {
            $order = DtfOrder::findOrFail(substr($paymentIntentId, strlen('free_order_')));
            if ($order->status == 1) {
                $order->update(['status' => 2]);
            }
            $order->load(['orderStatus', 'shippingAddress', 'paymentMethod', 'business']);
            return view('checkout.complete', compact('order'));
        }
        if (str_starts_with($paymentIntentId, 'invoice_')) {
            $order = DtfOrder::findOrFail(substr($paymentIntentId, strlen('invoice_')));
            if (!PaymentInfo::where('dtforder_id', $order->id)->where('processor', 'QB Invoice')->exists()) {
                PaymentInfo::create([
                    'dtforder_id' => $order->id,
                    'processor' => 'QB Invoice',
                    'processor_confirm' => 'Invoice',
                    'amount' => $order->total_price,
                    'notes' => 'Invoiced through QuickBooks. Awaiting payment.',
                    'status' => 'invoiced',
                ]);
            }
            $order->load(['orderStatus', 'shippingAddress', 'paymentMethod', 'business']);
            return view('checkout.complete', compact('order'));
        }

        Stripe::setApiKey(config('services.stripe.secret'));
        try {
            $paymentIntent = PaymentIntent::retrieve([
                'id' => $paymentIntentId,
                'expand' => ['latest_charge.balance_transaction'],
            ]);
            if ($paymentIntent->status !== 'succeeded' || !isset($paymentIntent->metadata->order_id)) {
                return redirect()->route('cart.index')->with('error', 'Payment has not succeeded or has no order.');
            }
            $order = DtfOrder::findOrFail($paymentIntent->metadata->order_id);
            app(\App\Services\StripePaymentCompletionService::class)->completeOrder($paymentIntent, $order);
            $order->refresh()->load(['orderStatus', 'shippingAddress', 'paymentMethod', 'business']);
            return view('checkout.complete', compact('order'));
        } catch (\Throwable $e) {
            Log::error('Stripe order completion failed', ['pi' => $paymentIntentId, 'error' => $e->getMessage()]);
            return redirect()->route('cart.index')->with('error', 'Payment could not be verified. Please contact support.');
        }
    }

    public function payQboInvoices(Request $request)
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business || !$business->qbo_customer_id) {
            return back()->with('error', 'No QuickBooks account linked.');
        }

        $invoiceIds = explode(',', $request->invoice_ids);
        if (empty($invoiceIds)) {
            return back()->with('error', 'No invoices selected.');
        }

        try {
            $invoices = $this->qbo->getUnpaidInvoices($business->qbo_customer_id);
            $total = 0;
            $selectedInvoices = [];
            $selectedDocNumbers = [];
            $selectedInvoiceAmounts = [];

            foreach ($invoices as $inv) {
                if (in_array($inv['Id'], $invoiceIds)) {
                    $payableBalance = $inv['PayableBalance'] ?? $this->qbo->getInvoicePayableBalance($inv);
                    $total += $payableBalance;
                    $selectedInvoices[] = $inv['Id'];
                    $selectedDocNumbers[] = $inv['DocNumber'] ?? $inv['Id'];
                    $selectedInvoiceAmounts[$inv['Id']] = number_format($payableBalance, 2, '.', '');
                }
            }

            if ($total <= 0) {
                return back()->with('error', 'Selected invoices have no remaining balance.');
            }

            Stripe::setApiKey(config('services.stripe.secret'));

            $paymentIntent = PaymentIntent::create([
                'amount' => round($total * 100),
                'currency' => 'usd',
                'metadata' => [
                    'qbo_customer_id' => $business->qbo_customer_id,
                    'business_id' => $business->id,
                    'qbo_invoice_ids' => implode(',', $selectedInvoices),
                    'qbo_invoice_numbers' => implode(',', $selectedDocNumbers),
                    'qbo_invoice_amounts' => http_build_query($selectedInvoiceAmounts, '', '&'),
                    'payment_type' => 'qbo_invoice_payment'
                ],
            ]);

            return view('checkout.qbo_payment', [
                'client_secret' => $paymentIntent->client_secret,
                'stripe_publishable_key' => config('services.stripe.key'),
                'total' => $total,
                'invoices' => $selectedInvoices
            ]);

        } catch (\Exception $e) {
            Log::error('QBO Payment Error: ' . $e->getMessage());
            return back()->with('error', 'Failed to initialize payment: ' . $e->getMessage());
        }
    }

    public function completeQboPayment(Request $request)
    {
        $paymentIntentId = $request->query('payment_intent');
        if (!$paymentIntentId) {
            return redirect()->route('account')->with('error', 'Payment failed or was cancelled.');
        }
        Stripe::setApiKey(config('services.stripe.secret'));
        try {
            $paymentIntent = PaymentIntent::retrieve([
                'id' => $paymentIntentId,
                'expand' => ['latest_charge.balance_transaction'],
            ]);
            if ($paymentIntent->status !== 'succeeded') {
                return redirect()->route('account')->with('error', 'Payment has not succeeded.');
            }
            $complete = app(\App\Services\StripePaymentCompletionService::class)->completeQboInvoices($paymentIntent);
            return redirect()->route('account')->with(
                $complete ? 'success' : 'warning',
                $complete
                    ? 'Payment successful! Your QuickBooks invoices have been updated.'
                    : 'Stripe payment received. QuickBooks posting is in progress or needs review; do not pay again.'
            );
        } catch (\Throwable $e) {
            Log::error('QBO payment completion failed', ['pi' => $paymentIntentId, 'error' => $e->getMessage()]);
            return redirect()->route('account')->with('error', 'Payment could not be verified. Please contact support before paying again.');
        }
    }
}
