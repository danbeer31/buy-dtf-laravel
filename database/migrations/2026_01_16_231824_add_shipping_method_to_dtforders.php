<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');
        Schema::connection($connection)->table('dtforders', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('dtforders', 'shipping_method')) {
                $table->string('shipping_method', 100)->nullable()->after('shipping_method_id');
            }
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');
        Schema::connection($connection)->table('dtforders', function (Blueprint $table) {
            $table->dropColumn('shipping_method');
        });
    }
};
