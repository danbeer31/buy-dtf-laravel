<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Database\Schema\Builder;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        $connection = $this->auditedFuelConnection();
        $schema = Schema::connection($connection);

        // Schema introspection is unavailable while Laravel records pretend
        // queries. The deployment runner proves the table exists and the
        // column is absent before invoking the staged migration with --pretend.
        if (DB::connection($connection)->pretending()) {
            $this->addItemMetadataColumn($schema);

            return;
        }

        if (! $schema->hasTable('savedimages')) {
            throw new RuntimeException('The savedimages table is missing on the audited Fuel connection.');
        }

        if (! $schema->hasColumn('savedimages', 'item_meta')) {
            $this->addItemMetadataColumn($schema);
        }
    }

    public function down(): void
    {
        $this->auditedFuelConnection();

        // Intentionally additive. Source rollback must retain every frozen
        // Saved Image policy and private source-artwork reference.
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
                'Refusing Saved Image metadata schema change: active migration connection [%s] does not match the audited Fuel connection [%s].',
                $activeConnection,
                $configuredFuelConnection,
            ));
        }

        return $activeConnection;
    }

    private function addItemMetadataColumn(Builder $schema): void
    {
        $schema->table('savedimages', function (Blueprint $table): void {
            $table->text('item_meta')->nullable();
        });
    }
};
