<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\OrderStatus;
use App\Services\QboService;
use Illuminate\Database\Eloquent\Collection as EloquentCollection;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;

class OrderController extends Controller
{
    private const PRODUCTION_STATUS = 3;
    private const PRODUCTION_LOCKED_STATUSES = [4, 5, 6, 8, 10, 11, 12, 13, 14];

    private function canEditPricing(DtfOrder $order): bool
    {
        return (int)$order->status === 1 && empty($order->qbo_invoice_id);
    }

    public function index(Request $request, QboService $qbo)
    {
        $query = DtfOrder::with(['business', 'orderStatus', 'paymentInfo']);

        if ($request->filled('search')) {
            $search = $request->search;
            $query->whereHas('business', function ($q) use ($search) {
                $q->where('business_name', 'like', "%{$search}%")
                  ->orWhere('contact_name', 'like', "%{$search}%")
                  ->orWhere('email', 'like', "%{$search}%");
            })->orWhere('id', 'like', "%{$search}%");
        }

        if ($request->filled('filter_status')) {
            $query->where('status', $request->filter_status);
        }

        if ($request->filled('filter_paid')) {
            if ($request->filter_paid === 'paid') {
                $query->paid();
            } elseif ($request->filter_paid === 'unpaid') {
                $query->unpaid();
            }
        }

        $orders = $query->orderBy('id', 'desc')->paginate(15)->withQueryString();
        $orderStatuses = OrderStatus::orderBy('sort_order', 'asc')->get();
        $qboInvoicesMapByBusiness = [];

        // Mirror customer-side payment status logic by using QBO invoice history when available.
        $businessesOnPage = $orders->getCollection()
            ->pluck('business')
            ->filter()
            ->unique('id')
            ->values();

        foreach ($businessesOnPage as $business) {
            if (empty($business->qbo_customer_id)) {
                continue;
            }

            $cacheKey = 'admin_qbo_invoice_history_' . $business->id;
            $invoiceHistory = Cache::remember($cacheKey, 600, function () use ($qbo, $business) {
                try {
                    return $qbo->getInvoiceHistory($business->qbo_customer_id);
                } catch (\Throwable $e) {
                    \Illuminate\Support\Facades\Log::warning('Admin orders: failed QBO invoice history fetch', [
                        'business_id' => $business->id,
                        'error' => $e->getMessage(),
                    ]);
                    return [];
                }
            });

            $map = [];
            foreach ((array)$invoiceHistory as $inv) {
                if (isset($inv['Id'])) {
                    $map[$inv['Id']] = $inv;
                }
                if (isset($inv['DocNumber'])) {
                    $map['doc_' . $inv['DocNumber']] = $inv;
                }
            }
            $qboInvoicesMapByBusiness[$business->id] = $map;
        }

        return view('admin.orders.index', compact('orders', 'orderStatuses', 'qboInvoicesMapByBusiness'));
    }

    public function production(Request $request)
    {
        // Status 2 is "Paid/Processing" which usually means ready for production
        // In the legacy system, production view might have specific statuses.
        // For now let's use status 2 as a default "Ready for Production"
        $query = DtfOrder::with(['business', 'orderStatus'])
            ->whereIn('status', [2]);

        $orders = $query->orderBy('id', 'asc')->paginate(15)->withQueryString();

        return view('admin.orders.production', compact('orders'));
    }

    public function show(DtfOrder $order)
    {
        $order->load(['business', 'orderStatus', 'dtfImages', 'shippingAddress', 'paymentMethod', 'paymentInfo']);
        if ((int)$order->status === 1 && empty($order->qbo_invoice_id)) {
            $this->refreshOrderTotals($order);
            $order->refresh()->load(['business', 'orderStatus', 'dtfImages', 'shippingAddress', 'paymentMethod', 'paymentInfo']);
        }
        $orderStatuses = \App\Models\OrderStatus::orderBy('sort_order', 'asc')->get();
        return view('admin.orders.show', compact('order', 'orderStatuses'));
    }

    public function productionOrder(DtfOrder $order)
    {
        $order->load(['business', 'orderStatus', 'dtfImages', 'shippingAddress', 'paymentMethod', 'paymentInfo']);
        $orderStatuses = OrderStatus::orderBy('sort_order', 'asc')->get();
        return view('admin.orders.production_order', compact('order', 'orderStatuses'));
    }

    public function updateStatus(Request $request)
    {
        $fuelDb = env('FUEL_DB_CONNECTION', 'fuelmysql');
        $request->validate([
            'order_id' => "required|exists:{$fuelDb}.dtforders,id",
            'order_status' => "required|exists:{$fuelDb}.order_statuses,id",
        ]);

        $order = DtfOrder::findOrFail($request->order_id);
        $order->update(['status' => $request->order_status]);

        return back()->with('success', 'Order status updated successfully.');
    }

    public function createQboInvoice(Request $request, \App\Services\QboService $qbo)
    {
        $fuelDb = env('FUEL_DB_CONNECTION', 'fuelmysql');
        $request->validate([
            'order_id' => "required|exists:{$fuelDb}.dtforders,id",
        ]);

        $order = DtfOrder::with(['business', 'dtfImages', 'paymentInfo'])->findOrFail($request->order_id);

        if ($order->qbo_invoice_id) {
            return back()->with('error', 'Order already has a QBO invoice.');
        }

        try {
            $qbo->createInvoice($order->business, $order);
            $message = 'Quickbooks invoice created successfully.';

            // If it's already paid via Stripe, record the payment too
            if ($order->paymentInfo && $order->paymentInfo->status === 'complete' && $order->paymentInfo->processor === 'Stripe') {
                try {
                    $qbo->recordPayment(
                        $order,
                        $order->paymentInfo->amount,
                        $order->paymentInfo->processor_confirm,
                        $order->paymentInfo->stripe_fee
                    );
                    $message .= ' Stripe payment was also recorded in QuickBooks.';
                } catch (\Exception $pe) {
                    $message .= ' Note: Invoice created, but failed to record payment: ' . $pe->getMessage();
                }
            }

            return back()->with('success', $message);
        } catch (\Exception $e) {
            \Illuminate\Support\Facades\Log::error('Admin QBO Error: ' . $e->getMessage());
            return back()->with('error', 'Failed to create QBO invoice: ' . $e->getMessage());
        }
    }

    public function addToProduction(Request $request)
    {
        \Illuminate\Support\Facades\Log::info('addToProduction call', $request->all());
        error_log('addToProduction call: ' . json_encode($request->all()));

        try {
            $request->validate([
                'image_id' => 'nullable|integer',
                'order_id' => 'nullable|integer',
            ]);
        } catch (\Illuminate\Validation\ValidationException $e) {
            \Illuminate\Support\Facades\Log::error('Validation failed', $e->errors());
            return response()->json(['status' => 'error', 'message' => 'Validation failed', 'errors' => $e->errors()], 422);
        }

        if ($request->has('image_id') && $request->image_id) {
            $image = \App\Models\DtfImage::find($request->image_id);
            if (!$image) {
                \Illuminate\Support\Facades\Log::error('Image not found: ' . $request->image_id);
                return response()->json(['status' => 'error', 'message' => 'Image not found.'], 404);
            }
            if ($image->item_type === 'gang_sheet') {
                return response()->json([
                    'status' => 'error',
                    'message' => 'Gang sheet items are manual-production only in phase 1.'
                ], 422);
            }
            try {
                $readd = $request->boolean('readd', false);
                if (!$readd && (int)$image->production === 1) {
                    if ($image->dtfOrder) {
                        $this->ensureOrderInProduction($image->dtfOrder);
                        $image->dtfOrder->checkProductionStatus();
                    }

                    return response()->json([
                        'status' => 'success',
                        'message' => 'Image already in production.',
                        'skipped' => true,
                    ]);
                }

                $groupRows = $this->productionDuplicateGroup($image, $readd);
                \Illuminate\Support\Facades\Log::info('Calling production duplicate group', [
                    'image_id' => $image->id,
                    'order_id' => $image->dtforder_id,
                    'group_count' => $groupRows->count(),
                    'quantity' => $this->productionGroupQuantity($groupRows),
                    'readd' => $readd,
                ]);
                $this->addProductionGroup($groupRows);

                // Refresh order and check status
                if ($image->dtfOrder) {
                    $this->ensureOrderInProduction($image->dtfOrder);
                    $image->dtfOrder->checkProductionStatus();
                }

                \Illuminate\Support\Facades\Log::info('Successfully added image ' . $image->id . ' to production');
                return response()->json([
                    'status' => 'success',
                    'message' => $groupRows->count() > 1
                        ? 'Image group added to production.'
                        : 'Image added to production.',
                    'group_count' => $groupRows->count(),
                    'quantity' => $this->productionGroupQuantity($groupRows),
                ]);
            } catch (\Exception $e) {
                \Illuminate\Support\Facades\Log::error('ProductionHelper Error for image ' . $image->id . ': ' . $e->getMessage(), [
                    'exception' => $e,
                    'trace' => $e->getTraceAsString()
                ]);
                return response()->json(['status' => 'error', 'message' => $e->getMessage()], 500);
            }
        }

        if ($request->has('order_id') && $request->order_id) {
            $order = DtfOrder::with('dtfImages')->find($request->order_id);
            if (!$order) {
                \Illuminate\Support\Facades\Log::error('Order not found: ' . $request->order_id);
                return response()->json(['status' => 'error', 'message' => 'Order not found.'], 404);
            }
            $mode = (string)$request->input('production_mode', 'new');
            $includeAlreadyProduced = $mode === 'all';
            $eligibleImages = $order->dtfImages
                ->filter(fn (DtfImage $image) => $image->item_type !== 'gang_sheet')
                ->filter(fn (DtfImage $image) => $includeAlreadyProduced || (int)$image->production !== 1)
                ->values();

            \Illuminate\Support\Facades\Log::info('Adding order ' . $order->id . ' to production', [
                'mode' => $mode,
                'images' => $eligibleImages->count(),
            ]);

            $groups = $eligibleImages->groupBy(fn (DtfImage $image) => $this->productionDuplicateKey($image));
            $processedGroups = 0;
            $processedImages = 0;
            $processedQuantity = 0;

            foreach ($groups as $groupRows) {
                try {
                    $groupRows = $groupRows->values();
                    \Illuminate\Support\Facades\Log::info('Calling ProductionHelper::addToProduction for image group in order ' . $order->id, [
                        'representative_image_id' => $groupRows->first()->id,
                        'group_count' => $groupRows->count(),
                        'quantity' => $this->productionGroupQuantity($groupRows),
                    ]);
                    $this->addProductionGroup($groupRows);
                    $processedGroups++;
                    $processedImages += $groupRows->count();
                    $processedQuantity += $this->productionGroupQuantity($groupRows);
                } catch (\Exception $e) {
                    $first = $groupRows->first();
                    \Illuminate\Support\Facades\Log::error('ProductionHelper Error (Order Loop) for image group ' . ($first->id ?? 'unknown') . ': ' . $e->getMessage(), [
                        'exception' => $e
                    ]);
                    return response()->json(['status' => 'error', 'message' => 'Failed on image ' . ($first->id ?? 'unknown') . ': ' . $e->getMessage()], 500);
                }
            }

            $this->ensureOrderInProduction($order);
            $order->checkProductionStatus();

            \Illuminate\Support\Facades\Log::info('Successfully added order ' . $order->id . ' to production');
            return response()->json([
                'status' => 'success',
                'message' => 'Order added to production.',
                'groups_processed' => $processedGroups,
                'images_processed' => $processedImages,
                'quantity_processed' => $processedQuantity,
                'duplicates_skipped' => max(0, $processedImages - $processedGroups),
            ]);
        }

        \Illuminate\Support\Facades\Log::warning('Invalid addToProduction request', $request->all());
        return response()->json(['status' => 'error', 'message' => 'Invalid request.'], 422);
    }

    public function updateLinePricing(Request $request, DtfOrder $order, DtfImage $image)
    {
        if (!$this->canEditPricing($order)) {
            return back()->with('error', 'Pricing is locked for invoiced or non-open orders.');
        }

        if ((int)$image->dtforder_id !== (int)$order->id) {
            abort(404);
        }

        $validated = $request->validate([
            'admin_unit_price' => 'required|numeric|min:0',
        ]);

        $image->update([
            'admin_unit_price' => round((float)$validated['admin_unit_price'], 4),
            'admin_price_locked' => 1,
        ]);

        $this->refreshOrderTotals($order->fresh('dtfImages'));

        return back()->with('success', 'Line price locked.');
    }

    public function clearLinePricing(DtfOrder $order, DtfImage $image)
    {
        if (!$this->canEditPricing($order)) {
            return back()->with('error', 'Pricing is locked for invoiced or non-open orders.');
        }

        if ((int)$image->dtforder_id !== (int)$order->id) {
            abort(404);
        }

        $image->update([
            'admin_unit_price' => null,
            'admin_price_locked' => 0,
        ]);

        $this->refreshOrderTotals($order->fresh('dtfImages'));

        return back()->with('success', 'Line price lock removed.');
    }

    public function applyOrderDiscount(Request $request, DtfOrder $order)
    {
        if (!$this->canEditPricing($order)) {
            return back()->with('error', 'Pricing is locked for invoiced or non-open orders.');
        }

        $validated = $request->validate([
            'discount_pct' => 'required|numeric|min:0|max:100',
        ]);

        $discountPct = round((float)$validated['discount_pct'], 4);
        $factor = max(0.0, (100.0 - $discountPct) / 100.0);

        $order->load('dtfImages');
        if ($order->dtfImages->isEmpty()) {
            return back()->with('error', 'Order has no line items to discount.');
        }

        DB::connection($order->getConnectionName())->transaction(function () use ($order, $factor, $discountPct) {
            foreach ($order->dtfImages as $img) {
                $baseUnit = (float)$img->get_price();
                $img->update([
                    'admin_unit_price' => round($baseUnit * $factor, 4),
                    'admin_price_locked' => 1,
                ]);
            }

            $order->update([
                'admin_discount_pct' => $discountPct,
                'admin_discount_locked' => 1,
            ]);
        });

        $this->refreshOrderTotals($order->fresh('dtfImages'));

        return back()->with('success', 'Order discount applied and locked into line prices.');
    }

    public function clearPricingLocks(DtfOrder $order)
    {
        if (!$this->canEditPricing($order)) {
            return back()->with('error', 'Pricing is locked for invoiced or non-open orders.');
        }

        $order->load('dtfImages');

        DB::connection($order->getConnectionName())->transaction(function () use ($order) {
            foreach ($order->dtfImages as $img) {
                $img->update([
                    'admin_unit_price' => null,
                    'admin_price_locked' => 0,
                ]);
            }

            $order->update([
                'admin_discount_pct' => null,
                'admin_discount_locked' => 0,
            ]);
        });

        $this->refreshOrderTotals($order->fresh('dtfImages'));

        return back()->with('success', 'Pricing locks cleared.');
    }

    private function refreshOrderTotals(DtfOrder $order): void
    {
        $order->loadMissing('dtfImages');
        $subtotal = 0.0;
        foreach ($order->dtfImages as $img) {
            $subtotal += (float)$img->get_total();
        }

        $subtotal = round($subtotal, 2);
        $shipping = (float)($order->shipping_cost ?? 0);
        $salesTax = (float)($order->sales_tax ?? 0);

        $order->update([
            'price' => $subtotal,
            'total_price' => round($subtotal + $shipping + $salesTax, 2),
        ]);
    }

    private function productionDuplicateKey(DtfImage $image): string
    {
        if ($image->item_type === 'gang_sheet') {
            return 'gang_sheet:' . $image->id;
        }

        return implode('|', [
            (string)$image->image,
            number_format((float)$image->width, 2, '.', ''),
            number_format((float)$image->height, 2, '.', ''),
        ]);
    }

    private function productionDuplicateGroup(DtfImage $image, bool $includeAlreadyProduced = false): EloquentCollection
    {
        $query = DtfImage::where('dtforder_id', $image->dtforder_id)
            ->get()
            ->filter(fn (DtfImage $candidate) => $candidate->item_type !== 'gang_sheet')
            ->filter(fn (DtfImage $candidate) => $this->productionDuplicateKey($candidate) === $this->productionDuplicateKey($image));

        if (!$includeAlreadyProduced) {
            $query = $query->filter(fn (DtfImage $candidate) => (int)$candidate->production !== 1);
        }

        $rows = new EloquentCollection($query->values()->all());
        return $rows->isEmpty() ? new EloquentCollection([$image]) : $rows;
    }

    private function productionGroupQuantity($groupRows): int
    {
        return max(1, (int)collect($groupRows)->sum(fn (DtfImage $image) => max(0, (int)$image->quantity)));
    }

    private function addProductionGroup($groupRows): void
    {
        $groupRows = new EloquentCollection(collect($groupRows)->values()->all());
        $representative = $groupRows->first();

        if (!$representative) {
            return;
        }

        \App\Helpers\ProductionHelper::addToProduction($representative, [
            'quantity' => $this->productionGroupQuantity($groupRows),
        ]);

        DtfImage::whereIn('id', $groupRows->pluck('id')->all())->update(['production' => 1]);
    }

    private function ensureOrderInProduction(DtfOrder $order): void
    {
        if ((int)$order->status === self::PRODUCTION_STATUS) {
            return;
        }

        if (in_array((int)$order->status, self::PRODUCTION_LOCKED_STATUSES, true)) {
            \Illuminate\Support\Facades\Log::warning('Skipped production status rollback for locked order', [
                'order_id' => $order->id,
                'status' => $order->status,
            ]);
            return;
        }

        $order->update(['status' => self::PRODUCTION_STATUS]);
    }
}
