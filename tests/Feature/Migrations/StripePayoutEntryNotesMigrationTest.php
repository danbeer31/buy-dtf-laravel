<?php

namespace Tests\Feature\Migrations;

use App\Models\StripePayoutEntry;
use Illuminate\Database\QueryException;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

class StripePayoutEntryNotesMigrationTest extends TestCase
{
    public function test_additive_correction_repairs_the_observed_notes_write_failure(): void
    {
        $connection = (string) config('database.fuel_connection');
        $schema = Schema::connection($connection);

        $schema->table('stripe_payout_entries', function (Blueprint $table): void {
            $table->dropColumn('notes');
        });

        $payoutId = DB::connection($connection)->table('stripe_payouts')->insertGetId([
            'stripe_payout_id' => 'po_notes_migration_test',
            'amount' => 100,
            'fee' => 3,
            'net' => 97,
            'currency' => 'USD',
            'status' => 'paid',
            'arrival_date' => '2026-09-18 12:00:00',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        try {
            StripePayoutEntry::query()->create([
                'stripe_payout_id' => $payoutId,
                'stripe_transaction_id' => 'txn_missing_notes_column',
                'type' => 'charge',
                'gross' => 100,
                'fee' => 3,
                'net' => 97,
                'notes' => 'Production-only business label',
            ]);

            $this->fail('The legacy schema should reject a write to the missing notes column.');
        } catch (QueryException $exception) {
            $this->assertStringContainsString('notes', strtolower($exception->getMessage()));
        }

        $this->assertDatabaseCount('stripe_payout_entries', 0, $connection);

        $migration = require database_path('migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php');
        $migration->up();

        $this->assertTrue($schema->hasColumn('stripe_payout_entries', 'notes'));

        $entry = StripePayoutEntry::query()->create([
            'stripe_payout_id' => $payoutId,
            'stripe_transaction_id' => 'txn_repaired_notes_column',
            'type' => 'charge',
            'gross' => 100,
            'fee' => 3,
            'net' => 97,
            'notes' => 'Production-only business label',
        ]);

        $this->assertSame('Production-only business label', $entry->fresh()->notes);

        $migration->up();
        $migration->down();

        $this->assertTrue($schema->hasColumn('stripe_payout_entries', 'notes'));
        $this->assertDatabaseCount('stripe_payout_entries', 1, $connection);
    }
}
