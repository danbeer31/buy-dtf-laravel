<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::connection('mysql')->create('business_user', function (Blueprint $table) {
            $table->id();
            $table->unsignedInteger('business_id');
            $table->foreignId('user_id')->constrained('users')->cascadeOnDelete();
            $table->string('role', 20)->default('member');
            $table->boolean('is_active')->default(true);
            $table->unsignedBigInteger('invited_by')->nullable();
            $table->timestamps();

            $table->unique(['business_id', 'user_id']);
            $table->index(['user_id', 'is_active']);
            $table->index(['business_id', 'is_active']);
        });

        $now = now();
        $users = DB::connection('mysql')
            ->table('users')
            ->select(['id', 'email', 'fuel_business_id'])
            ->get();

        foreach ($users as $user) {
            $businessId = $user->fuel_business_id;

            if (!$businessId && !empty($user->email)) {
                $businessId = DB::connection('fuelmysql')
                    ->table('businesses')
                    ->whereRaw('LOWER(email) = ?', [strtolower((string) $user->email)])
                    ->orderBy('id')
                    ->value('id');
            }

            if (!$businessId) {
                continue;
            }

            DB::connection('mysql')->table('business_user')->updateOrInsert(
                [
                    'business_id' => (int) $businessId,
                    'user_id' => (int) $user->id,
                ],
                [
                    'role' => 'owner',
                    'is_active' => 1,
                    'invited_by' => null,
                    'created_at' => $now,
                    'updated_at' => $now,
                ]
            );

            if (!$user->fuel_business_id) {
                DB::connection('mysql')
                    ->table('users')
                    ->where('id', $user->id)
                    ->update(['fuel_business_id' => (int) $businessId]);
            }
        }
    }

    public function down(): void
    {
        Schema::connection('mysql')->dropIfExists('business_user');
    }
};
