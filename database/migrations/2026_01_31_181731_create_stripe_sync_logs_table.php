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
        Schema::connection($connection)->create('stripe_sync_logs', function (Blueprint $table) {
            $table->id();
            $table->string('sync_type'); // 'webhook', 'cron', 'manual'
            $table->string('event_type')->nullable(); // e.g., 'payout.paid', 'charge.succeeded'
            $table->string('stripe_id')->nullable(); // Stripe object ID (e.g., payout ID)
            $table->string('status'); // 'success', 'failure', 'partial'
            $table->text('message')->nullable();
            $table->json('payload')->nullable();
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');
        Schema::connection($connection)->dropIfExists('stripe_sync_logs');
    }
};
