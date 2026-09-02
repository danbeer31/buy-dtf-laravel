<?php

namespace Tests\Unit;

use App\Services\QboAdminReadCircuitBreaker;
use Illuminate\Support\Facades\Cache;
use RuntimeException;
use Tests\TestCase;

class QboAdminReadCircuitBreakerTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
        config(['services.qbo.admin_circuit_seconds' => 300]);
    }

    public function test_it_opens_with_retry_details_and_can_close(): void
    {
        $breaker = new QboAdminReadCircuitBreaker;

        $breaker->open(new RuntimeException('QBO timed out'));

        $this->assertTrue($breaker->isOpen());
        $this->assertSame('QBO timed out', $breaker->state()['reason']);
        $this->assertNotEmpty($breaker->state()['retry_at']);

        $breaker->close();

        $this->assertFalse($breaker->isOpen());
        $this->assertNull($breaker->state());
    }
}
