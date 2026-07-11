<?php

namespace App\Services;

use App\Models\StripePayout;
use App\Models\StripePayoutEntry;
use App\Models\PaymentInfo;
use Stripe\Stripe;
use Stripe\Payout;
use Stripe\BalanceTransaction;
use Stripe\Charge;
use Illuminate\Support\Facades\Log;

class StripePayoutService
{
    public function __construct()
    {
        Stripe::setApiKey(config('services.stripe.secret'));
    }

    public function syncPayouts($limit = 20)
    {
        Log::info("Starting Stripe payout sync for {$limit} payouts.");
        $startTime = microtime(true);

        // First sync 'pending' and 'in_transit' payouts specifically if needed,
        // but 'all' should return them. Let's just increase the limit and
        // maybe use a wider window if we were filtering by date (we aren't).
        $payouts = Payout::all(['limit' => $limit]);

        $syncedPayouts = [];
        foreach ($payouts->data as $stripePayout) {
            $payoutStartTime = microtime(true);
            try {
                $syncedPayouts[] = $this->syncPayout($stripePayout);
            } catch (\Exception $e) {
                Log::error("Failed to sync individual payout {$stripePayout->id}: " . $e->getMessage());
            }
            $payoutEndTime = microtime(true);
            $duration = round($payoutEndTime - $payoutStartTime, 2);
            Log::info("Processed payout {$stripePayout->id} in {$duration}s.");
        }

        $endTime = microtime(true);
        $totalDuration = round($endTime - $startTime, 2);
        Log::info("Stripe payout sync finished. Total time: {$totalDuration}s.");

        return $syncedPayouts;
    }

    public function syncPayout($stripePayout)
    {
        if (is_string($stripePayout)) {
            $stripePayout = Payout::retrieve($stripePayout);
        }

        // Check if we already have this payout and if it's already 'paid'
        $existingPayout = StripePayout::where('stripe_payout_id', $stripePayout->id)->first();
        if ($existingPayout && $existingPayout->status === 'paid' && $stripePayout->status === 'paid') {
            // Check if there are any unlinked entries. If so, we should re-sync to try to correlate them.
            $unlinkedCount = $existingPayout->entries()->whereNull('dtforder_id')->whereIn('type', ['charge', 'payment'])->count();

            if ($unlinkedCount === 0 && $existingPayout->entries()->count() > 0) {
                // If everything is already synced and linked, we can update status if needed and return
                if ($existingPayout->status !== $stripePayout->status) {
                    $existingPayout->update(['status' => $stripePayout->status]);
                }
                return $existingPayout;
            }
        }

        $payout = StripePayout::updateOrCreate(
            ['stripe_payout_id' => $stripePayout->id],
            [
                'amount' => $stripePayout->amount / 100,
                'currency' => $stripePayout->currency,
                'status' => $stripePayout->status,
                'arrival_date' => date('Y-m-d H:i:s', $stripePayout->arrival_date ?? time()),
                'description' => $stripePayout->description ?? '',
            ]
        );

        // Fetch balance transactions for this payout
        // Note: Filtering by 'payout' in BalanceTransaction::all only works for automatic payouts.
        // For manual payouts, this will throw an InvalidRequestException.
        $balanceTransactions = [];
        try {
            $balanceTransactions = BalanceTransaction::all([
                'payout' => $stripePayout->id,
                'limit' => 100,
            ]);
        } catch (\Stripe\Exception\InvalidRequestException $e) {
            Log::info("Could not fetch balance transactions via payout filter for payout {$stripePayout->id} (manual payout?). Attempting alternative fetch.");

            // For manual payouts, we fetch recent balance transactions and filter manually.
            // We'll look for transactions that happened around the payout creation time.
            $payoutCreated = $stripePayout->created;
            $balanceTransactions = BalanceTransaction::all([
                'created' => [
                    'gte' => $payoutCreated - 86400, // 24h before
                    'lte' => $payoutCreated + 86400, // 24h after
                ],
                'limit' => 100,
            ]);

            // We need to filter this collection to only include transactions associated with this payout.
            // This is tricky because for manual payouts, the transactions don't link back to the payout
            // in the same way. But usually, the user wants to see what was in the payout.
            // However, the error message specifically says they can't be filtered on manual transfers.

            // If we can't accurately link them, we might have to skip the breakdown or warn the user.
            // Given the complexity and potential for incorrect data, let's just return what we find
            // that is EXPLICITLY linked if any, or just an empty collection with a warning.

            // Re-evaluating: Most Stripe users want to see the CHARGES that were paid out.
            // If it's a manual payout, the charges were "available" and then moved.

            $filteredData = [];
            foreach ($balanceTransactions->autoPagingIterator() as $bt) {
                $sourceId = is_string($bt->source) ? $bt->source : ($bt->source->id ?? null);
                if ($sourceId === $stripePayout->id) {
                    $filteredData[] = $bt;
                }
            }

            $balanceTransactions = new \Stripe\Collection();
            $balanceTransactions->data = $filteredData;
        }

        $totalFee = 0;
        $balanceTransactionsList = [];

        // Use a single pass to collect data from Stripe to avoid multiple auto-paging loops
        // and limit the number of entries we process per payout to avoid timeouts
        $maxEntriesPerPayout = 200;
        $count = 0;

        foreach ($balanceTransactions->autoPagingIterator() as $bt) {
            $balanceTransactionsList[] = $bt;
            $count++;
            if ($count >= $maxEntriesPerPayout) {
                Log::info("Reached limit of {$maxEntriesPerPayout} balance transactions for payout {$stripePayout->id}. Skipping remaining.");
                break;
            }
        }

        // Collect all source IDs to eager load PaymentInfo
        $sourceIds = [];
        foreach ($balanceTransactionsList as $bt) {
            if ($bt->type === 'charge' || $bt->type === 'payment') {
                $btSourceId = is_string($bt->source) ? $bt->source : ($bt->source->id ?? null);
                if ($btSourceId) {
                    $sourceIds[] = $btSourceId;
                }
            }
        }

        // Eager load PaymentInfos by both possible columns
        $paymentInfos = [];
        if (!empty($sourceIds)) {
            $paymentInfos = PaymentInfo::whereIn('stripe_charge_id', $sourceIds)
                ->orWhereIn('processor_confirm', $sourceIds)
                ->get()
                ->keyBy(function($item) {
                    // We'll index by both to make lookup easier
                    return $item->stripe_charge_id ?: $item->processor_confirm;
                });
        }

        foreach ($balanceTransactionsList as $bt) {
            $orderId = null;
            $paymentInfo = null;

            if (($bt->type === 'charge' || $bt->type === 'payment') && !empty($bt->source)) {
                // Try to find the order associated with this charge in our pre-fetched list
                $btSourceId = is_string($bt->source) ? $bt->source : ($bt->source->id ?? null);
                if ($btSourceId) {
                    $paymentInfo = $paymentInfos->get($btSourceId);

                    // If not found in our pre-fetched list (e.g. it's stored by PI ID and we didn't match),
                    // we might still need to do the heavy lookup, but hopefully less often now.
                    if (!$paymentInfo) {
                        $paymentInfo = PaymentInfo::where('processor_confirm', $btSourceId)
                            ->orWhere('stripe_charge_id', $btSourceId)
                            ->first();
                    }

                    // If not found, and it's a charge, it might be stored by PaymentIntent ID
                    if (!$paymentInfo && str_starts_with($btSourceId, 'ch_')) {
                        try {
                            $charge = Charge::retrieve($btSourceId);
                            if ($charge->payment_intent) {
                                $paymentInfo = PaymentInfo::where('processor_confirm', $charge->payment_intent)->first();
                                if ($paymentInfo && !$paymentInfo->stripe_charge_id) {
                                    $paymentInfo->update(['stripe_charge_id' => $btSourceId]);
                                }
                            }
                        } catch (\Exception $e) {
                            Log::warning("Failed to retrieve charge {$btSourceId} for correlation: " . $e->getMessage());
                        }
                    }

                    if ($paymentInfo) {
                        $orderId = $paymentInfo->dtforder_id;

                        // If we found it via processor_confirm but stripe_charge_id is empty, let's fill it
                        if (!$paymentInfo->stripe_charge_id && str_starts_with($btSourceId, 'ch_')) {
                            $paymentInfo->update(['stripe_charge_id' => $btSourceId]);
                        }
                    } else {
                        Log::warning("Stripe Payout Sync: Could not correlate balance transaction {$bt->id} (source: {$btSourceId}) to any order using strong IDs.");
                    }
                }
            }

            $entryData = [
                'type' => $bt->type,
                'gross' => $bt->amount / 100,
                'fee' => $bt->fee / 100,
                'net' => $bt->net / 100,
                'dtforder_id' => $orderId,
            ];

            if ($paymentInfo && $paymentInfo->qbo_fee_expense_id) {
                $entryData['qbo_expense_id'] = $paymentInfo->qbo_fee_expense_id;
            }

            // Capture business name for the entry if possible
            if ($paymentInfo && $paymentInfo->dtfOrder && $paymentInfo->dtfOrder->business) {
                $entryData['notes'] = $paymentInfo->dtfOrder->business->business_name;
            } elseif ($paymentInfo && str_contains($paymentInfo->notes ?? '', 'QBO Invoice Payment')) {
                $entryData['notes'] = $paymentInfo->notes;
            }

            // If it's a refund, try to capture the refund ID if possible
            // Note: Balance Transaction source for a refund is usually the Refund ID (re_...)
            if ($bt->type === 'refund' && str_starts_with($bt->source, 're_')) {
                // We could add a stripe_refund_id column if needed,
                // but stripe_transaction_id already stores the BT ID.
            }

            StripePayoutEntry::updateOrCreate(
                [
                    'stripe_payout_id' => $payout->id,
                    'stripe_transaction_id' => $bt->id
                ],
                $entryData
            );
            $totalFee += ($bt->fee / 100);
        }

        $payout->update([
            'fee' => $totalFee,
            'net' => $payout->amount - $totalFee
        ]);

        return $payout;
    }
}
