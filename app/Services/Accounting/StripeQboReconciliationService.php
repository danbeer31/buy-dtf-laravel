<?php

namespace App\Services\Accounting;

use App\Models\AccountingReconciliationCheck;
use App\Models\PaymentInfo;
use App\Models\Setting;
use App\Models\StripePayout;
use App\Models\StripePayoutEntry;
use App\Services\QboService;
use Carbon\Carbon;

class StripeQboReconciliationService
{
    public function __construct(
        protected QboService $qbo
    ) {
    }

    /**
     * Build a read-only reconciliation snapshot and optionally persist it.
     *
     * @param array{
     *   business_id?: int|null,
     *   as_of_date?: string|null,
     *   scope?: string,
     *   tolerance_cents?: int,
     *   persist?: bool
     * } $options
     */
    public function run(array $options = []): array
    {
        $businessId = isset($options['business_id']) ? (int) $options['business_id'] : null;
        $scope = (string) ($options['scope'] ?? ($options['as_of_date'] ? 'as_of' : 'current'));
        $toleranceCents = (int) ($options['tolerance_cents'] ?? 1);
        $persist = (bool) ($options['persist'] ?? true);
        $asOfDate = !empty($options['as_of_date']) ? Carbon::parse((string) $options['as_of_date']) : null;

        $result = [
            'business_id' => $businessId,
            'provider' => 'stripe',
            'scope' => $scope,
            'as_of_date' => $asOfDate ? $asOfDate->toDateString() : null,
            'currency' => 'USD',
            'expected_holding_amount_cents' => 0,
            'actual_holding_amount_cents' => 0,
            'difference_amount_cents' => 0,
            'tolerance_cents' => $toleranceCents,
            'status' => 'error',
            'notes' => null,
            'meta' => [],
            'ran_at' => now(),
        ];

        try {
            $components = $this->buildExpectedComponents($businessId, $asOfDate);
            $expectedCents = $components['expected_holding_amount_cents'];

            $holdingAccountId = Setting::get('qbo_stripe_clearing_id', Setting::get('qbo_deposit_account_id'));
            if (empty($holdingAccountId)) {
                throw new \RuntimeException('Missing qbo_stripe_clearing_id (or qbo_deposit_account_id) setting.');
            }

            $actualBalance = $this->qbo->getAccountBalance((string) $holdingAccountId);
            $actualCents = $this->toCents($actualBalance);

            $difference = $actualCents - $expectedCents;
            $status = abs($difference) <= $toleranceCents ? 'balanced' : 'mismatch';

            $result['expected_holding_amount_cents'] = $expectedCents;
            $result['actual_holding_amount_cents'] = $actualCents;
            $result['difference_amount_cents'] = $difference;
            $result['status'] = $status;
            $result['meta'] = array_merge($components['meta'], [
                'holding_account_id' => (string) $holdingAccountId,
                'actual_scope' => 'qbo_account_balance',
            ]);
        } catch (\Throwable $e) {
            $result['status'] = 'error';
            $result['notes'] = $e->getMessage();
            $result['meta'] = array_merge($result['meta'], [
                'exception_class' => get_class($e),
            ]);
        }

        if ($persist) {
            AccountingReconciliationCheck::create($result);
        }

        return $result;
    }

    /**
     * Expected holding formula (in cents):
     * stripe-complete sales in - stripe fees - refunds - adjustments - paid payout transfers.
     */
    protected function buildExpectedComponents(?int $businessId = null, ?Carbon $asOfDate = null): array
    {
        $salesQ = PaymentInfo::query()
            ->where('processor', 'Stripe')
            ->whereIn('status', ['complete', 'paid']);

        $feeQ = PaymentInfo::query()
            ->where('processor', 'Stripe')
            ->whereIn('status', ['complete', 'paid'])
            ->whereNotNull('stripe_fee')
            ->where('stripe_fee', '>', 0);

        $refundQ = StripePayoutEntry::query()
            ->where('type', 'refund');

        // Keep "adjustments" to true residual adjustment types only.
        // Exclude movement types already represented by other components:
        // - sales: charge/payment
        // - refunds: refund
        // - payout transfers: payout
        // - fees: stripe_fee/application_fee
        $adjustmentQ = StripePayoutEntry::query()
            ->whereNotIn('type', ['charge', 'payment', 'refund', 'payout', 'stripe_fee', 'application_fee']);

        // Only include payouts that have a confirmed QBO transfer link.
        // This prevents expected-holding drift when a payout is marked paid locally
        // but its transfer was never persisted (or was later disconnected).
        $transferQ = StripePayout::query()
            ->where('status', 'paid')
            ->whereNotNull('qbo_transfer_id');

        $unsyncedTransferQ = StripePayout::query()
            ->where('status', 'paid')
            ->whereNull('qbo_transfer_id');

        if ($businessId) {
            $salesQ->where('business_id', $businessId);
            $feeQ->where('business_id', $businessId);
            $refundQ->whereHas('dtfOrder', fn ($q) => $q->where('business_id', $businessId));
            $adjustmentQ->whereHas('dtfOrder', fn ($q) => $q->where('business_id', $businessId));
            // Transfers are account-level and not attributed per business with high fidelity.
        }

        if ($asOfDate) {
            $end = $asOfDate->copy()->endOfDay();

            $salesQ->where('created_at', '<=', $end->timestamp);
            $feeQ->where('created_at', '<=', $end->timestamp);
            $refundQ->where('created_at', '<=', $end);
            $adjustmentQ->where('created_at', '<=', $end);
            $transferQ->where('arrival_date', '<=', $end);
            $unsyncedTransferQ->where('arrival_date', '<=', $end);
        }

        $salesCents = $this->sumDecimalToCents($salesQ, 'amount');
        $feesCents = $this->sumDecimalToCents($feeQ, 'stripe_fee');
        $refundsCents = $this->sumAbsDecimalToCents($refundQ, 'gross');
        $adjustmentsCents = $this->sumAbsDecimalToCents($adjustmentQ, 'net');
        $transfersCents = $this->sumDecimalToCents($transferQ, 'amount');
        $unsyncedTransfersCents = $this->sumDecimalToCents($unsyncedTransferQ, 'amount');

        $expectedCents = $salesCents - $feesCents - $refundsCents - $adjustmentsCents - $transfersCents;

        return [
            'expected_holding_amount_cents' => $expectedCents,
            'meta' => [
                'components_cents' => [
                    'sales_receipts' => $salesCents,
                    'fees' => $feesCents,
                    'refunds' => $refundsCents,
                    'adjustments' => $adjustmentsCents,
                    'payout_transfers' => $transfersCents,
                ],
                'component_counts' => [
                    'sales_rows' => (clone $salesQ)->count(),
                    'fee_rows' => (clone $feeQ)->count(),
                    'refund_rows' => (clone $refundQ)->count(),
                    'adjustment_rows' => (clone $adjustmentQ)->count(),
                    'paid_payout_rows_synced' => (clone $transferQ)->count(),
                    'paid_payout_rows_unsynced' => (clone $unsyncedTransferQ)->count(),
                ],
                'unsynced_paid_payouts_cents' => $unsyncedTransfersCents,
                'filters' => [
                    'business_id' => $businessId,
                    'as_of_date' => $asOfDate ? $asOfDate->toDateString() : null,
                ],
            ],
        ];
    }

    protected function sumDecimalToCents($query, string $column): int
    {
        return $this->toCents((float) $query->sum($column));
    }

    protected function sumAbsDecimalToCents($query, string $column): int
    {
        return $this->toCents((float) abs((float) $query->sum($column)));
    }

    protected function toCents(float $amount): int
    {
        return (int) round($amount * 100);
    }
}
