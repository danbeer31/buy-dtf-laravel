<?php

namespace App\Jobs;

use App\Models\StripeWebhookEvent;
use App\Services\StripePayoutService;
use App\Services\QboService;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Log;

class ProcessStripePayoutWebhook implements ShouldQueue
{
    use Queueable;

    protected $webhookEventId;

    /**
     * Create a new job instance.
     */
    public function __construct($webhookEventId)
    {
        $this->webhookEventId = $webhookEventId;
    }

    /**
     * Execute the job.
     */
    public function handle(StripePayoutService $payoutService, QboService $qbo): void
    {
        $webhookEvent = StripeWebhookEvent::find($this->webhookEventId);

        if (!$webhookEvent || $webhookEvent->processed_at) {
            return;
        }

        $payload = $webhookEvent->payload;
        $stripePayout = $payload['data']['object'] ?? null;

        if (!$stripePayout || ($stripePayout['object'] ?? '') !== 'payout') {
            Log::warning('ProcessStripePayoutWebhook: Payload does not contain a payout object', ['event_id' => $webhookEvent->stripe_event_id]);
            return;
        }

        $payoutId = $stripePayout['id'];
        Log::info("ProcessStripePayoutWebhook: Processing payout {$payoutId} for event {$webhookEvent->type}");

        // 1. Sync the payout from Stripe to local database
        try {
            $payout = $payoutService->syncPayout($payoutId);
        } catch (\Exception $e) {
            Log::error("ProcessStripePayoutWebhook: Failed to sync payout {$payoutId}: " . $e->getMessage());
            throw $e; // Retry job
        }

        // 2. Handle based on webhook event type
        if ($webhookEvent->type === 'payout.paid' || $payout->status === 'paid') {
            if (!$payout->qbo_transfer_id) {
                try {
                    // Record the Payout Transfer - NET ONLY as per instructions
                    // "Create ONE QBO Transfer: From: Stripe Holding (Bank) To: Real Checking. Amount: net payout"
                    // "Do NOT: Create Stripe fees, Touch invoices, Touch A/R"
                    $qbo->recordStripePayoutTransfer($payout);
                    Log::info("ProcessStripePayoutWebhook: Successfully synced payout {$payoutId} to QBO (Transfer only)");
                } catch (\Exception $e) {
                    Log::warning("ProcessStripePayoutWebhook: QBO transfer failed for payout {$payoutId}: " . $e->getMessage());
                    throw $e;
                }
            }
        } elseif ($webhookEvent->type === 'payout.failed' || $payout->status === 'failed') {
            // "No accounting entry. Mark failed + surface admin alert"
            Log::warning("Stripe Payout FAILED: {$payoutId}");
            // TODO: Surface admin alert (e.g. via database notifications or email)
        } elseif ($webhookEvent->type === 'payout.updated') {
            // "If status transitions -> paid, process it. Otherwise update metadata only"
            if ($payout->status === 'paid' && !$payout->qbo_transfer_id) {
                $qbo->recordStripePayoutTransfer($payout);
            }
        }

        $webhookEvent->update(['processed_at' => now()]);
    }
}
