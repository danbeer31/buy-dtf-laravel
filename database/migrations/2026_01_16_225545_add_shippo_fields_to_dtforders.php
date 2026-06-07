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
            if (!Schema::connection($connection)->hasColumn('dtforders', 'shippo_transaction_id')) {
                $table->string('shippo_transaction_id', 100)->nullable()->after('shippo_service_name');
            }
            if (!Schema::connection($connection)->hasColumn('dtforders', 'tracking_number')) {
                $table->string('tracking_number', 100)->nullable()->after('shippo_transaction_id');
            }
            if (!Schema::connection($connection)->hasColumn('dtforders', 'label_url')) {
                $table->text('label_url')->nullable()->after('tracking_number');
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
            $table->dropColumn(['shippo_transaction_id', 'tracking_number', 'label_url']);
        });
    }
};
