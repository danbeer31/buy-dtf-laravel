<?php

namespace Tests\Unit;

use App\Services\QboAdminReadCircuitBreaker;
use App\Services\QboAdminSnapshotBuilder;
use App\Services\QboAdminSnapshotRefresher;
use App\Services\QboAdminSnapshotStore;
use App\Services\QboService;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;
use Mockery;
use RuntimeException;
use Tests\TestCase;

class QboAdminSnapshotRefresherTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        Cache::flush();
    }

    public function test_a_successful_refresh_stores_business_snapshots(): void
    {
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldReceive('getAdminOpenInvoices')->once()->andReturn([[
            'Id' => 'open-invoice-1',
            'CustomerRef' => ['value' => '101'],
            'PayableBalance' => 88.50,
        ]]);
        $qbo->shouldReceive('getAdminRecentInvoices')->once()->andReturn([[
            'Id' => 'invoice-1',
            'CustomerRef' => ['value' => '101'],
        ]]);
        $store = new QboAdminSnapshotStore;
        $refresher = $this->refresher($qbo, $store, collect([
            ['id' => 5, 'qbo_customer_id' => '101'],
        ]));

        $result = $refresher->refresh();

        $this->assertSame('ok', $result['status']);
        $this->assertSame(1, $result['open_invoice_count']);
        $this->assertSame(88.50, $store->get(5)['balance']);
        $this->assertSame('invoice-1', $store->get(5)['invoices'][0]['Id']);
        $this->assertSame('ok', $store->status()['state']);
    }

    public function test_an_outage_opens_the_circuit_and_preserves_stale_data(): void
    {
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldReceive('getAdminOpenInvoices')->once()->andThrow(new RuntimeException('QBO timed out'));
        $qbo->shouldNotReceive('getAdminRecentInvoices');
        $store = new QboAdminSnapshotStore;
        $staleSnapshot = [
            'balance' => 31.00,
            'invoices' => [],
            'refreshed_at' => '2026-09-02T01:00:00+00:00',
        ];
        $store->put(5, $staleSnapshot);
        $breaker = new QboAdminReadCircuitBreaker;
        $refresher = $this->refresher($qbo, $store, collect([
            ['id' => 5, 'qbo_customer_id' => '101'],
        ]), $breaker);

        try {
            $refresher->refresh();
            $this->fail('Expected the QBO timeout to be rethrown.');
        } catch (RuntimeException $exception) {
            $this->assertSame('QBO timed out', $exception->getMessage());
        }

        $this->assertTrue($breaker->isOpen());
        $this->assertSame($staleSnapshot, $store->get(5));
        $this->assertSame('error', $store->status()['state']);
    }

    public function test_an_open_circuit_skips_qbo_calls(): void
    {
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('getAdminOpenInvoices');
        $qbo->shouldNotReceive('getAdminRecentInvoices');
        $store = new QboAdminSnapshotStore;
        $breaker = new QboAdminReadCircuitBreaker;
        $breaker->open(new RuntimeException('QBO timed out'));
        $refresher = $this->refresher($qbo, $store, collect(), $breaker);

        $result = $refresher->refresh();

        $this->assertSame('deferred', $result['status']);
        $this->assertSame('deferred', $store->status()['state']);
    }

    private function refresher(
        QboService $qbo,
        QboAdminSnapshotStore $store,
        Collection $businesses,
        ?QboAdminReadCircuitBreaker $breaker = null,
    ): QboAdminSnapshotRefresher {
        return new class($qbo, $store, new QboAdminSnapshotBuilder, $breaker ?? new QboAdminReadCircuitBreaker, $businesses) extends QboAdminSnapshotRefresher
        {
            public function __construct(
                QboService $qbo,
                QboAdminSnapshotStore $store,
                QboAdminSnapshotBuilder $builder,
                QboAdminReadCircuitBreaker $breaker,
                private readonly Collection $businesses,
            ) {
                parent::__construct($qbo, $store, $builder, $breaker);
            }

            protected function linkedBusinesses(): Collection
            {
                return $this->businesses;
            }
        };
    }
}
