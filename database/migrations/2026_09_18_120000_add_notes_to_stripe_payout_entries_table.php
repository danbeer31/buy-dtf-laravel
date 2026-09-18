<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        $connection = config('database.fuel_connection', env('FUEL_DB_CONNECTION', 'fuelmysql'));
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
        // Intentionally additive: retaining this nullable column is the safe rollback.
    }
};
