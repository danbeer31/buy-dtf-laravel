<?php

namespace App\Services;

use App\Models\Business;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Log;
use RuntimeException;
use Throwable;

class QboAdminSnapshotRefresher
{
    public function __construct(
        private readonly QboService $qbo,
        private readonly QboAdminSnapshotStore $store,
        private readonly QboAdminSnapshotBuilder $builder,
        private readonly QboAdminReadCircuitBreaker $circuitBreaker,
    ) {}

    public function refresh(): array
    {
        $this->store->markAttempt();

        if ($this->circuitBreaker->isOpen()) {
            $state = $this->circuitBreaker->state();
            $this->store->markDeferred($state);

            return [
                'status' => 'deferred',
                'retry_at' => $state['retry_at'] ?? null,
            ];
        }

        $businesses = $this->linkedBusinesses();

        if ($businesses->isEmpty()) {
            $this->circuitBreaker->close();
            $this->store->markSuccess(0, 0, 0);

            return [
                'status' => 'ok',
                'linked_businesses' => 0,
                'updated_businesses' => 0,
                'invoice_count' => 0,
            ];
        }

        try {
            $balances = $this->qbo->getAdminCustomerBalances();
            if ($balances === []) {
                throw new RuntimeException('QBO returned no customers for linked admin businesses.');
            }

            $invoices = $this->qbo->getAdminRecentInvoices();
            $snapshots = $this->builder->build($businesses, $balances, $invoices, now());
            if ($snapshots === []) {
                throw new RuntimeException('QBO returned no matching customers for linked admin businesses.');
            }

            foreach ($snapshots as $businessId => $snapshot) {
                $this->store->put((int) $businessId, $snapshot);
            }

            $this->circuitBreaker->close();
            $this->store->markSuccess($businesses->count(), count($snapshots), count($invoices));

            Log::info('QBO admin snapshots refreshed', [
                'linked_businesses' => $businesses->count(),
                'updated_businesses' => count($snapshots),
                'invoice_count' => count($invoices),
            ]);

            return [
                'status' => 'ok',
                'linked_businesses' => $businesses->count(),
                'updated_businesses' => count($snapshots),
                'invoice_count' => count($invoices),
            ];
        } catch (Throwable $exception) {
            $this->circuitBreaker->open($exception);
            $this->store->markFailure($exception, $this->circuitBreaker->state());

            Log::warning('QBO admin snapshot refresh failed', [
                'exception' => get_class($exception),
                'error' => $exception->getMessage(),
            ]);

            throw $exception;
        }
    }

    protected function linkedBusinesses(): Collection
    {
        return Business::query()
            ->select(['id', 'qbo_customer_id'])
            ->whereNotNull('qbo_customer_id')
            ->where('qbo_customer_id', '!=', '')
            ->get();
    }
}
