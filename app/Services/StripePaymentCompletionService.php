<?php

namespace App\Services;

use App\Models\DtfOrder;
use App\Models\PaymentInfo;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;
use Stripe\BalanceTransaction;
use Stripe\PaymentIntent;

class StripePaymentCompletionService
{
    public function __construct(
        private readonly QboService $qbo,
        private readonly StripePaymentCompletionGuard $guard,
    ) {}

    public function completeOrder(PaymentIntent $intent, DtfOrder $order): void
    {
        if (!$this->guard->claim($intent->id, 'order')) {
            Log::info('Stripe order completion already claimed', ['pi' => $intent->id, 'order_id' => $order->id]);
            return;
        }

        if ((int) $order->status === 2) {
            $this->guard->finish($intent->id, true, 'Order is already paid but no matching Stripe payment row exists.');
            Log::error('Paid order missing matching Stripe payment row', ['pi' => $intent->id, 'order_id' => $order->id]);
            return;
        }

        $needsReview = false;
        $reasons = [];

        try {
            [$chargeId, $fee] = $this->chargeAndFee($intent);
            $paymentInfo = PaymentInfo::create([
                'dtforder_id' => $order->id,
                'business_id' => $order->business_id,
                'processor' => 'Stripe',
                'processor_confirm' => $intent->id,
                'stripe_charge_id' => $chargeId,
                'amount' => $intent->amount_received / 100,
                'stripe_fee' => $fee,
                'notes' => 'Payment received via Stripe.',
                'status' => 'complete',
            ]);
            $this->guard->paymentInfoCreated($intent->id, $paymentInfo->id);

            $order->finalizeMetrics();
            $order->update(['status' => 2]);

            try {
                if (!$order->qbo_invoice_id) {
                    $step = 'invoice';
                    $this->guard->startStep($intent->id, $step);
                    try {
                        $invoice = $this->qbo->createInvoice($order->business, $order);
                        $this->guard->succeedStep($intent->id, $step, (string) ($invoice['Id'] ?? $order->fresh()->qbo_invoice_id));
                    } catch (\Throwable $e) {
                        $this->guard->uncertainStep($intent->id, $step, $e);
                        throw $e;
                    }
                }

                $step = 'payment:' . $order->qbo_invoice_id;
                $this->guard->startStep($intent->id, $step);
                try {
                    $payment = $this->qbo->recordPayment($order, $paymentInfo->amount, $intent->id, $fee);
                    $paymentId = (string) ($payment['Id'] ?? '');
                    if ($paymentId === '') {
                        throw new \RuntimeException('QBO payment response has no ID.');
                    }
                    $paymentInfo->update(['qbo_payment_id' => $paymentId]);
                    $this->guard->succeedStep($intent->id, $step, $paymentId);
                } catch (\Throwable $e) {
                    $this->guard->uncertainStep($intent->id, $step, $e);
                    throw $e;
                }
            } catch (\Throwable $e) {
                $needsReview = true;
                $reasons[] = 'QBO invoice/payment: ' . $e->getMessage();
                Log::error('Stripe order QBO payment needs review', ['pi' => $intent->id, 'order_id' => $order->id, 'error' => $e->getMessage()]);
            }

            if ($fee > 0) {
                $this->recordFee($intent->id, $chargeId, $fee, $paymentInfo, $needsReview, $reasons);
            } else {
                $needsReview = true;
                $reasons[] = 'Stripe fee unavailable after bounded lookup.';
            }
        } catch (\Throwable $e) {
            $needsReview = true;
            $reasons[] = 'Local completion: ' . $e->getMessage();
            Log::error('Stripe order local completion needs review', ['pi' => $intent->id, 'order_id' => $order->id, 'error' => $e->getMessage()]);
        } finally {
            $this->guard->finish($intent->id, $needsReview, implode(' | ', $reasons));
        }
    }

    /** Returns true only if every QBO write was confirmed. */
    public function completeQboInvoices(PaymentIntent $intent): bool
    {
        if (($intent->metadata->payment_type ?? null) !== 'qbo_invoice_payment') {
            throw new \InvalidArgumentException('Stripe PaymentIntent is not a QuickBooks invoice payment.');
        }

        if (!$this->guard->claim($intent->id, 'qbo_invoices')) {
            Log::info('Stripe QBO invoice completion already claimed', ['pi' => $intent->id]);
            return $this->guard->state($intent->id) === 'complete';
        }

        $needsReview = false;
        $reasons = [];
        try {
            [$chargeId, $fee] = $this->chargeAndFee($intent);
            $metadata = $intent->metadata;
            $businessId = $metadata->business_id ?? null;
            $invoiceIds = array_values(array_unique(array_filter(explode(',', (string) ($metadata->qbo_invoice_ids ?? '')))));
            parse_str((string) ($metadata->qbo_invoice_amounts ?? ''), $invoiceAmounts);

            $paymentInfo = PaymentInfo::create([
                'dtforder_id' => 0,
                'business_id' => $businessId,
                'processor' => 'Stripe',
                'processor_confirm' => $intent->id,
                'stripe_charge_id' => $chargeId,
                'amount' => $intent->amount_received / 100,
                'stripe_fee' => $fee,
                'qbo_invoice_numbers' => $metadata->qbo_invoice_numbers ?? $metadata->qbo_invoice_ids ?? null,
                'notes' => 'QBO Invoice Payment for Invoices: ' . ($metadata->qbo_invoice_numbers ?? $metadata->qbo_invoice_ids ?? 'N/A'),
                'status' => 'complete',
            ]);
            $this->guard->paymentInfoCreated($intent->id, $paymentInfo->id);

            $expectedCents = array_sum(array_map(fn ($amount) => (int) round((float) $amount * 100), $invoiceAmounts));
            if (($metadata->payment_type ?? null) !== 'qbo_invoice_payment' || !$businessId || !$invoiceIds
                || count($invoiceIds) !== count($invoiceAmounts)
                || $expectedCents !== (int) $intent->amount_received) {
                $needsReview = true;
                $reasons[] = 'Stripe invoice metadata is missing or does not match the charge amount.';
            } else {
                foreach ($invoiceIds as $invoiceId) {
                    $step = 'payment:' . $invoiceId;
                    try {
                        $invoiceResult = $this->qbo->request('GET', 'invoice/' . rawurlencode($invoiceId));
                        if (!isset($invoiceResult['Invoice']['CustomerRef']['value']) || isset($invoiceResult['error'])) {
                            throw new \RuntimeException("Could not read QBO invoice {$invoiceId}.");
                        }
                        $invoice = $invoiceResult['Invoice'];
                        $expectedAmount = round((float) ($invoiceAmounts[$invoiceId] ?? 0), 2);
                        $payableAmount = round((float) $this->qbo->getInvoicePayableBalance($invoice), 2);
                        if ($expectedAmount <= 0 || abs($payableAmount - $expectedAmount) > 0.01) {
                            throw new \RuntimeException("QBO invoice {$invoiceId} balance changed; manual allocation required.");
                        }

                        $this->guard->startStep($intent->id, $step);
                        try {
                            $payment = $this->qbo->recordGenericPayment(
                                $invoice['CustomerRef']['value'], $invoiceId, $expectedAmount, $intent->id
                            );
                            $paymentId = (string) ($payment['Id'] ?? '');
                            if ($paymentId === '') {
                                throw new \RuntimeException('QBO payment response has no ID.');
                            }
                            $this->guard->succeedStep($intent->id, $step, $paymentId);
                        } catch (\Throwable $e) {
                            $this->guard->uncertainStep($intent->id, $step, $e);
                            throw $e;
                        }
                    } catch (\Throwable $e) {
                        $needsReview = true;
                        $reasons[] = "Invoice {$invoiceId}: " . $e->getMessage();
                        Log::error('Stripe QBO invoice allocation needs review', ['pi' => $intent->id, 'invoice_id' => $invoiceId, 'error' => $e->getMessage()]);
                    }
                }
            }

            if ($fee > 0) {
                $this->recordFee($intent->id, $chargeId, $fee, $paymentInfo, $needsReview, $reasons);
            } else {
                $needsReview = true;
                $reasons[] = 'Stripe fee unavailable after bounded lookup.';
            }
            if ($businessId) {
                Cache::forget('qbo_data_' . $businessId);
            }
        } catch (\Throwable $e) {
            $needsReview = true;
            $reasons[] = 'Local completion: ' . $e->getMessage();
            Log::error('Stripe QBO invoice local completion needs review', ['pi' => $intent->id, 'error' => $e->getMessage()]);
        } finally {
            $this->guard->finish($intent->id, $needsReview, implode(' | ', $reasons));
        }

        return !$needsReview;
    }

    private function recordFee(string $intentId, ?string $chargeId, float $fee, PaymentInfo $paymentInfo, bool &$needsReview, array &$reasons): void
    {
        $step = 'fee';
        try {
            $this->guard->startStep($intentId, $step);
            $feeEntry = (object) [
                'fee' => $fee,
                'stripe_transaction_id' => $chargeId ?: $intentId,
                'qbo_expense_id' => $paymentInfo->qbo_fee_expense_id,
                'update' => function (array $data) use ($paymentInfo): void {
                    $paymentInfo->update(['qbo_fee_expense_id' => $data['qbo_expense_id']]);
                },
            ];
            try {
                $expense = $this->qbo->recordStripeFee($feeEntry);
                $expenseId = (string) ($expense['Id'] ?? $paymentInfo->fresh()->qbo_fee_expense_id ?? '');
                if ($expenseId === '') {
                    throw new \RuntimeException('QBO fee expense response has no ID.');
                }
                $this->guard->succeedStep($intentId, $step, $expenseId);
            } catch (\Throwable $e) {
                $this->guard->uncertainStep($intentId, $step, $e);
                throw $e;
            }
        } catch (\Throwable $e) {
            $needsReview = true;
            $reasons[] = 'QBO fee: ' . $e->getMessage();
            Log::error('Stripe fee needs review', ['pi' => $intentId, 'error' => $e->getMessage()]);
        }
    }

    /** Always terminates, even when Stripe responds without a balance transaction or fee. */
    private function chargeAndFee(PaymentIntent $intent): array
    {
        $charge = $intent->latest_charge ?? null;
        $chargeId = is_string($charge) ? $charge : ($charge->id ?? null);
        for ($attempt = 0; $attempt < 5; $attempt++) {
            try {
                if ($attempt > 0) {
                    $refreshed = PaymentIntent::retrieve([
                        'id' => $intent->id,
                        'expand' => ['latest_charge.balance_transaction'],
                    ]);
                    $charge = $refreshed->latest_charge ?? null;
                    $chargeId = is_string($charge) ? $charge : ($charge->id ?? $chargeId);
                }
                if (!is_string($charge) && isset($charge->balance_transaction->fee)) {
                    return [$chargeId, $charge->balance_transaction->fee / 100];
                }
                $balanceTransaction = is_string($charge->balance_transaction ?? null)
                    ? $charge->balance_transaction : ($charge->balance_transaction->id ?? null);
                if ($balanceTransaction) {
                    $details = BalanceTransaction::retrieve($balanceTransaction);
                    if (isset($details->fee)) {
                        return [$chargeId, $details->fee / 100];
                    }
                }
            } catch (\Throwable $e) {
                Log::warning('Stripe fee lookup failed', ['pi' => $intent->id, 'attempt' => $attempt + 1, 'error' => $e->getMessage()]);
            }
            if ($attempt < 4) {
                sleep(1);
            }
        }

        return [$chargeId, 0.0];
    }
}
