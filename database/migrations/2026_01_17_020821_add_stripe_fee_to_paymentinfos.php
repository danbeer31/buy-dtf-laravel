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
            if (!Schema::connection($connection)->hasColumn('paymentinfos', 'stripe_fee')) {
                $table->decimal('stripe_fee', 10, 2)->nullable()->after('amount');
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
            $table->dropColumn('stripe_fee');
        });
    }
};
