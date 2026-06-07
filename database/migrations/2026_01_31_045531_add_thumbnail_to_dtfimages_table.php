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
        Schema::connection($connection)->table('dtfimages', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('dtfimages', 'thumbnail')) {
                $table->string('thumbnail')->nullable()->after('image');
            }
        });

        Schema::connection($connection)->table('savedimages', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('savedimages', 'thumbnail')) {
                $table->string('thumbnail')->nullable()->after('image');
            }
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');
        Schema::connection($connection)->table('dtfimages', function (Blueprint $table) use ($connection) {
            if (Schema::connection($connection)->hasColumn('dtfimages', 'thumbnail')) {
                $table->dropColumn('thumbnail');
            }
        });

        Schema::connection($connection)->table('savedimages', function (Blueprint $table) use ($connection) {
            if (Schema::connection($connection)->hasColumn('savedimages', 'thumbnail')) {
                $table->dropColumn('thumbnail');
            }
        });
    }
};
