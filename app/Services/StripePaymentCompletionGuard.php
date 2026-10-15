<?php

namespace App\Services;

use App\Models\PaymentInfo;
use Illuminate\Support\Facades\DB;
use RuntimeException;

/**
 * A durable, per-PaymentIntent claim. We never replay an uncertain QBO write
 * just because a browser revisits a Stripe return URL.
 */
class StripePaymentCompletionGuard
{
    private function connection()
    {
        return DB::connection((new PaymentInfo())->getConnectionName());
    }

    public function claim(string $paymentIntentId, string $flow): bool
    {
        return $this->connection()->transaction(function () use ($paymentIntentId, $flow) {
            $inserted = $this->connection()->table('stripe_payment_completions')->insertOrIgnore([
                'payment_intent_id' => $paymentIntentId,
                'flow' => $flow,
                'state' => 'claimed',
                'created_at' => now(),
                'updated_at' => now(),
            ]);

            if (!$inserted) {
                return false;
            }

            // Protect payments processed before this guard was deployed.
            $existing = PaymentInfo::where('processor', 'Stripe')
                ->where('processor_confirm', $paymentIntentId)
                ->orderBy('id')
                ->first();
            if ($existing) {
                $this->connection()->table('stripe_payment_completions')
                    ->where('payment_intent_id', $paymentIntentId)
                    ->update([
                        'state' => 'preexisting',
                        'payment_info_id' => $existing->id,
                        'updated_at' => now(),
                    ]);
                return false;
            }

            return true;
        });
    }

    public function paymentInfoCreated(string $paymentIntentId, int $paymentInfoId): void
    {
        $this->updateCompletion($paymentIntentId, [
            'payment_info_id' => $paymentInfoId,
            'state' => 'processing',
        ]);
    }

    public function state(string $paymentIntentId): ?string
    {
        return $this->connection()->table('stripe_payment_completions')
            ->where('payment_intent_id', $paymentIntentId)
            ->value('state');
    }

    public function startStep(string $paymentIntentId, string $stepKey): void
    {
        $inserted = $this->connection()->table('stripe_payment_completion_steps')->insertOrIgnore([
            'payment_intent_id' => $paymentIntentId,
            'step_key' => $stepKey,
            'state' => 'started',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        if (!$inserted) {
            throw new RuntimeException("QBO step {$stepKey} has already been attempted for {$paymentIntentId}; manual review required.");
        }
    }

    public function succeedStep(string $paymentIntentId, string $stepKey, ?string $externalId): void
    {
        $this->updateStep($paymentIntentId, $stepKey, [
            'state' => 'succeeded',
            'external_id' => $externalId,
        ]);
    }

    public function uncertainStep(string $paymentIntentId, string $stepKey, \Throwable $error): void
    {
        $this->updateStep($paymentIntentId, $stepKey, [
            'state' => 'outcome_unknown',
            'error' => mb_substr($error->getMessage(), 0, 2000),
        ]);
    }

    public function finish(string $paymentIntentId, bool $needsReview, ?string $reason = null): void
    {
        $this->updateCompletion($paymentIntentId, [
            'state' => $needsReview ? 'needs_review' : 'complete',
            'last_error' => $reason ? mb_substr($reason, 0, 2000) : null,
        ]);
    }

    private function updateCompletion(string $paymentIntentId, array $attributes): void
    {
        $this->connection()->table('stripe_payment_completions')
            ->where('payment_intent_id', $paymentIntentId)
            ->update($attributes + ['updated_at' => now()]);
    }

    private function updateStep(string $paymentIntentId, string $stepKey, array $attributes): void
    {
        $this->connection()->table('stripe_payment_completion_steps')
            ->where('payment_intent_id', $paymentIntentId)
            ->where('step_key', $stepKey)
            ->update($attributes + ['updated_at' => now()]);
    }
}
