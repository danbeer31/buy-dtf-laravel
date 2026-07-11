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
        Log::error('DEBUG: Entering CheckoutController::index');
        try {
            $user = Auth::user();
            $business = $user->business;

            if (!$business) {
                Log::error('DEBUG: Checkout: No business found for user ' . ($user->id ?? 'unknown'));
                return redirect()->route('home')->with('error', 'No business found or not logged in.');
            }

            $order = $business->dtfOrders()->where('status', 1)->first();
            if (!$order) {
                Log::error('DEBUG: Checkout: No open order found for business ' . $business->id);
                return redirect()->route('home')->with('error', 'No open order found.');
            }
        } catch (\Exception $e) {
            Log::error('DEBUG: Checkout: Database error during initial load: ' . $e->getMessage());
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
                Log::error('DEBUG: Order ' . $order->id . ' weight calculation failed or was 0, falling back to ' . $weight . ' lbs');
            }

            Log::error('DEBUG: Checkout index for order ' . $order->id . ': Weight=' . ($weight === false ? 'false' : $weight) . ', Address=' . ($shippingAddress ? 'Set' : 'Missing'));

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
                    Log::error('DEBUG: Quoting rates for order ' . $order->id . ' with weight ' . $weightOz . 'oz to ' . $shippingAddress->zip);
                    $quote = $this->shippo->quoteUpsRates($toAddr, $weightOz);
                    $rates = $quote['rates'];
                    Log::error('DEBUG: Found ' . count($rates) . ' UPS rates');

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
                    Log::error('DEBUG: Shippo error: ' . $e->getMessage());
                }
            } else {
                Log::error('DEBUG: Skipping Shippo rates for order ' . $order->id . ': ' .
                    (!$shippingAddress ? 'Missing Address. ' : '') .
                    ($weight === false ? 'Weight is false. ' : '') .
                    ($weight <= 0 ? 'Weight is <= 0. ' : ''));
            }

            $pickupEnabled = Setting::get('shipping_pickup_enabled', '0');
            Log::error('DEBUG: Checkout pickup setting raw: ' . var_export($pickupEnabled, true));
            // Add Pickup option if enabled as the first option
            // Even if Shippo fails, we want to show this if it is enabled.
            if ($pickupEnabled == '1' || $pickupEnabled === true || $pickupEnabled == 'true') {
                Log::error('DEBUG: Adding pickup option to rates');
                array_unshift($rates, [
                    'object_id' => 'pickup',
                    'provider' => 'Local',
                    'servicelevel' => ['name' => Setting::get('shipping_pickup_message', 'Local Pick-up')],
                    'amount' => 0,
                    'currency' => 'USD',
                    'duration_terms' => 'Available for local pickup',
                ]);
            }
            Log::error('DEBUG: Final rates count: ' . count($rates));

            return view('checkout.index', compact('order', 'business', 'rates', 'paymentMethods'));
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
        Log::info('DEBUG: startPayment initiated', [
            'user_id' => Auth::id(),
            'payload' => $request->all()
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

            // Recalculate total with shipping
            // Sales tax calculation placeholder (needs porting Helpers_Salestax)
            $salesTax = 0; // TODO: Implement sales tax
            $totalPrice = $order->price + $order->shipping_cost + $salesTax;
            $order->update(['total_price' => $totalPrice, 'sales_tax' => $salesTax]);

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
        Log::info('DEBUG: Entering CheckoutController::complete', ['pi' => $paymentIntentId]);

        if (!$paymentIntentId) {
            Log::warning('DEBUG: Checkout complete reached without pi parameter');
            return redirect()->route('cart.index')->with('error', 'Payment failed or was cancelled.');
        }

        if (str_starts_with($paymentIntentId, 'free_order_')) {
            $orderId = str_replace('free_order_', '', $paymentIntentId);
            $order = DtfOrder::findOrFail($orderId);

            if ($order->status == 1) {
                $order->update(['status' => 2]);
            }

            $order->load(['orderStatus', 'shippingAddress', 'paymentMethod', 'business']);

            return view('checkout.complete', compact('order'));
        }

        if (str_starts_with($paymentIntentId, 'invoice_')) {
            $orderId = str_replace('invoice_', '', $paymentIntentId);
            $order = DtfOrder::findOrFail($orderId);

            // Invoice order status is updated in completeInvoiceOrder
            $order->load(['orderStatus', 'shippingAddress', 'paymentMethod', 'business']);

            // Create a PaymentInfo record for "QB Invoice" type so it is tracked
            // but distinct from Stripe Transactions
            if (!PaymentInfo::where('dtforder_id', $order->id)->where('processor', 'QB Invoice')->exists()) {
                PaymentInfo::create([
                    'dtforder_id' => $order->id,
                    'processor' => 'QB Invoice',
                    'processor_confirm' => 'Invoice',
                    'amount' => $order->total_price,
                    'notes' => 'Invoiced through QuickBooks. Awaiting payment.',
                    'status' => 'pending',
                ]);
                Log::info("DEBUG: Created PaymentInfo for QB Invoice Order", ['order_id' => $order->id]);
            }

            return view('checkout.complete', compact('order'));
        }

        Stripe::setApiKey(config('services.stripe.secret'));
        try {
            $paymentIntent = PaymentIntent::retrieve([
                'id' => $paymentIntentId,
                'expand' => ['latest_charge.balance_transaction']
            ]);
            Log::info('DEBUG: Stripe PaymentIntent retrieved', ['status' => $paymentIntent->status, 'id' => $paymentIntent->id, 'metadata' => $paymentIntent->metadata]);

            // Re-attempt expansion if latest_charge is a string
            if (is_string($paymentIntent->latest_charge)) {
                $paymentIntent = PaymentIntent::retrieve([
                    'id' => $paymentIntentId,
                    'expand' => ['latest_charge.balance_transaction']
                ]);
            }
        } catch (\Exception $e) {
            Log::error('DEBUG: Stripe PaymentIntent retrieval failed', ['error' => $e->getMessage(), 'pi' => $paymentIntentId]);
            return redirect()->route('cart.index')->with('error', 'Invalid Payment or Stripe connection error.');
        }

        if ($paymentIntent->status !== 'succeeded') {
            Log::warning('DEBUG: Stripe PaymentIntent status not succeeded', ['status' => $paymentIntent->status, 'id' => $paymentIntent->id]);
            return redirect()->route('cart.index')->with('error', 'Payment has not succeeded.');
        }

        $orderId = $paymentIntent->metadata->order_id;
        $order = DtfOrder::findOrFail($orderId);

        if ($order->status == 2) {
            Log::info('DEBUG: Order already marked as paid', ['order_id' => $order->id]);
            $order->load(['orderStatus', 'shippingAddress', 'paymentMethod', 'business']);
            return view('checkout.complete', compact('order'));
        }

        try {
            \Illuminate\Support\Facades\DB::transaction(function () use ($order, $paymentIntent) {
                $stripeFee = 0;
                $chargeId = null;
                $charge = $paymentIntent->latest_charge ?? null;

                if ($charge) {
                    $chargeId = is_string($charge) ? $charge : $charge->id;
                    $btId = is_string($charge->balance_transaction) ? $charge->balance_transaction : ($charge->balance_transaction->id ?? null);

                    if ($btId) {
                        // Explicitly retrieve balance transaction with retries
                        $retries = 0;
                        $bt = null;
                        while ($retries < 5) { // Increased retries
                            try {
                                Log::info("DEBUG: Attempting explicit BT retrieval for PI: {$paymentIntent->id} (Retry $retries)");
                                $bt = \Stripe\BalanceTransaction::retrieve($btId);
                                if ($bt && isset($bt->fee)) {
                                    $stripeFee = $bt->fee / 100;
                                    Log::info("DEBUG: Stripe fee found in BT for PI: {$paymentIntent->id}: $stripeFee");
                                    break;
                                }
                            } catch (\Exception $e) {
                                Log::warning("DEBUG: Failed to retrieve balance transaction explicitly for PI: {$paymentIntent->id}: " . $e->getMessage());
                                $retries++;
                                if ($retries < 5) sleep(1 * $retries); // Exponential backoff
                            }
                        }
                    }
                }

                if ($stripeFee == 0) {
                    Log::warning('DEBUG: Stripe fee is 0 after initial attempts for PI: ' . $paymentIntent->id, [
                        'has_charge' => !!$charge,
                        'bt_id' => $btId ?? 'none',
                    ]);
                }

                // Mark as paid
                Log::info("DEBUG: Record payment info start for Order {$order->id}", [
                    'db_connection' => (new PaymentInfo())->getConnectionName(),
                    'config_fuel_conn' => config('database.fuel_connection')
                ]);
                $paymentInfo = PaymentInfo::create([
                    'dtforder_id' => $order->id,
                    'business_id' => $order->business_id,
                    'processor' => 'Stripe',
                    'processor_confirm' => $paymentIntent->id,
                    'stripe_charge_id' => $chargeId,
                    'amount' => $paymentIntent->amount_received / 100,
                    'stripe_fee' => $stripeFee,
                    'notes' => 'Payment received via Stripe.',
                    'status' => 'complete',
                ]);

                // Final check: if fee is still 0, try one more time after a short delay
                if ($stripeFee == 0) {
                    try {
                        // We use a slightly longer delay here as Stripe might be processing the fee calculation
                        sleep(3);
                        Log::info("DEBUG: Final fee recovery attempt for PI: " . $paymentIntent->id);
                        $pi = \Stripe\PaymentIntent::retrieve([
                            'id' => $paymentIntent->id,
                            'expand' => ['latest_charge.balance_transaction']
                        ]);

                    if ($pi->latest_charge) {
                        $chargeId = is_string($pi->latest_charge) ? $pi->latest_charge : ($pi->latest_charge->id ?? null);
                        if ($chargeId && str_starts_with($chargeId, 'ch_')) {
                             $paymentInfo->update(['stripe_charge_id' => $chargeId]);
                        }
                    }

                    if (isset($pi->latest_charge->balance_transaction->fee)) {
                        $stripeFee = $pi->latest_charge->balance_transaction->fee / 100;
                        $paymentInfo->update(['stripe_fee' => $stripeFee]);
                        Log::info("DEBUG: Fee recovered for PI: " . $paymentIntent->id . " after PI re-retrieve: $" . $stripeFee);
                    } else {
                        // Try one last explicit retrieval of the BT ID if we can find it
                        $btId = is_string($pi->latest_charge->balance_transaction ?? null)
                            ? $pi->latest_charge->balance_transaction
                            : ($pi->latest_charge->balance_transaction->id ?? null);

                        if ($btId) {
                            $bt = \Stripe\BalanceTransaction::retrieve($btId);
                            if ($bt && isset($bt->fee)) {
                                $stripeFee = $bt->fee / 100;
                                $paymentInfo->update(['stripe_fee' => $stripeFee]);
                                Log::info("DEBUG: Fee recovered for PI: " . $paymentIntent->id . " after explicit BT retrieve: $" . $stripeFee);
                            }
                        }
                    }
                    } catch (\Exception $e) {
                        Log::warning('DEBUG: Final fee recovery attempt failed: ' . $e->getMessage());
                    }
                }

                $order->finalizeMetrics();
                $order->update(['status' => 2]); // Status 2 = Paid/Processing

                // Integrate with QBO
                try {
                    Log::info("DEBUG: Attempting QBO integration after Stripe success", ['order_id' => $order->id]);
                    if (!$order->qbo_invoice_id) {
                        Log::info("DEBUG: Order has no QBO invoice, creating one now", ['order_id' => $order->id]);
                        $this->qbo->createInvoice($order->business, $order);
                    }

                    // ABSOLUTE RULE: Invoices are marked PAID when Stripe charge succeeds (GROSS amount)
                    Log::info("DEBUG: Recording QBO payment for order", ['order_id' => $order->id, 'qbo_invoice_id' => $order->qbo_invoice_id, 'amount' => $paymentInfo->amount]);
                    $this->qbo->recordPayment($order, $paymentInfo->amount, $paymentIntent->id, $paymentInfo->stripe_fee);

                    // ABSOLUTE RULE: Stripe fees are recorded IMMEDIATELY at charge time
                    if ($paymentInfo->stripe_fee > 0) {
                        try {
                            Log::info("DEBUG: Recording immediate Stripe fee for order {$order->id}, fee: {$paymentInfo->stripe_fee}");
                            $feeEntry = (object)[
                                'fee' => $paymentInfo->stripe_fee,
                                'stripe_transaction_id' => $chargeId ?? $paymentIntent->id,
                                'qbo_expense_id' => $paymentInfo->qbo_fee_expense_id,
                                'update' => function($data) use ($paymentInfo) {
                                    $paymentInfo->update(['qbo_fee_expense_id' => $data['qbo_expense_id']]);
                                }
                            ];
                            $this->qbo->recordStripeFee($feeEntry);
                            Log::info("DEBUG: Successfully recorded immediate Stripe fee in QBO", ['order_id' => $order->id, 'qbo_expense_id' => $paymentInfo->fresh()->qbo_fee_expense_id]);
                        } catch (\Exception $fe) {
                            Log::error("DEBUG: Failed to record immediate Stripe fee in QBO: " . $fe->getMessage());
                        }
                    } else {
                        Log::warning("DEBUG: Skipping Stripe fee recording because fee is 0.", ['order_id' => $order->id]);
                    }
                } catch (\Exception $e) {
                    Log::error('QBO Error after Stripe payment: ' . $e->getMessage(), [
                        'order_id' => $order->id,
                        'payment_intent' => $paymentIntent->id,
                        'trace' => $e->getTraceAsString()
                    ]);
                }
            });
            Log::info('DEBUG: Order successfully finalized via Stripe', ['order_id' => $order->id, 'pi' => $paymentIntent->id]);
        } catch (\Exception $e) {
            Log::error('DEBUG: Failed to finalize order in database after successful Stripe payment', [
                'order_id' => $order->id,
                'pi' => $paymentIntent->id,
                'error' => $e->getMessage()
            ]);
            // Still show completion page because payment was successful, but admin needs to know
            // Or maybe show a message that order is being processed.
        }

        $order->load(['orderStatus', 'shippingAddress', 'paymentMethod', 'business']);

        // TODO: Send emails, other post-processing

        return view('checkout.complete', compact('order'));
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

            foreach ($invoices as $inv) {
                if (in_array($inv['Id'], $invoiceIds)) {
                    $total += $inv['Balance'];
                    $selectedInvoices[] = $inv['Id'];
                    $selectedDocNumbers[] = $inv['DocNumber'] ?? $inv['Id'];
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
                'expand' => ['latest_charge.balance_transaction']
            ]);

            Log::info('DEBUG: [START] Stripe PaymentIntent retrieved (QBO Pay)', [
                'status' => $paymentIntent->status,
                'id' => $paymentIntent->id,
                'metadata' => $paymentIntent->metadata
            ]);

            if ($paymentIntent->status !== 'succeeded') {
                Log::warning('DEBUG: [TERMINATE] QBO PaymentIntent status not succeeded', ['status' => $paymentIntent->status, 'id' => $paymentIntent->id]);
                return redirect()->route('account')->with('error', 'Payment has not succeeded.');
            }

            Log::info("DEBUG: [PROCEED] QBO Payment successful, processing invoices", ['invoices' => $paymentIntent->metadata->qbo_invoice_ids ?? 'MISSING']);
            $invoiceIds = explode(',', $paymentIntent->metadata->qbo_invoice_ids ?? '');
            $businessId = $paymentIntent->metadata->business_id;
            $business = \App\Models\Business::find($businessId);

            $charge = $paymentIntent->latest_charge ?? null;
            $chargeId = is_string($charge) ? $charge : ($charge->id ?? null);
            $stripeFee = 0;

            if ($charge && !is_string($charge) && isset($charge->balance_transaction->fee)) {
                $stripeFee = $charge->balance_transaction->fee / 100;
            }

            // Retry if fee is 0, similar to regular checkout
            if ($stripeFee == 0 && $charge) {
                $retries = 0;
                while ($retries < 5) {
                    try {
                        Log::info("DEBUG: [STEP 0] Attempting explicit BT retrieval for PI: {$paymentIntentId} (Retry $retries)");
                        $pi = PaymentIntent::retrieve([
                            'id' => $paymentIntentId,
                            'expand' => ['latest_charge.balance_transaction']
                        ]);
                        if (isset($pi->latest_charge->balance_transaction->fee)) {
                            $stripeFee = $pi->latest_charge->balance_transaction->fee / 100;
                            Log::info("DEBUG: [STEP 0] Stripe fee found for PI: {$paymentIntentId}: $stripeFee");
                            break;
                        }
                    } catch (\Exception $e) {
                        Log::warning("DEBUG: [STEP 0] BT retrieval failed for PI: {$paymentIntentId}: " . $e->getMessage());
                        $retries++;
                        if ($retries < 5) sleep(1 * $retries);
                    }
                }
            }

            // CREATE PaymentInfo record FIRST so it is tracked even if QBO fails
            $paymentInfo = null;
            try {
                $charge = $paymentIntent->latest_charge ?? null;
                $chargeId = is_string($charge) ? $charge : ($charge->id ?? null);

                Log::info("DEBUG: [STEP 1] Starting PaymentInfo creation for QBO Invoice Payment", [
                    'pi' => $paymentIntent->id,
                    'amount' => $paymentIntent->amount_received / 100,
                    'fee' => $stripeFee,
                    'db_connection' => (new PaymentInfo())->getConnectionName(),
                    'config_fuel_conn' => config('database.fuel_connection')
                ]);

                $paymentInfo = PaymentInfo::create([
                    'dtforder_id' => 0, // Not tied to a single DTF order, but database requires non-null
                    'business_id' => $paymentIntent->metadata->business_id ?? null,
                    'processor' => 'Stripe',
                    'processor_confirm' => $paymentIntent->id,
                    'stripe_charge_id' => $chargeId,
                    'amount' => $paymentIntent->amount_received / 100,
                    'stripe_fee' => $stripeFee,
                    'qbo_invoice_numbers' => $paymentIntent->metadata->qbo_invoice_numbers ?? $paymentIntent->metadata->qbo_invoice_ids ?? null,
                    'notes' => 'QBO Invoice Payment for Invoices: ' . ($paymentIntent->metadata->qbo_invoice_numbers ?? $paymentIntent->metadata->qbo_invoice_ids ?? 'N/A'),
                    'status' => 'processing',
                ]);

                if ($paymentInfo) {
                    Log::info("DEBUG: [STEP 1 SUCCESS] PaymentInfo created with ID: " . $paymentInfo->id . " on connection: " . $paymentInfo->getConnectionName());
                } else {
                    Log::error("DEBUG: [STEP 1 FAILURE] PaymentInfo::create returned null");
                }
            } catch (\Exception $pe) {
                Log::error("DEBUG: [STEP 1 EXCEPTION] Failed to create initial PaymentInfo: " . $pe->getMessage(), [
                    'trace' => $pe->getTraceAsString()
                ]);
            }

            // Ensure invoices are marked PAID by recording payments FIRST, then fees.
            foreach ($invoiceIds as $invoiceId) {
                if (empty($invoiceId)) continue;
                try {
                    Log::info("DEBUG: [STEP 2] Processing QBO Invoice $invoiceId");
                    $invoiceRes = $this->qbo->request('GET', "invoice/{$invoiceId}");
                    if (isset($invoiceRes['Invoice'])) {
                        $invoice = $invoiceRes['Invoice'];
                        $balance = $invoice['Balance'];
                        $qboInvoiceCustomerId = $invoice['CustomerRef']['value'];

                        Log::info("DEBUG: Invoice $invoiceId balance: $balance, QBO Customer ID: $qboInvoiceCustomerId");

                        if ($balance > 0) {
                            // Ensure we use the customer ID from the invoice if available,
                            // though it should match the metadata one.
                            $this->qbo->recordGenericPayment(
                                $qboInvoiceCustomerId,
                                $invoiceId,
                                $balance,
                                $paymentIntent->id
                            );
                            Log::info("DEBUG: Successfully recorded payment for Invoice $invoiceId");
                        } else {
                            Log::info("DEBUG: Invoice $invoiceId already has 0 balance, skipping payment recording.");
                        }
                    } else {
                        Log::error("DEBUG: Failed to retrieve invoice $invoiceId from QBO", ['response' => $invoiceRes]);
                    }
                } catch (\Exception $ie) {
                    Log::error("Failed to record payment for QBO Invoice {$invoiceId}: " . $ie->getMessage());
                }
            }

            // Record the Stripe fee as an expense in QBO immediately
            $qboFeeExpenseId = null;
            if ($stripeFee > 0) {
                try {
                    Log::info("DEBUG: [STEP 3] Recording immediate Stripe fee for QBO Payment, fee: $stripeFee");
                    $feeEntry = (object)[
                        'fee' => $stripeFee,
                        'stripe_transaction_id' => $chargeId ?? $paymentIntent->id,
                        'qbo_expense_id' => null,
                        'update' => function($data) use (&$qboFeeExpenseId) {
                            $qboFeeExpenseId = $data['qbo_expense_id'];
                        }
                    ];
                    $this->qbo->recordStripeFee($feeEntry);
                    Log::info("DEBUG: [STEP 3 SUCCESS] Successfully recorded Stripe fee in QBO", ['qbo_expense_id' => $qboFeeExpenseId]);
                } catch (\Exception $fe) {
                    Log::error("DEBUG: [STEP 3 ERROR] Failed to record Stripe fee for QBO Payment: " . $fe->getMessage());
                }
            } else {
                Log::warning("DEBUG: [STEP 3 SKIP] Skipping Stripe fee recording for QBO Payment because fee is 0", ['pi' => $paymentIntent->id]);
            }

            // Update PaymentInfo record with final results
            try {
                if ($paymentInfo) {
                    Log::info("DEBUG: [STEP 4] Updating PaymentInfo for QBO Invoice Payment to complete", [
                        'pi' => $paymentIntent->id,
                        'payment_info_id' => $paymentInfo->id,
                        'qbo_fee_expense_id' => $qboFeeExpenseId
                    ]);
                    $paymentInfo->update([
                        'stripe_fee' => $stripeFee,
                        'qbo_fee_expense_id' => $qboFeeExpenseId,
                        'qbo_invoice_numbers' => $paymentIntent->metadata->qbo_invoice_numbers ?? $paymentIntent->metadata->qbo_invoice_ids ?? null,
                        'status' => 'complete',
                    ]);
                    Log::info("DEBUG: [STEP 4 SUCCESS] PaymentInfo updated to complete");
                } else {
                    Log::warning("DEBUG: [STEP 4 FALLBACK] PaymentInfo record was not created at start, creating it now", ['pi' => $paymentIntent->id]);
                    $newPI = PaymentInfo::create([
                        'dtforder_id' => 0, // Not tied to a single DTF order, but database requires non-null
                        'processor' => 'Stripe',
                        'processor_confirm' => $paymentIntent->id,
                        'stripe_charge_id' => $chargeId,
                        'amount' => $paymentIntent->amount_received / 100,
                        'stripe_fee' => $stripeFee,
                        'qbo_fee_expense_id' => $qboFeeExpenseId,
                        'qbo_invoice_numbers' => $paymentIntent->metadata->qbo_invoice_numbers ?? $paymentIntent->metadata->qbo_invoice_ids ?? null,
                        'notes' => 'QBO Invoice Payment (Fallback Created) for Invoices: ' . ($paymentIntent->metadata->qbo_invoice_numbers ?? $paymentIntent->metadata->qbo_invoice_ids ?? 'N/A'),
                        'status' => 'complete',
                    ]);
                    Log::info("DEBUG: [STEP 4 FALLBACK SUCCESS] PaymentInfo created at the end with ID: " . $newPI->id);
                }
            } catch (\Exception $pe) {
                Log::error("DEBUG: [STEP 4 EXCEPTION] Failed to update/create final PaymentInfo: " . $pe->getMessage(), [
                    'trace' => $pe->getTraceAsString()
                ]);
            }

            // Clear cache
            Cache::forget('qbo_data_' . $businessId);

            Log::info("DEBUG: [FINISHED] QBO Payment process finished successfully", ['pi' => $paymentIntent->id]);

            return redirect()->route('account')->with('success', 'Payment successful! Your QuickBooks invoices have been updated.');

        } catch (\Exception $e) {
            Log::error('QBO Payment Completion Error: ' . $e->getMessage());
            return redirect()->route('account')->with('error', 'Payment succeeded but failed to update QuickBooks: ' . $e->getMessage());
        }
    }
}
