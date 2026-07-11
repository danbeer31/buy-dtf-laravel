<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        $connection = config('database.fuel_connection', env('FUEL_DB_CONNECTION', 'fuelmysql'));

        Schema::connection($connection)->table('dtfimages', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('dtfimages', 'item_type')) {
                $table->string('item_type', 40)->nullable()->after('sha256_bitmap');
            }
            if (!Schema::connection($connection)->hasColumn('dtfimages', 'item_meta')) {
                $table->text('item_meta')->nullable()->after('item_type');
            }
            if (!Schema::connection($connection)->hasColumn('dtfimages', 'upload_mime')) {
                $table->string('upload_mime', 120)->nullable()->after('item_meta');
            }
        });
    }

    public function down(): void
    {
        $connection = config('database.fuel_connection', env('FUEL_DB_CONNECTION', 'fuelmysql'));

        Schema::connection($connection)->table('dtfimages', function (Blueprint $table) use ($connection) {
            if (Schema::connection($connection)->hasColumn('dtfimages', 'upload_mime')) {
                $table->dropColumn('upload_mime');
            }
            if (Schema::connection($connection)->hasColumn('dtfimages', 'item_meta')) {
                $table->dropColumn('item_meta');
            }
            if (Schema::connection($connection)->hasColumn('dtfimages', 'item_type')) {
                $table->dropColumn('item_type');
            }
        });
    }
};

