<?php

namespace App\Services;

use Illuminate\Support\Facades\Cache;
use Throwable;

class QboAdminReadCircuitBreaker
{
    private const CACHE_KEY = 'qbo:admin-read-circuit';

    public function isOpen(): bool
    {
        return Cache::has(self::CACHE_KEY);
    }

    public function state(): ?array
    {
        $state = Cache::get(self::CACHE_KEY);

        return is_array($state) ? $state : null;
    }

    public function open(Throwable $exception): void
    {
        $seconds = max(1, (int) config('services.qbo.admin_circuit_seconds', 300));
        $now = now();

        Cache::put(self::CACHE_KEY, [
            'opened_at' => $now->toIso8601String(),
            'retry_at' => $now->copy()->addSeconds($seconds)->toIso8601String(),
            'reason' => mb_substr($exception->getMessage(), 0, 500),
        ], $seconds);
    }

    public function close(): void
    {
        Cache::forget(self::CACHE_KEY);
    }
}
