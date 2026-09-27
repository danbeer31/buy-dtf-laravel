<?php

namespace Tests\Feature\Migrations;

use Illuminate\Database\MySqlConnection;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use PDO;
use Tests\TestCase;

class IncomingOrderV1MigrationTest extends TestCase
{
    public function test_migration_is_additive_idempotent_and_down_preserves_frozen_data(): void
    {
        $connection = (string) config('database.fuel_connection');
        $schema = Schema::connection($connection);
        $this->dropNewTables($schema);

        $migration = require database_path('migrations/2026_09_27_120000_create_incoming_order_v1_tables.php');
        $migrator = app('migrator');
        $migrator->usingConnection($connection, fn () => $migration->up());

        $this->assertTrue($schema->hasTable('incoming_order_jobs'));
        $this->assertTrue($schema->hasTable('api_asset_records'));
        $this->assertTrue($schema->hasTable('customer_artwork_removals'));
        foreach (['integration_client', 'idempotency_key', 'job_label_metadata', 'production_state'] as $column) {
            $this->assertTrue($schema->hasColumn('incoming_order_jobs', $column));
        }

        DB::connection($connection)->table('incoming_order_jobs')->insert([
            'integration_client' => 'shopnltees',
            'idempotency_key' => 'migration-preservation-key',
            'request_fingerprint' => str_repeat('a', 64),
            'expected_art_sha256' => str_repeat('b', 64),
            'state' => 'completed',
            'attempt_count' => 1,
            'art_width_in' => 1,
            'art_height_in' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $migrator->usingConnection($connection, function () use ($migration): void {
            $migration->up();
            $migration->down();
        });

        $this->assertTrue($schema->hasTable('incoming_order_jobs'));
        $this->assertDatabaseHas('incoming_order_jobs', [
            'idempotency_key' => 'migration-preservation-key',
            'state' => 'completed',
        ], $connection);
    }

    public function test_migration_refuses_wrong_active_connection_without_touching_it(): void
    {
        $wrong = 'wrong_incoming_order_migration_target';
        config()->set("database.connections.{$wrong}", [
            'driver' => 'sqlite',
            'database' => ':memory:',
            'prefix' => '',
            'foreign_key_constraints' => true,
        ]);
        DB::purge($wrong);
        $wrongSchema = Schema::connection($wrong);
        $wrongSchema->create('marker', function (Blueprint $table): void {
            $table->id();
        });

        $migration = require database_path('migrations/2026_09_27_120000_create_incoming_order_v1_tables.php');
        $migrator = app('migrator');
        foreach (['up', 'down'] as $method) {
            try {
                $migrator->usingConnection($wrong, fn () => $migration->{$method}());
                $this->fail("Migration {$method} must reject the wrong active connection.");
            } catch (\RuntimeException $exception) {
                $this->assertStringContainsString('does not match the audited Fuel connection', $exception->getMessage());
            }
        }

        $this->assertTrue($wrongSchema->hasTable('marker'));
        $this->assertFalse($wrongSchema->hasTable('incoming_order_jobs'));
        $this->assertFalse($wrongSchema->hasTable('api_asset_records'));
        $this->assertFalse($wrongSchema->hasTable('customer_artwork_removals'));
        DB::purge($wrong);
    }

    public function test_mysql_binary_idempotency_columns_use_the_matching_ascii_charset(): void
    {
        $connection = new MySqlConnection(new PDO('sqlite::memory:'), 'grammar-probe', '', [
            'charset' => 'utf8mb4',
            'collation' => 'utf8mb4_unicode_ci',
        ]);
        $connection->useDefaultSchemaGrammar();
        $blueprint = new Blueprint($connection, 'incoming_order_probe', function (Blueprint $table): void {
            $table->create();
            $table->string('idempotency_key', 128)->charset('ascii')->collation('ascii_bin');
        });

        $sql = implode("\n", $blueprint->toSql());
        $this->assertStringContainsString(
            "`idempotency_key` varchar(128) character set ascii collate 'ascii_bin' not null",
            $sql,
        );
    }

    private function dropNewTables($schema): void
    {
        $schema->dropIfExists('customer_artwork_removals');
        $schema->dropIfExists('api_asset_records');
        $schema->dropIfExists('incoming_order_jobs');
    }
}
