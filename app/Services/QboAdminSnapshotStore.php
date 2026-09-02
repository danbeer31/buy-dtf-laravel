<?php

namespace App\Services;

use Illuminate\Support\Facades\Cache;
use Throwable;

class QboAdminSnapshotStore
{
    private const SNAPSHOT_PREFIX = 'qbo:admin-snapshot:';

    private const STATUS_KEY = 'qbo:admin-refresh-status';

    public function get(int $businessId): ?array
    {
        $snapshot = Cache::get(self::SNAPSHOT_PREFIX.$businessId);
        if (is_array($snapshot)) {
            return $snapshot;
        }

        return $this->legacySnapshot($businessId);
    }

    public function put(int $businessId, array $snapshot): void
    {
        Cache::forever(self::SNAPSHOT_PREFIX.$businessId, $snapshot);
    }

    public function status(): array
    {
        $status = Cache::get(self::STATUS_KEY, []);

        return array_merge([
            'state' => 'never',
            'last_attempt_at' => null,
            'last_success_at' => null,
            'last_error_at' => null,
            'last_error' => null,
            'circuit_retry_at' => null,
            'linked_businesses' => 0,
            'updated_businesses' => 0,
            'invoice_count' => 0,
        ], is_array($status) ? $status : []);
    }

    public function markAttempt(): void
    {
        $this->updateStatus([
            'last_attempt_at' => now()->toIso8601String(),
        ]);
    }

    public function markSuccess(int $linkedBusinesses, int $updatedBusinesses, int $invoiceCount): void
    {
        $now = now()->toIso8601String();

        $this->updateStatus([
            'state' => 'ok',
            'last_attempt_at' => $now,
            'last_success_at' => $now,
            'last_error_at' => null,
            'last_error' => null,
            'circuit_retry_at' => null,
            'linked_businesses' => $linkedBusinesses,
            'updated_businesses' => $updatedBusinesses,
            'invoice_count' => $invoiceCount,
        ]);
    }

    public function markFailure(Throwable $exception, ?array $circuitState): void
    {
        $this->updateStatus([
            'state' => 'error',
            'last_error_at' => now()->toIso8601String(),
            'last_error' => mb_substr($exception->getMessage(), 0, 500),
            'circuit_retry_at' => $circuitState['retry_at'] ?? null,
        ]);
    }

    public function markDeferred(?array $circuitState): void
    {
        $this->updateStatus([
            'state' => 'deferred',
            'last_attempt_at' => now()->toIso8601String(),
            'circuit_retry_at' => $circuitState['retry_at'] ?? null,
        ]);
    }

    private function updateStatus(array $changes): void
    {
        Cache::forever(self::STATUS_KEY, array_merge($this->status(), $changes));
    }

    private function legacySnapshot(int $businessId): ?array
    {
        $legacyData = Cache::get('qbo_data_'.$businessId);
        $legacyInvoices = Cache::get('admin_qbo_invoice_history_'.$businessId);

        $hasLegacyData = is_array($legacyData);
        $hasLegacyInvoices = is_array($legacyInvoices);
        if (! $hasLegacyData && ! $hasLegacyInvoices) {
            return null;
        }

        return [
            'business_id' => $businessId,
            'qbo_customer_id' => null,
            'balance' => $hasLegacyData && array_key_exists('balance', $legacyData)
                ? (float) $legacyData['balance']
                : null,
            'invoices' => $hasLegacyData && isset($legacyData['invoice_history'])
                ? (array) $legacyData['invoice_history']
                : (array) ($legacyInvoices ?? []),
            'refreshed_at' => null,
            'source' => 'legacy_cache',
        ];
    }
}
