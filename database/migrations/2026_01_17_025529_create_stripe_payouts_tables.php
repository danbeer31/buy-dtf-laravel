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
        Schema::connection($connection)->create('stripe_payouts', function (Blueprint $table) {
            $table->id();
            $table->string('stripe_payout_id')->unique();
            $table->decimal('amount', 12, 2);
            $table->decimal('fee', 12, 2)->default(0);
            $table->decimal('net', 12, 2)->default(0);
            $table->string('currency');
            $table->string('status');
            $table->timestamp('arrival_date');
            $table->string('description')->nullable();
            $table->string('qbo_deposit_id')->nullable(); // Track if synced to QBO Deposit
            $table->timestamps();
        });

        Schema::connection($connection)->create('stripe_payout_entries', function (Blueprint $table) use ($connection) {
            $table->id();
            $table->foreignId('stripe_payout_id')->constrained('stripe_payouts')->onDelete('cascade');
            $table->string('stripe_transaction_id'); // balance_transaction ID
            $table->string('type'); // charge, refund, adjustment, etc.
            $table->decimal('gross', 12, 2);
            $table->decimal('fee', 12, 2);
            $table->decimal('net', 12, 2);
            $table->unsignedBigInteger('dtforder_id')->nullable();
            $table->timestamps();

            $table->index('stripe_transaction_id');
            $table->index('dtforder_id');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::connection('fuelmysql')->dropIfExists('stripe_payout_entries');
        Schema::connection('fuelmysql')->dropIfExists('stripe_payouts');
    }
};
