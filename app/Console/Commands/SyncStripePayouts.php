<?php

namespace App\Console\Commands;

use App\Models\StripePayout;
use App\Models\QboToken;
use App\Models\StripeSyncLog;
use App\Services\StripePayoutService;
use App\Services\QboService;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;

class SyncStripePayouts extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'stripe:sync-payouts {--limit=10}';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Sync recent Stripe payouts and transfer to QBO';

    /**
     * Execute the console command.
     */
    public function handle(StripePayoutService $payoutService, QboService $qbo)
    {
        $limit = $this->option('limit');
        $this->info("Starting Stripe payout sync (limit: {$limit})...");

        try {
            $payoutService->syncPayouts($limit);

            $payoutSyncCount = 0;
            if (QboToken::getTokenRecord()) {
                $recentPayouts = StripePayout::whereNull('qbo_transfer_id')
                    ->where('status', 'paid')
                    ->where('arrival_date', '>=', now()->subDays(30))
                    ->orderBy('arrival_date', 'desc')
                    ->limit(10)
                    ->get();

                foreach ($recentPayouts as $payout) {
                    $this->info("Syncing payout {$payout->stripe_payout_id} to QBO...");
                    try {
                        if (!$payout->qbo_transfer_id) {
                            $qbo->recordStripePayoutTransfer($payout);
                            $payoutSyncCount++;
                            $this->info("Successfully synced payout {$payout->stripe_payout_id} to QBO.");
                        }
                    } catch (\Exception $qe) {
                        $this->error("QBO sync failed for payout {$payout->stripe_payout_id}: " . $qe->getMessage());
                    }
                }
            } else {
                $this->warn("QBO not connected. Skipping QBO sync.");
            }

            StripeSyncLog::log('cron', 'success', "Synced Stripe payouts (limit {$limit}). Created {$payoutSyncCount} Transfers.");
            $this->info("Stripe payout sync completed. Created {$payoutSyncCount} Transfers.");
        } catch (\Exception $e) {
            $this->error("Error syncing payouts: " . $e->getMessage());
            Log::error("SyncStripePayouts Command Error: " . $e->getMessage());
            StripeSyncLog::log('cron', 'failure', "Error syncing payouts: " . $e->getMessage());
            return 1;
        }

        return 0;
    }
}
