<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

use App\Models\DtfOrder;
use App\Models\DtfImage;
use App\Services\QboService;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Cache;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

class AccountController extends Controller
{
    public function index()
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            if ($user->role === 'admin') {
                return redirect()->route('admin.dashboard')->with('info', 'You are logged in as admin and do not have a linked business. Use the admin panel to manage businesses.');
            }
            return redirect()->route('home')->with('error', 'No business associated with your account.');
        }

        return view('account.index', compact('business'));
    }

    public function orders(Request $request, QboService $qbo)
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) return response()->json(['error' => 'No business found'], 404);

        $orders = DtfOrder::with(['orderStatus', 'paymentInfo', 'dtfImages'])
            ->where('business_id', $business->id)
            ->orderBy('id', 'desc')
            ->paginate(10);

        // We'll also need the QBO invoice map for the order list
        $qboInvoicesMap = [];
        if ($business->qbo_customer_id) {
            $cacheKey = 'qbo_data_' . $business->id;
            $qboData = Cache::get($cacheKey);
            // If cache is missing/stale, fetch fresh so Orders tab shows correct payment status.
            if (!$qboData || !isset($qboData['invoice_history'])) {
                try {
                    $qboData = [
                        'balance' => $qbo->getCustomerBalance($business->qbo_customer_id),
                        'unpaid_invoices' => $qbo->getUnpaidInvoices($business->qbo_customer_id),
                        'invoice_history' => $qbo->getInvoiceHistory($business->qbo_customer_id),
                    ];
                    Cache::put($cacheKey, $qboData, 600);
                } catch (\Exception $e) {
                    \Illuminate\Support\Facades\Log::warning("Could not refresh QBO data for orders tab, business {$business->id}: " . $e->getMessage());
                }
            }
            if ($qboData && isset($qboData['invoice_history'])) {
                foreach ($qboData['invoice_history'] as $inv) {
                    if (isset($inv['Id'])) $qboInvoicesMap[$inv['Id']] = $inv;
                    if (isset($inv['DocNumber'])) $qboInvoicesMap['doc_' . $inv['DocNumber']] = $inv;
                }
            }
        }

        if ($request->expectsJson()) {
            return response()->json([
                'html' => view('account.tabs._orders_table', compact('orders', 'qboInvoicesMap', 'business'))->render(),
                'pagination' => (string) $orders->links()
            ]);
        }

        return view('account.tabs._orders_table', compact('orders', 'qboInvoicesMap', 'business'));
    }

    public function invoices(Request $request, QboService $qbo)
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) return response()->json(['error' => 'No business found'], 404);

        // Fetch QBO Balance and Invoices
        $qboData = [
            'balance' => 0,
            'unpaid_invoices' => [],
            'invoice_history' => []
        ];

        if (!$business->qbo_customer_id) {
            try {
                $qbo->findOrCreateCustomer($business);
            } catch (\Exception $e) {
                \Illuminate\Support\Facades\Log::warning("Could not find or create QBO customer for business {$business->id}: " . $e->getMessage());
            }
        }

        if ($business->qbo_customer_id) {
            $cacheKey = 'qbo_data_' . $business->id;
            $qboData = Cache::remember($cacheKey, 600, function () use ($qbo, $business) {
                try {
                    return [
                        'balance' => $qbo->getCustomerBalance($business->qbo_customer_id),
                        'unpaid_invoices' => $qbo->getUnpaidInvoices($business->qbo_customer_id),
                        'invoice_history' => $qbo->getInvoiceHistory($business->qbo_customer_id)
                    ];
                } catch (\Exception $e) {
                    \Illuminate\Support\Facades\Log::warning("Could not fetch QBO data for business {$business->id}: " . $e->getMessage());
                    return [
                        'balance' => 0,
                        'unpaid_invoices' => [],
                        'invoice_history' => []
                    ];
                }
            });
        }

        $qboBalance = $qboData['balance'] ?? 0;
        $unpaidInvoices = $qboData['unpaid_invoices'] ?? [];
        $invoiceHistory = $qboData['invoice_history'] ?? [];

        if ($request->expectsJson()) {
            return response()->json([
                'balance' => $qboBalance,
                'html' => view('account.tabs._invoices_table', compact('invoiceHistory', 'unpaidInvoices', 'qboBalance'))->render(),
                'modal_html' => view('account._pay_invoices_modal', compact('unpaidInvoices', 'qboBalance'))->render(),
                'summary_html' => view('account._qbo_summary', compact('qboBalance', 'unpaidInvoices'))->render(),
            ]);
        }

        return view('account.tabs._invoices_table', compact('invoiceHistory', 'unpaidInvoices', 'qboBalance'));
    }

    public function images(Request $request)
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) return response()->json(['error' => 'No business found'], 404);

        $images = DtfImage::whereHas('dtfOrder', function($q) use ($business) {
                $q->where('business_id', $business->id);
            })
            ->orderBy('id', 'desc')
            ->get()
            ->unique('image');

        if ($request->expectsJson()) {
            return response()->json([
                'html' => view('account.tabs._images_grid', compact('images'))->render()
            ]);
        }

        return view('account.tabs._images_grid', compact('images'));
    }

    public function downloadImage(DtfImage $image): BinaryFileResponse
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            abort(404);
        }

        $belongsToBusiness = DtfImage::whereKey($image->id)
            ->whereHas('dtfOrder', function ($q) use ($business) {
                $q->where('business_id', $business->id);
            })
            ->exists();

        if (!$belongsToBusiness) {
            abort(403);
        }

        $relativePath = ltrim((string) $image->image, '/');
        $absolutePath = public_path($relativePath);

        if (!is_file($absolutePath)) {
            abort(404, 'Image file not found.');
        }

        $filename = $image->downloadFilename($absolutePath);

        return response()->download($absolutePath, $filename);
    }

    public function showOrder(DtfOrder $order)
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            return redirect()->route('account')->with('error', 'No business found.');
        }

        if ((int) $order->business_id !== (int) $business->id) {
            abort(403);
        }

        $order->load(['orderStatus', 'paymentInfo', 'paymentMethod', 'shippingMethod', 'shippingAddress', 'dtfImages']);

        return view('account.orders.show', compact('order', 'business'));
    }
}
