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
        Schema::table('paymentinfos', function (Blueprint $table) {
            if (!Schema::hasColumn('paymentinfos', 'qbo_fee_expense_id')) {
                $table->string('qbo_fee_expense_id')->nullable()->after('qbo_payment_id');
            }
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('paymentinfos', function (Blueprint $table) {
            if (Schema::hasColumn('paymentinfos', 'qbo_fee_expense_id')) {
                $table->dropColumn('qbo_fee_expense_id');
            }
        });
    }
};
