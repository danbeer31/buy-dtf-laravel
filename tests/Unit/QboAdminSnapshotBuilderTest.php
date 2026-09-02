<?php

namespace Tests\Unit;

use App\Services\QboAdminSnapshotBuilder;
use Carbon\CarbonImmutable;
use PHPUnit\Framework\TestCase;

class QboAdminSnapshotBuilderTest extends TestCase
{
    public function test_it_sums_open_invoices_and_groups_recent_invoices(): void
    {
        $invoices = [];
        for ($index = 1; $index <= 22; $index++) {
            $invoices[] = [
                'Id' => (string) $index,
                'CustomerRef' => ['value' => 'customer-1'],
            ];
        }
        $invoices[] = [
            'Id' => 'other',
            'CustomerRef' => ['value' => 'customer-2'],
        ];

        $snapshots = (new QboAdminSnapshotBuilder)->build(
            [
                ['id' => 10, 'qbo_customer_id' => 'customer-1'],
                ['id' => 20, 'qbo_customer_id' => 'customer-with-no-open-invoices'],
                ['id' => 30, 'qbo_customer_id' => ''],
            ],
            [
                [
                    'Id' => 'open-1',
                    'CustomerRef' => ['value' => 'customer-1'],
                    'PayableBalance' => 125.75,
                ],
                [
                    'Id' => 'open-2',
                    'CustomerRef' => ['value' => 'customer-1'],
                    'Balance' => 20,
                ],
            ],
            $invoices,
            CarbonImmutable::parse('2026-09-02T01:00:00Z'),
        );

        $this->assertSame([10, 20], array_keys($snapshots));
        $this->assertSame(145.75, $snapshots[10]['balance']);
        $this->assertSame('open_invoices', $snapshots[10]['balance_basis']);
        $this->assertSame(2, $snapshots[10]['open_invoice_count']);
        $this->assertCount(20, $snapshots[10]['invoices']);
        $this->assertSame('1', $snapshots[10]['invoices'][0]['Id']);
        $this->assertSame(0.0, $snapshots[20]['balance']);
        $this->assertSame('2026-09-02T01:00:00+00:00', $snapshots[10]['refreshed_at']);
    }
}
