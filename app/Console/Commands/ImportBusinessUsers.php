<?php

namespace App\Console\Commands;

use App\Models\Business;
use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;

class ImportBusinessUsers extends Command
{
    protected $signature = 'import:business-users
        {--source-connection=fuelmysql : The database connection to read from (old schema)}
        {--target-connection=remotefuel : The database connection to write to (new schema)}
        {--dry-run : Do not write anything}
        {--limit=0 : Limit number of rows}';

    protected $description = 'Import customers from old businesses table into Laravel users and new businesses table.';

    public function handle(): int
    {
        $sourceConn = $this->option('source-connection');
        $targetConn = $this->option('target-connection');

        // Check if source businesses table is fuel_businesses (if we renamed it)
        $sourceTable = 'businesses';
        if (Schema::connection($sourceConn)->hasTable('fuel_businesses')) {
            $sourceTable = 'fuel_businesses';
        }

        $q = DB::connection($sourceConn)
            ->table($sourceTable)
            ->select(['*']);

        $limit = (int) $this->option('limit');
        if ($limit > 0) {
            $q->limit($limit);
        }

        $rows = $q->orderBy('id')->get();

        $this->info("Source table: {$sourceTable} on {$sourceConn}");
        $this->info('Rows to process: '.$rows->count());

        $created = 0;
        $updated = 0;
        $skipped = 0;

        foreach ($rows as $b) {
            $email = strtolower(trim((string) $b->email));
            if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
                $skipped++;
                continue;
            }

            $name = trim((string)($b->contact_name ?: $b->business_name ?: $email));
            if ($name === '') $name = $email;

            $userPayload = [
                'name' => $name,
                'email' => $email,
                'role' => 'customer',
                'fuel_business_id' => (int) $b->id,
                'password_reset_required' => true,
                'password' => Hash::make(Str::random(40)),
            ];

            if ($this->option('dry-run')) {
                $this->line('[DRY] Processing '.$email.' (fuel_id: '.$b->id.')');
                continue;
            }

            $user = User::on($targetConn)->updateOrCreate(
                ['email' => $email],
                $userPayload
            );

            // Now create/update the Business record linked to this user
            $businessPayload = [
                'user_id' => $user->id,
                'business_name' => $b->business_name,
                'contact_name' => $b->contact_name,
                'email' => $email,
                'phone' => $b->phone,
                'address' => $b->address,
                'address2' => $b->address2,
                'city' => $b->city,
                'state' => $b->state,
                'zip' => $b->zip,
                'qbo_customer_id' => $b->qbo_customer_id,
                'status' => $b->status,
                'tax_exempt' => $b->tax_exempt ?? false,
                'tax_number' => $b->tax_number,
                'confirmation_code' => $b->confirmation_code,
                'created_at' => $b->created_at,
                'updated_at' => $b->updated_at,
            ];

            DB::connection($targetConn)->table('businesses')->updateOrInsert(
                ['id' => $b->id],
                $businessPayload
            );

            $created++;
        }

        $this->info("Processed: {$created}, Skipped: {$skipped}");

        return self::SUCCESS;
    }
}
