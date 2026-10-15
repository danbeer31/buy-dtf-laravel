<?php

use App\Models\PaymentInfo;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        $connection = (new PaymentInfo())->getConnectionName();

        if (!Schema::connection($connection)->hasTable('stripe_payment_completions')) {
            Schema::connection($connection)->create('stripe_payment_completions', function (Blueprint $table) {
                $table->id();
                $table->string('payment_intent_id')->unique();
                $table->string('flow', 32);
                $table->string('state', 32);
                $table->unsignedBigInteger('payment_info_id')->nullable();
                $table->text('last_error')->nullable();
                $table->timestamps();
            });
        }

        if (!Schema::connection($connection)->hasTable('stripe_payment_completion_steps')) {
            Schema::connection($connection)->create('stripe_payment_completion_steps', function (Blueprint $table) {
                $table->id();
                $table->string('payment_intent_id');
                $table->string('step_key');
                $table->string('state', 32);
                $table->string('external_id')->nullable();
                $table->text('error')->nullable();
                $table->timestamps();
                $table->unique(['payment_intent_id', 'step_key'], 'stripe_completion_step_unique');
            });
        }
    }

    public function down(): void
    {
        $connection = (new PaymentInfo())->getConnectionName();
        Schema::connection($connection)->dropIfExists('stripe_payment_completion_steps');
        Schema::connection($connection)->dropIfExists('stripe_payment_completions');
    }
};
