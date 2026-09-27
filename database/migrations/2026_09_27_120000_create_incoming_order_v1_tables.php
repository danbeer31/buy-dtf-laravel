<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        $connection = $this->auditedFuelConnection();
        $schema = Schema::connection($connection);

        if (! DB::connection($connection)->pretending()) {
            foreach (['businesses', 'dtforders', 'dtfimages'] as $requiredTable) {
                if (! $schema->hasTable($requiredTable)) {
                    throw new RuntimeException("Required Fuel table [{$requiredTable}] is missing.");
                }
            }
        }

        $driver = DB::connection($connection)->getDriverName();
        $asciiCollation = $driver === 'mysql' ? 'ascii_bin' : 'BINARY';

        if (! $schema->hasTable('incoming_order_jobs')) {
            $schema->create('incoming_order_jobs', function (Blueprint $table) use ($asciiCollation): void {
                $table->id();
                $table->unsignedBigInteger('dtfimage_id')->nullable()->unique();
                $clientColumn = $table->string('integration_client', 64)->collation($asciiCollation);
                $keyColumn = $table->string('idempotency_key', 128)->collation($asciiCollation);
                if ($asciiCollation === 'ascii_bin') {
                    $clientColumn->charset('ascii');
                    $keyColumn->charset('ascii');
                }
                $table->char('request_fingerprint', 64);
                $table->char('expected_art_sha256', 64);
                $table->char('actual_art_sha256', 64)->nullable();
                $table->string('state', 32);
                $leaseOwnerColumn = $table->char('lease_owner', 36)->nullable()->collation($asciiCollation);
                if ($asciiCollation === 'ascii_bin') {
                    $leaseOwnerColumn->charset('ascii');
                }
                $table->dateTime('lease_expires_at', 6)->nullable();
                $table->dateTime('heartbeat_at', 6)->nullable();
                $table->unsignedInteger('attempt_count')->default(0);
                $table->dateTime('last_attempt_at', 6)->nullable();
                $table->json('response_payload')->nullable();

                $table->unsignedSmallInteger('job_label_version')->nullable();
                $table->boolean('job_label_required')->nullable();
                $table->string('job_label_mode', 32)->nullable();
                $table->string('job_label_status', 32)->nullable();
                $table->string('job_label_reason', 64)->nullable();
                $table->json('job_label_metadata')->nullable();
                $table->char('job_label_fingerprint', 64)->nullable();

                $table->decimal('art_width_in', 10, 4);
                $table->decimal('art_height_in', 10, 4);
                $table->string('original_asset_path', 1024)->nullable();
                $table->char('original_asset_sha256', 64)->nullable();
                $table->string('normalized_asset_path', 1024)->nullable();
                $table->char('normalized_asset_sha256', 64)->nullable();
                $table->string('job_card_asset_path', 1024)->nullable();
                $table->char('job_card_asset_sha256', 64)->nullable();
                $table->string('renderer_version', 64)->nullable();

                $table->string('production_state', 32)->nullable();
                $table->unsignedInteger('production_attempt_count')->default(0);
                $table->char('production_group_key', 64)->nullable();
                $productionOwnerColumn = $table->char('production_owner', 36)->nullable()->collation($asciiCollation);
                if ($asciiCollation === 'ascii_bin') {
                    $productionOwnerColumn->charset('ascii');
                }
                $table->dateTime('production_heartbeat_at', 6)->nullable();
                $table->dateTime('production_lease_expires_at', 6)->nullable();
                $table->json('production_result')->nullable();
                $table->dateTime('production_started_at', 6)->nullable();
                $table->dateTime('production_completed_at', 6)->nullable();
                $table->string('last_error_code', 64)->nullable();
                $table->timestamps(6);

                $table->unique(['integration_client', 'idempotency_key'], 'incoming_jobs_client_key_unique');
                $table->index(['state', 'lease_expires_at'], 'incoming_jobs_state_lease_index');
                $table->index('job_label_status', 'incoming_jobs_label_status_index');
                $table->index('production_state', 'incoming_jobs_production_state_index');
                $table->index(
                    ['production_state', 'production_lease_expires_at'],
                    'incoming_jobs_production_lease_index',
                );
            });
        }

        if (! $schema->hasTable('api_asset_records')) {
            $schema->create('api_asset_records', function (Blueprint $table): void {
                $table->id();
                $table->unsignedBigInteger('incoming_order_job_id');
                $table->unsignedBigInteger('dtfimage_id')->nullable();
                $table->string('origin', 64);
                $table->string('asset_role', 64);
                $table->string('storage_scope', 32);
                $table->string('asset_path', 1024);
                $table->char('path_hash', 64);
                $table->char('sha256', 64)->nullable();
                $table->unsignedBigInteger('bytes')->nullable();
                $table->string('retention_policy', 32)->default('forever');
                $table->boolean('retention_enabled')->default(false);
                $table->unsignedInteger('retention_days')->nullable();
                $table->dateTime('expires_at', 6)->nullable();
                $table->dateTime('customer_deleted_at', 6)->nullable();
                $table->dateTime('purged_at', 6)->nullable();
                $table->timestamps(6);

                $table->unique(
                    ['incoming_order_job_id', 'asset_role', 'path_hash'],
                    'api_assets_job_role_path_unique',
                );
                $table->index(['retention_enabled', 'expires_at', 'purged_at'], 'api_assets_retention_index');
                $table->index('path_hash', 'api_assets_path_hash_index');
            });
        }

    }

    public function down(): void
    {
        $this->auditedFuelConnection();

        // Intentionally additive. Code rollback must retain frozen jobs, assets,
        // idempotency outcomes, and API asset-retention records.
    }

    private function auditedFuelConnection(): string
    {
        $activeConnection = DB::getDefaultConnection();
        $configuredFuelConnection = config('database.fuel_connection');

        if (! is_string($configuredFuelConnection) || $configuredFuelConnection === '') {
            throw new RuntimeException('The audited Fuel database connection is not configured.');
        }

        if ($activeConnection !== $configuredFuelConnection) {
            throw new RuntimeException(sprintf(
                'Refusing incoming-order schema change: active migration connection [%s] does not match the audited Fuel connection [%s].',
                $activeConnection,
                $configuredFuelConnection,
            ));
        }

        return $activeConnection;
    }
};
