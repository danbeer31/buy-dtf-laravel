<?php

namespace Tests\Unit;

use App\Services\QboAdminSnapshotBuilder;
use Carbon\CarbonImmutable;
use PHPUnit\Framework\TestCase;

class QboAdminSnapshotBuilderTest extends TestCase
{
    public function test_it_groups_recent_invoices_and_skips_unmatched_customers(): void
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
                ['id' => 20, 'qbo_customer_id' => 'missing'],
            ],
            ['customer-1' => 125.75],
            $invoices,
            CarbonImmutable::parse('2026-09-02T01:00:00Z'),
        );

        $this->assertSame([10], array_keys($snapshots));
        $this->assertSame(125.75, $snapshots[10]['balance']);
        $this->assertCount(20, $snapshots[10]['invoices']);
        $this->assertSame('1', $snapshots[10]['invoices'][0]['Id']);
        $this->assertSame('2026-09-02T01:00:00+00:00', $snapshots[10]['refreshed_at']);
    }
}
