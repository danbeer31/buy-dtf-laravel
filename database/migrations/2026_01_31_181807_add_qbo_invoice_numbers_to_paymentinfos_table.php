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
        Schema::connection($connection)->table('paymentinfos', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('paymentinfos', 'qbo_invoice_numbers')) {
                $table->text('qbo_invoice_numbers')->nullable()->after('qbo_payment_id');
            }
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');
        Schema::connection($connection)->table('paymentinfos', function (Blueprint $table) {
            $table->dropColumn('qbo_invoice_numbers');
        });
    }
};
