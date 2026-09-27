<?php

namespace Tests\Feature\Api;

use App\Models\IncomingOrderJob;
use App\Services\IncomingOrders\IncomingOrderIdempotency;
use Tests\TestCase;

class IncomingOrderIdempotencyTest extends TestCase
{
    public function test_active_owner_returns_processing_without_incrementing_attempts(): void
    {
        $service = app(IncomingOrderIdempotency::class);
        $first = $service->claim('shopnltees', 'Dispatch-Key', str_repeat('a', 64), $this->initial());
        $second = $service->claim('shopnltees', 'Dispatch-Key', str_repeat('a', 64), $this->initial());

        $this->assertSame('owned', $first->outcome);
        $this->assertSame('processing', $second->outcome);
        $this->assertGreaterThanOrEqual(1, $second->retryAfter);
        $this->assertSame(1, (int) $second->job->attempt_count);
        $this->assertDatabaseCount('incoming_order_jobs', 1, 'fuelmysql');
    }

    public function test_expired_owner_is_reclaimed_with_a_new_owner_and_incremented_attempt(): void
    {
        $service = app(IncomingOrderIdempotency::class);
        $first = $service->claim('shopnltees', 'stale-key', str_repeat('b', 64), $this->initial());
        IncomingOrderJob::whereKey($first->job->id)->update(['lease_expires_at' => now()->subSecond()]);

        $reclaimed = $service->claim('shopnltees', 'stale-key', str_repeat('b', 64), $this->initial());

        $this->assertSame('owned', $reclaimed->outcome);
        $this->assertSame($first->owner, $reclaimed->expiredOwner);
        $this->assertNotSame($first->owner, $reclaimed->owner);
        $this->assertSame(2, (int) $reclaimed->job->attempt_count);
    }

    public function test_retryable_failure_can_be_reclaimed_but_conflicting_payload_cannot(): void
    {
        $service = app(IncomingOrderIdempotency::class);
        $first = $service->claim('shopnltees', 'retry-key', str_repeat('c', 64), $this->initial());
        $service->fail((int) $first->job->id, (string) $first->owner, 'source_timeout', true);

        $conflict = $service->claim('shopnltees', 'retry-key', str_repeat('d', 64), $this->initial());
        $retry = $service->claim('shopnltees', 'retry-key', str_repeat('c', 64), $this->initial());

        $this->assertSame('conflict', $conflict->outcome);
        $this->assertSame('owned', $retry->outcome);
        $this->assertSame(2, (int) $retry->job->attempt_count);
    }

    public function test_attempt_limit_becomes_a_stable_permanent_failure(): void
    {
        config()->set('incoming_order.max_attempts', 1);
        $service = app(IncomingOrderIdempotency::class);
        $first = $service->claim('shopnltees', 'limit-key', str_repeat('e', 64), $this->initial());
        IncomingOrderJob::whereKey($first->job->id)->update(['lease_expires_at' => now()->subSecond()]);

        $limited = $service->claim('shopnltees', 'limit-key', str_repeat('e', 64), $this->initial());

        $this->assertSame('attempts_exhausted', $limited->outcome);
        $this->assertSame('permanent_failure', $limited->job->state);
        $this->assertSame('idempotency_attempts_exhausted', $limited->job->last_error_code);
    }

    public function test_keys_are_case_sensitive_with_the_reviewed_binary_collation(): void
    {
        $service = app(IncomingOrderIdempotency::class);
        $upper = $service->claim('shopnltees', 'Case-Key', str_repeat('f', 64), $this->initial());
        $lower = $service->claim('shopnltees', 'case-key', str_repeat('f', 64), $this->initial());

        $this->assertSame('owned', $upper->outcome);
        $this->assertSame('owned', $lower->outcome);
        $this->assertNotSame($upper->job->id, $lower->job->id);
        $this->assertDatabaseCount('incoming_order_jobs', 2, 'fuelmysql');
    }

    /** @return array<string, mixed> */
    private function initial(): array
    {
        return [
            'expected_art_sha256' => str_repeat('0', 64),
            'art_width_in' => '1.0000',
            'art_height_in' => '1.0000',
        ];
    }
}
