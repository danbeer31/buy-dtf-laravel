<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');

        Schema::connection($connection)->create('accounting_reconciliation_checks', function (Blueprint $table) {
            $table->id();
            $table->unsignedBigInteger('business_id')->nullable();
            $table->string('provider')->default('stripe');
            $table->string('scope')->default('current');
            $table->date('as_of_date')->nullable();
            $table->string('currency', 3)->default('USD');

            $table->bigInteger('expected_holding_amount_cents')->default(0);
            $table->bigInteger('actual_holding_amount_cents')->default(0);
            $table->bigInteger('difference_amount_cents')->default(0);

            $table->string('status')->default('error'); // balanced, mismatch, error
            $table->integer('tolerance_cents')->default(1);
            $table->text('notes')->nullable();
            $table->json('meta')->nullable();
            $table->timestamp('ran_at')->nullable();
            $table->timestamps();

            $table->index(['provider', 'scope']);
            $table->index('as_of_date');
            $table->index('status');
            $table->index('business_id');
        });
    }

    public function down(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');
        Schema::connection($connection)->dropIfExists('accounting_reconciliation_checks');
    }
};

