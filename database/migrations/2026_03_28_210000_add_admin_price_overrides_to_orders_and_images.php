<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

class AddAdminPriceOverridesToOrdersAndImages extends Migration
{
    public function up(): void
    {
        $connection = config('database.fuel_connection', env('FUEL_DB_CONNECTION', 'fuelmysql'));

        Schema::connection($connection)->table('dtfimages', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('dtfimages', 'admin_unit_price')) {
                $table->decimal('admin_unit_price', 12, 4)->nullable()->after('price');
            }
            if (!Schema::connection($connection)->hasColumn('dtfimages', 'admin_price_locked')) {
                $table->unsignedTinyInteger('admin_price_locked')->default(0)->after('admin_unit_price');
            }
        });

        Schema::connection($connection)->table('dtforders', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('dtforders', 'admin_discount_pct')) {
                $table->decimal('admin_discount_pct', 7, 4)->nullable()->after('sales_tax');
            }
            if (!Schema::connection($connection)->hasColumn('dtforders', 'admin_discount_locked')) {
                $table->unsignedTinyInteger('admin_discount_locked')->default(0)->after('admin_discount_pct');
            }
        });
    }

    public function down(): void
    {
        $connection = config('database.fuel_connection', env('FUEL_DB_CONNECTION', 'fuelmysql'));

        Schema::connection($connection)->table('dtfimages', function (Blueprint $table) use ($connection) {
            if (Schema::connection($connection)->hasColumn('dtfimages', 'admin_price_locked')) {
                $table->dropColumn('admin_price_locked');
            }
            if (Schema::connection($connection)->hasColumn('dtfimages', 'admin_unit_price')) {
                $table->dropColumn('admin_unit_price');
            }
        });

        Schema::connection($connection)->table('dtforders', function (Blueprint $table) use ($connection) {
            if (Schema::connection($connection)->hasColumn('dtforders', 'admin_discount_locked')) {
                $table->dropColumn('admin_discount_locked');
            }
            if (Schema::connection($connection)->hasColumn('dtforders', 'admin_discount_pct')) {
                $table->dropColumn('admin_discount_pct');
            }
        });
    }
};
