<?php

namespace Tests\Unit;

use App\Services\QboAdminSnapshotStore;
use Illuminate\Support\Facades\Cache;
use RuntimeException;
use Tests\TestCase;

class QboAdminSnapshotStoreTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
    }

    public function test_a_failure_preserves_the_last_successful_snapshot_and_timestamp(): void
    {
        $store = new QboAdminSnapshotStore;
        $snapshot = [
            'balance' => 42.50,
            'invoices' => [['Id' => 'invoice-1']],
            'refreshed_at' => '2026-09-02T01:00:00+00:00',
        ];

        $store->put(12, $snapshot);
        $store->markSuccess(1, 1, 1);
        $lastSuccessAt = $store->status()['last_success_at'];
        $store->markFailure(new RuntimeException('QBO unavailable'), [
            'retry_at' => '2026-09-02T01:05:00+00:00',
        ]);

        $this->assertSame($snapshot, $store->get(12));
        $this->assertSame($lastSuccessAt, $store->status()['last_success_at']);
        $this->assertSame('error', $store->status()['state']);
        $this->assertSame('QBO unavailable', $store->status()['last_error']);
    }

    public function test_it_can_read_the_emergency_legacy_cache_as_a_fallback(): void
    {
        Cache::put('qbo_data_7', [
            'balance' => 19.25,
            'invoice_history' => [['Id' => 'legacy-invoice']],
        ]);

        $snapshot = (new QboAdminSnapshotStore)->get(7);

        $this->assertSame(19.25, $snapshot['balance']);
        $this->assertSame('legacy-invoice', $snapshot['invoices'][0]['Id']);
        $this->assertSame('legacy_cache', $snapshot['source']);
    }
}
