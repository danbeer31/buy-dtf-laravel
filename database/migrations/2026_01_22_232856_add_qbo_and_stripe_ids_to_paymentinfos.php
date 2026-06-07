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
            if (!Schema::connection($connection)->hasColumn('paymentinfos', 'stripe_charge_id')) {
                $table->string('stripe_charge_id')->nullable()->after('processor_confirm');
            }
            if (!Schema::connection($connection)->hasColumn('paymentinfos', 'qbo_payment_id')) {
                $table->string('qbo_payment_id')->nullable()->after('stripe_charge_id');
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
            $table->dropColumn(['stripe_charge_id', 'qbo_payment_id']);
        });
    }
};
