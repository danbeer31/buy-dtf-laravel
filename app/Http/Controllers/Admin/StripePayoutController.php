<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\StripePayout;
use App\Models\StripeSyncLog;
use App\Services\StripePayoutService;
use Illuminate\Http\Request;

class StripePayoutController extends Controller
{
    public function index()
    {
        $payouts = StripePayout::orderBy('arrival_date', 'desc')->paginate(20);
        return view('admin.payments.stripe_payouts', compact('payouts'));
    }

    public function show(StripePayout $payout)
    {
        $payout->load(['entries.dtfOrder.business']);
        return view('admin.payments.stripe_payout_show', compact('payout'));
    }

    public function sync(\App\Console\Commands\SyncStripePayouts $syncCommand, StripePayoutService $payoutService, \App\Services\QboService $qbo)
    {
        // Increase memory and time limit for this request if possible
        @ini_set('max_execution_time', 120);
        @ini_set('memory_limit', '512M');

        try {
            // Use the logic from the command to avoid duplication
            // We can just call the handle method or ideally refactor the common logic.
            // For now, let's just make sure they use the same underlying service methods.

            $limit = 10;
            $payoutService->syncPayouts($limit);

            $payoutSyncCount = 0;
            if (\App\Models\QboToken::getTokenRecord()) {
                $recentPayouts = \App\Models\StripePayout::whereNull('qbo_transfer_id')
                    ->where('status', 'paid')
                    ->where('arrival_date', '>=', now()->subDays(30))
                    ->orderBy('arrival_date', 'desc')
                    ->limit(10)
                    ->get();

                foreach ($recentPayouts as $payout) {
                    try {
                        if (!$payout->qbo_transfer_id) {
                            $qbo->recordStripePayoutTransfer($payout);
                            $payoutSyncCount++;
                        }
                    } catch (\Exception $qe) {
                        \Illuminate\Support\Facades\Log::warning("QBO Payout sync failed for payout {$payout->stripe_payout_id}: " . $qe->getMessage());
                    }
                }
            }

            StripeSyncLog::log('manual', 'success', "Synced Stripe payouts (limit {$limit}). Created {$payoutSyncCount} Transfers.");

            $msg = 'Stripe payouts synced successfully.';
            if ($payoutSyncCount > 0) {
                $msg .= " Created {$payoutSyncCount} Payout Transfer(s) in QuickBooks.";
            }

            return back()->with('success', $msg);
        } catch (\Exception $e) {
            \Illuminate\Support\Facades\Log::error("Stripe payout sync error: " . $e->getMessage());
            StripeSyncLog::log('manual', 'failure', "Failed to sync payouts: " . $e->getMessage());
            return back()->with('error', 'Failed to sync payouts: ' . $e->getMessage());
        }
    }
}
