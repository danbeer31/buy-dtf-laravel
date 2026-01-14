<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        Schema::table('users', function (Blueprint $table) {
            // links to buydtf_fuel_stage.businesses.id
            $table->unsignedInteger('fuel_business_id')->nullable()->unique()->after('id');

            // force users to set password on first login
            $table->boolean('password_reset_required')->default(true)->index()->after('password');

            // role gating (admin/customer)
            if (!Schema::hasColumn('users', 'role')) {
                $table->string('role', 20)->default('customer')->index()->after('email');
            }
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table) {
            if (Schema::hasColumn('users', 'fuel_business_id')) {
                $table->dropUnique(['fuel_business_id']);
                $table->dropColumn('fuel_business_id');
            }
            if (Schema::hasColumn('users', 'password_reset_required')) {
                $table->dropIndex(['password_reset_required']);
                $table->dropColumn('password_reset_required');
            }
            if (Schema::hasColumn('users', 'role')) {
                $table->dropIndex(['role']);
                $table->dropColumn('role');
            }
        });
    }
};
