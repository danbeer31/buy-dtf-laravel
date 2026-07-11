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
            if (!Schema::connection($connection)->hasColumn('dtforders', 'qbo_invoice_number')) {
                $table->string('qbo_invoice_number')->nullable()->after('qbo_invoice_id');
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
            $table->dropColumn('qbo_invoice_number');
        });
    }
};
