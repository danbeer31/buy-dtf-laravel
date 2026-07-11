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
        Schema::connection($connection)->table('stripe_payouts', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('stripe_payouts', 'qbo_transfer_id')) {
                $table->string('qbo_transfer_id')->nullable()->after('qbo_deposit_id');
            }
        });

        Schema::connection($connection)->table('stripe_payout_entries', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('stripe_payout_entries', 'qbo_expense_id')) {
                $table->string('qbo_expense_id')->nullable();
            }
            if (!Schema::connection($connection)->hasColumn('stripe_payout_entries', 'qbo_refund_id')) {
                $table->string('qbo_refund_id')->nullable();
            }
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');
        Schema::connection($connection)->table('stripe_payouts', function (Blueprint $table) {
            $table->dropColumn('qbo_transfer_id');
        });

        Schema::connection($connection)->table('stripe_payout_entries', function (Blueprint $table) {
            $table->dropColumn(['qbo_expense_id', 'qbo_refund_id']);
        });
    }
};
