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
        Schema::connection($connection)->table('dropbox_tokens', function (Blueprint $table) {
            $table->text('access_token')->change();
            $table->text('refresh_token')->nullable()->change();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');
        Schema::connection($connection)->table('dropbox_tokens', function (Blueprint $table) {
            $table->string('access_token', 255)->change();
            $table->string('refresh_token', 255)->nullable()->change();
        });
    }
};
