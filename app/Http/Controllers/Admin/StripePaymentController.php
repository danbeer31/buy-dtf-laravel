<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\PaymentInfo;
use Illuminate\Http\Request;
use Stripe\Stripe;
use Stripe\PaymentIntent;

class StripePaymentController extends Controller
{
    public function index(Request $request)
    {
        $query = PaymentInfo::with(['dtfOrder.business', 'business'])
            ->where('processor', 'Stripe');

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('processor_confirm', 'like', "%{$search}%")
                  ->orWhere('dtforder_id', 'like', "%{$search}%")
                  ->orWhere('qbo_invoice_numbers', 'like', "%{$search}%")
                  ->orWhere('dtforder_id', '0') // Allow finding generic payments if they search specifically? Or maybe just include them if search is empty
                  ->orWhereHas('dtfOrder', function ($oq) use ($search) {
                      $oq->where('id', 'like', "%{$search}%")
                        ->orWhere('qbo_invoice_number', 'like', "%{$search}%");
                  })
                  ->orWhereHas('dtfOrder.business', function ($bq) use ($search) {
                      $bq->where('business_name', 'like', "%{$search}%");
                  })
                  ->orWhereHas('business', function ($bq) use ($search) {
                      $bq->where('business_name', 'like', "%{$search}%");
                  });
            });
        }

        $payments = $query->orderBy('id', 'desc')->paginate(20)->withQueryString();

        return view('admin.payments.stripe', compact('payments'));
    }

    public function show(PaymentInfo $payment)
    {
        $payment->load(['dtfOrder.business', 'dtfOrder.shippingAddress', 'business']);
        return view('admin.payments.stripe_show', compact('payment'));
    }

    public function refreshFee(PaymentInfo $payment)
    {
        if ($payment->processor !== 'Stripe' || !$payment->processor_confirm) {
            return back()->with('error', 'Not a valid Stripe transaction.');
        }

        try {
            Stripe::setApiKey(config('services.stripe.secret'));
            $paymentIntent = PaymentIntent::retrieve([
                'id' => $payment->processor_confirm,
                'expand' => ['latest_charge.balance_transaction']
            ]);

            $fee = 0;
            if (isset($paymentIntent->latest_charge->balance_transaction->fee)) {
                $fee = $paymentIntent->latest_charge->balance_transaction->fee / 100;
            }

            $payment->update(['stripe_fee' => $fee]);

            return back()->with('success', 'Stripe fee refreshed successfully.');
        } catch (\Exception $e) {
            return back()->with('error', 'Failed to refresh fee from Stripe: ' . $e->getMessage());
        }
    }
}
