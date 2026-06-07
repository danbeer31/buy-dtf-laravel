<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');

        // 1. Add missing columns to dtforders
        Schema::connection($connection)->table('dtforders', function (Blueprint $table) use ($connection) {
            if (!Schema::connection($connection)->hasColumn('dtforders', 'shippo_transaction_id')) {
                $table->string('shippo_transaction_id', 100)->nullable()->after('shippo_service_name');
            }
            if (!Schema::connection($connection)->hasColumn('dtforders', 'tracking_number')) {
                $table->string('tracking_number', 100)->nullable()->after('shippo_transaction_id');
            }
            if (!Schema::connection($connection)->hasColumn('dtforders', 'label_url')) {
                $table->text('label_url')->nullable()->after('tracking_number');
            }
            if (!Schema::connection($connection)->hasColumn('dtforders', 'shipping_method')) {
                $table->string('shipping_method', 100)->nullable()->after('shipping_method_id');
            }
        });

        // 2. Ensure order statuses exist
        $statuses = [
            11 => ['name' => 'in transit', 'color' => '#17a2b8', 'sort_order' => 5],
            12 => ['name' => 'out for delivery', 'color' => '#ffc107', 'sort_order' => 6],
            13 => ['name' => 'delivered', 'color' => '#28a745', 'sort_order' => 7],
            14 => ['name' => 'pickup complete', 'color' => '#153c65', 'sort_order' => 8],
        ];

        foreach ($statuses as $id => $data) {
            DB::connection($connection)->table('order_statuses')->updateOrInsert(
                ['id' => $id],
                array_merge($data, ['locked' => 0, 'updated_at' => now()])
            );
        }
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        $connection = env('FUEL_DB_CONNECTION', 'fuelmysql');

        Schema::connection($connection)->table('dtforders', function (Blueprint $table) {
            $table->dropColumn(['shippo_transaction_id', 'tracking_number', 'label_url', 'shipping_method']);
        });

        DB::connection($connection)->table('order_statuses')->whereIn('id', [11, 12, 13, 14])->delete();
    }
};
