<?php

namespace App\Services\IncomingOrders;

use App\Models\IncomingOrderJob;
use Carbon\CarbonImmutable;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class IncomingOrderIdempotency
{
    /**
     * @param  array<string, mixed>  $initial
     */
    public function claim(string $client, string $key, string $fingerprint, array $initial): IdempotencyClaim
    {
        try {
            return $this->claimInTransaction($client, $key, $fingerprint, $initial);
        } catch (QueryException $exception) {
            if (! $this->isUniqueViolation($exception)) {
                throw $exception;
            }

            // A concurrent insert won the key. Re-enter the locked state machine.
            return $this->claimInTransaction($client, $key, $fingerprint, $initial);
        }
    }

    public function heartbeat(int $jobId, string $owner): bool
    {
        $connection = $this->connection();
        $now = $this->databaseNow($connection);

        return IncomingOrderJob::query()
            ->whereKey($jobId)
            ->where('state', 'processing')
            ->where('lease_owner', $owner)
            ->update([
                'heartbeat_at' => $now,
                'lease_expires_at' => $now->addSeconds($this->leaseSeconds()),
                'updated_at' => $now,
            ]) === 1;
    }

    /**
     * @param  array<string, mixed>|null  $frozenResponse
     */
    public function fail(
        int $jobId,
        string $owner,
        string $reason,
        bool $retryable,
        ?array $frozenResponse = null,
    ): void {
        $connection = $this->connection();
        $now = $this->databaseNow($connection);
        IncomingOrderJob::query()
            ->whereKey($jobId)
            ->where('state', 'processing')
            ->where('lease_owner', $owner)
            ->update([
                'state' => $retryable ? 'retryable_failure' : 'permanent_failure',
                'lease_owner' => null,
                'lease_expires_at' => null,
                'heartbeat_at' => null,
                'last_error_code' => $reason,
                'response_payload' => $frozenResponse,
                'updated_at' => $now,
            ]);
    }

    public function cleanupOwnerTemporaryFiles(?string $owner): void
    {
        if (! is_string($owner)
            || ! preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/Di', $owner)) {
            return;
        }

        $base = storage_path('app/private/incoming-orders/tmp');
        $directory = $base.DIRECTORY_SEPARATOR.$owner;
        $baseReal = realpath($base);
        $directoryReal = realpath($directory);
        if ($baseReal === false || $directoryReal === false
            || ! str_starts_with($directoryReal, $baseReal.DIRECTORY_SEPARATOR)) {
            return;
        }

        foreach ((array) scandir($directoryReal) as $name) {
            if ($name === '.' || $name === '..') {
                continue;
            }
            $path = $directoryReal.DIRECTORY_SEPARATOR.$name;
            if (is_file($path)) {
                @unlink($path);
            }
        }
        @rmdir($directoryReal);
    }

    /**
     * @param  array<string, mixed>  $initial
     */
    private function claimInTransaction(string $client, string $key, string $fingerprint, array $initial): IdempotencyClaim
    {
        $connection = $this->connection();

        return DB::connection($connection)->transaction(function () use ($client, $key, $fingerprint, $initial, $connection): IdempotencyClaim {
            $now = $this->databaseNow($connection);
            $job = IncomingOrderJob::query()
                ->where('integration_client', $client)
                ->where('idempotency_key', $key)
                ->lockForUpdate()
                ->first();

            if ($job === null) {
                $owner = (string) Str::uuid();
                $job = IncomingOrderJob::query()->create(array_merge($initial, [
                    'integration_client' => $client,
                    'idempotency_key' => $key,
                    'request_fingerprint' => $fingerprint,
                    'state' => 'processing',
                    'lease_owner' => $owner,
                    'lease_expires_at' => $now->addSeconds($this->leaseSeconds()),
                    'heartbeat_at' => $now,
                    'attempt_count' => 1,
                    'last_attempt_at' => $now,
                    'created_at' => $now,
                    'updated_at' => $now,
                ]));

                return new IdempotencyClaim('owned', $job, $owner);
            }

            if (! hash_equals((string) $job->request_fingerprint, $fingerprint)) {
                return new IdempotencyClaim('conflict', $job);
            }

            if ($job->state === 'completed') {
                return new IdempotencyClaim('replay', $job);
            }

            if ($job->state === 'permanent_failure') {
                return new IdempotencyClaim('permanent_failure', $job);
            }

            $expiresAt = $job->lease_expires_at !== null
                ? CarbonImmutable::parse($job->lease_expires_at)->utc()
                : null;
            if ($job->state === 'processing' && $expiresAt !== null && $expiresAt->isAfter($now)) {
                $seconds = (int) max(1, min(15, $now->diffInSeconds($expiresAt, false)));

                return new IdempotencyClaim('processing', $job, retryAfter: $seconds);
            }

            if ((int) $job->attempt_count >= $this->maxAttempts()) {
                $job->forceFill([
                    'state' => 'permanent_failure',
                    'lease_owner' => null,
                    'lease_expires_at' => null,
                    'heartbeat_at' => null,
                    'last_error_code' => 'idempotency_attempts_exhausted',
                    'updated_at' => $now,
                ])->save();

                return new IdempotencyClaim('attempts_exhausted', $job->fresh());
            }

            $expiredOwner = $job->state === 'processing' ? $job->lease_owner : null;
            $owner = (string) Str::uuid();
            $job->forceFill([
                'state' => 'processing',
                'lease_owner' => $owner,
                'lease_expires_at' => $now->addSeconds($this->leaseSeconds()),
                'heartbeat_at' => $now,
                'attempt_count' => (int) $job->attempt_count + 1,
                'last_attempt_at' => $now,
                'last_error_code' => null,
                'updated_at' => $now,
            ])->save();

            return new IdempotencyClaim('owned', $job->fresh(), $owner, $expiredOwner);
        }, 3);
    }

    private function databaseNow(string $connection): CarbonImmutable
    {
        $database = DB::connection($connection);
        $sql = $database->getDriverName() === 'mysql'
            ? 'SELECT UTC_TIMESTAMP(6) AS current_time'
            : 'SELECT CURRENT_TIMESTAMP AS current_time';
        $row = $database->selectOne($sql);
        $value = is_object($row) ? ($row->current_time ?? null) : null;

        return CarbonImmutable::parse((string) $value, 'UTC')->utc();
    }

    private function connection(): string
    {
        $connection = config('database.fuel_connection');
        if (! is_string($connection) || $connection === '') {
            throw new \RuntimeException('Fuel connection is not configured.');
        }

        return $connection;
    }

    private function leaseSeconds(): int
    {
        return max(30, (int) config('incoming_order.lease_seconds', 90));
    }

    private function maxAttempts(): int
    {
        return max(1, (int) config('incoming_order.max_attempts', 10));
    }

    private function isUniqueViolation(QueryException $exception): bool
    {
        return in_array((string) ($exception->errorInfo[0] ?? $exception->getCode()), ['23000', '23505', '19'], true);
    }
}
