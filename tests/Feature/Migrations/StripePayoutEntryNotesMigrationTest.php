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
        $migrator = app('migrator');
        $migrator->usingConnection($connection, function () use ($migration): void {
            $migration->up();
        });

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

        $migrator->usingConnection($connection, function () use ($migration): void {
            $migration->up();
            $migration->down();
        });

        $this->assertTrue($schema->hasColumn('stripe_payout_entries', 'notes'));
        $this->assertDatabaseCount('stripe_payout_entries', 1, $connection);
    }

    public function test_correction_refuses_a_different_active_connection_without_touching_either_schema(): void
    {
        $fuelConnection = (string) config('database.fuel_connection');
        $fuelSchema = Schema::connection($fuelConnection);

        $fuelSchema->table('stripe_payout_entries', function (Blueprint $table): void {
            $table->dropColumn('notes');
        });

        $wrongConnection = 'wrong_migration_target';
        config()->set("database.connections.{$wrongConnection}", [
            'driver' => 'sqlite',
            'database' => ':memory:',
            'prefix' => '',
            'foreign_key_constraints' => true,
        ]);
        DB::purge($wrongConnection);

        $wrongSchema = Schema::connection($wrongConnection);
        $wrongSchema->create('stripe_payout_entries', function (Blueprint $table): void {
            $table->id();
            $table->string('marker')->nullable();
        });

        $migration = require database_path('migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php');
        $migrator = app('migrator');

        try {
            $migrator->usingConnection($wrongConnection, function () use ($migration): void {
                $migration->up();
            });

            $this->fail('The migration must reject a non-Fuel active connection.');
        } catch (\RuntimeException $exception) {
            $this->assertStringContainsString('does not match the audited Fuel connection', $exception->getMessage());
        }

        try {
            $migrator->usingConnection($wrongConnection, function () use ($migration): void {
                $migration->down();
            });

            $this->fail('The rollback must reject a non-Fuel active connection.');
        } catch (\RuntimeException $exception) {
            $this->assertStringContainsString('does not match the audited Fuel connection', $exception->getMessage());
        }

        $this->assertFalse($wrongSchema->hasColumn('stripe_payout_entries', 'notes'));
        $this->assertTrue($wrongSchema->hasColumn('stripe_payout_entries', 'marker'));
        $this->assertFalse($fuelSchema->hasColumn('stripe_payout_entries', 'notes'));
        $this->assertSame($fuelConnection, DB::getDefaultConnection());

        DB::purge($wrongConnection);
    }
}
