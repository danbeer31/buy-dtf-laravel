<?php

namespace Tests\Feature\Migrations;

use Illuminate\Database\MySqlConnection;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use PDO;
use Tests\TestCase;

class SavedImageItemMetadataMigrationTest extends TestCase
{
    private const MIGRATION = 'migrations/2026_10_01_120000_add_item_meta_to_savedimages_table.php';

    public function test_migration_is_guarded_additive_idempotent_and_preserves_metadata_on_down(): void
    {
        $connection = (string) config('database.fuel_connection');
        $schema = Schema::connection($connection);
        $schema->table('savedimages', function (Blueprint $table): void {
            $table->dropColumn('item_meta');
        });

        $businessId = DB::connection($connection)->table('businesses')->insertGetId([
            'business_name' => 'Saved Image Migration Business',
            'email' => 'saved-image-migration@example.test',
            'status' => 1,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $savedImageId = DB::connection($connection)->table('savedimages')->insertGetId([
            'business_id' => $businessId,
            'image' => '/uploads/images/migration-policy.png',
            'image_name' => 'Migration Policy',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $migration = require database_path(self::MIGRATION);
        $migrator = app('migrator');
        $migrator->usingConnection($connection, function () use ($migration): void {
            $migration->up();
            $migration->up();
        });

        $this->assertTrue($schema->hasColumn('savedimages', 'item_meta'));
        $snapshot = json_encode([
            'alpha_processing' => [
                'version' => 1,
                'scope' => 'production_derivative',
                'threshold' => 128,
            ],
        ], JSON_THROW_ON_ERROR);
        DB::connection($connection)->table('savedimages')->where('id', $savedImageId)->update([
            'item_meta' => $snapshot,
        ]);

        $migrator->usingConnection($connection, fn () => $migration->down());

        $this->assertTrue($schema->hasColumn('savedimages', 'item_meta'));
        $this->assertSame(
            $snapshot,
            DB::connection($connection)->table('savedimages')->where('id', $savedImageId)->value('item_meta'),
        );
    }

    public function test_migration_refuses_a_different_active_connection_without_touching_either_schema(): void
    {
        $fuelConnection = (string) config('database.fuel_connection');
        $fuelSchema = Schema::connection($fuelConnection);
        $fuelSchema->table('savedimages', function (Blueprint $table): void {
            $table->dropColumn('item_meta');
        });

        $wrongConnection = 'wrong_saved_image_migration_target';
        config()->set("database.connections.{$wrongConnection}", [
            'driver' => 'sqlite',
            'database' => ':memory:',
            'prefix' => '',
            'foreign_key_constraints' => true,
        ]);
        DB::purge($wrongConnection);
        $wrongSchema = Schema::connection($wrongConnection);
        $wrongSchema->create('savedimages', function (Blueprint $table): void {
            $table->id();
            $table->string('marker')->nullable();
        });

        $migration = require database_path(self::MIGRATION);
        $migrator = app('migrator');
        foreach (['up', 'down'] as $method) {
            try {
                $migrator->usingConnection($wrongConnection, fn () => $migration->{$method}());
                $this->fail("Migration {$method} must reject the wrong active connection.");
            } catch (\RuntimeException $exception) {
                $this->assertStringContainsString('does not match the audited Fuel connection', $exception->getMessage());
            }
        }

        $this->assertFalse($wrongSchema->hasColumn('savedimages', 'item_meta'));
        $this->assertTrue($wrongSchema->hasColumn('savedimages', 'marker'));
        $this->assertFalse($fuelSchema->hasColumn('savedimages', 'item_meta'));
        $this->assertSame($fuelConnection, DB::getDefaultConnection());
        DB::purge($wrongConnection);
    }

    public function test_pretend_mode_emits_only_the_expected_nullable_column_statement(): void
    {
        $connection = (string) config('database.fuel_connection');
        $schema = Schema::connection($connection);
        $schema->table('savedimages', function (Blueprint $table): void {
            $table->dropColumn('item_meta');
        });

        $migration = require database_path(self::MIGRATION);
        $queries = app('migrator')->usingConnection(
            $connection,
            fn (): array => DB::connection($connection)->pretend(fn () => $migration->up()),
        );

        $this->assertCount(1, $queries);
        $this->assertStringContainsString(
            'alter table "savedimages" add column "item_meta" text',
            strtolower($queries[0]['query']),
        );
        $this->assertFalse($schema->hasColumn('savedimages', 'item_meta'));
    }

    public function test_mysql_grammar_emits_one_nullable_text_column_alter(): void
    {
        $connection = new MySqlConnection(new PDO('sqlite::memory:'), 'saved-image-grammar-probe');
        $connection->useDefaultSchemaGrammar();
        $blueprint = new Blueprint($connection, 'savedimages', function (Blueprint $table): void {
            $table->text('item_meta')->nullable();
        });

        $sql = $blueprint->toSql();

        $this->assertCount(1, $sql);
        $this->assertSame(
            'alter table `savedimages` add `item_meta` text null',
            strtolower($sql[0]),
        );
    }
}
