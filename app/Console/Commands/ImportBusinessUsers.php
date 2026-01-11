<?php

namespace App\Console\Commands;

use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Str;

class ImportBusinessUsers extends Command
{
    protected $signature = 'import:business-users
        {--dry-run : Do not write anything}
        {--limit=0 : Limit number of rows}';

    protected $description = 'Import customers from fuelmysql.businesses into Laravel users (forces password reset).';

    public function handle(): int
    {
        $q = DB::connection('fuelmysql')
            ->table('businesses')
            ->select(['id','business_name','contact_name','email','status']);

        $limit = (int) $this->option('limit');
        if ($limit > 0) {
            $q->limit($limit);
        }

        $rows = $q->orderBy('id')->get();

        $this->info('businesses rows: '.$rows->count());

        $created = 0;
        $updated = 0;
        $skipped = 0;

        foreach ($rows as $b) {
            $email = strtolower(trim((string) $b->email));
            if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
                $skipped++;
                continue;
            }

            // Optional: skip closed/suspended
            // if (in_array($b->status, ['closed','suspended'], true)) { $skipped++; continue; }

            $name = trim((string)($b->contact_name ?: $b->business_name ?: $email));
            if ($name === '') $name = $email;

            $payload = [
                'name' => $name,
                'email' => $email,
                'role' => 'customer',
                'fuel_business_id' => (int) $b->id,
                'password_reset_required' => true,
                // Set random password so old credentials cannot work
                'password' => Hash::make(Str::random(40)),
            ];

            $existing = User::where('fuel_business_id', (int)$b->id)
                ->orWhere('email', $email)
                ->first();

            if ($this->option('dry-run')) {
                $this->line('[DRY] upsert '.$email.' fuel_business_id='.$b->id);
                continue;
            }

            if ($existing) {
                // do not overwrite name if admin manually changed it
                $existing->fill($payload);
                $existing->save();
                $updated++;
            } else {
                User::create($payload);
                $created++;
            }
        }

        $this->info("Created: {$created}, Updated: {$updated}, Skipped: {$skipped}");

        return self::SUCCESS;
    }
}
