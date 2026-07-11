<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        $schema = DB::connection('mysql')->getDatabaseName();

        $uniqueExists = DB::connection('mysql')->table('information_schema.statistics')
            ->where('table_schema', $schema)
            ->where('table_name', 'users')
            ->where('index_name', 'users_fuel_business_id_unique')
            ->exists();

        if ($uniqueExists) {
            DB::connection('mysql')->statement('ALTER TABLE users DROP INDEX users_fuel_business_id_unique');
        }

        $indexExists = DB::connection('mysql')->table('information_schema.statistics')
            ->where('table_schema', $schema)
            ->where('table_name', 'users')
            ->where('index_name', 'users_fuel_business_id_index')
            ->exists();

        if (!$indexExists) {
            DB::connection('mysql')->statement('ALTER TABLE users ADD INDEX users_fuel_business_id_index (fuel_business_id)');
        }
    }

    public function down(): void
    {
        // No-op by design: re-adding uniqueness may fail if multiple users share one business.
    }
};
