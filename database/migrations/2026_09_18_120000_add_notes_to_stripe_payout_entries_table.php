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

        if (! $schema->hasTable('stripe_payout_entries')) {
            throw new \RuntimeException('The stripe_payout_entries table is missing on the Fuel connection.');
        }

        if (! $schema->hasColumn('stripe_payout_entries', 'notes')) {
            $schema->table('stripe_payout_entries', function (Blueprint $table): void {
                // Append the nullable column to keep the production ALTER narrowly scoped.
                $table->text('notes')->nullable();
            });
        }
    }

    public function down(): void
    {
        $this->auditedFuelConnection();

        // Intentionally additive: retaining this nullable column is the safe rollback.
    }

    private function auditedFuelConnection(): string
    {
        // Laravel temporarily makes the --database connection the default while a
        // migration runs. Binding the DDL to that active connection keeps the
        // migration repository and altered schema on the same database.
        $activeConnection = DB::getDefaultConnection();
        $configuredFuelConnection = config('database.fuel_connection');

        if (! is_string($configuredFuelConnection) || $configuredFuelConnection === '') {
            throw new \RuntimeException('The audited Fuel database connection is not configured.');
        }

        if ($activeConnection !== $configuredFuelConnection) {
            throw new \RuntimeException(sprintf(
                'Refusing payout schema correction: active migration connection [%s] does not match the audited Fuel connection [%s].',
                $activeConnection,
                $configuredFuelConnection,
            ));
        }

        return $activeConnection;
    }
};
