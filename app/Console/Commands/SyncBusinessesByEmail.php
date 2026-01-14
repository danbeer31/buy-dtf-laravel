<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;

class SyncBusinessesByEmail extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'app:sync-businesses';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Verification command to see if users and businesses match by email';

    /**
     * Execute the console command.
     */
    public function handle()
    {
        $this->info('Starting verification...');

        $users = \App\Models\User::all();
        $this->info("Found {$users->count()} users.");

        $matchCount = 0;

        foreach ($users as $user) {
            if (empty($user->email)) {
                continue;
            }

            $business = \App\Models\Business::where('email', $user->email)->first();

            if ($business) {
                $this->line("Match found: <info>{$user->email}</info> (User ID: {$user->id}, Business ID: {$business->id})");
                $matchCount++;
            } else {
                $this->error("No match for user: {$user->email}");
            }
        }

        $this->info("Finished. Total matches found: {$matchCount}");
    }
}
