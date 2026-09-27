<?php

namespace App\Console\Commands;

use App\Models\CustomerArtworkRemoval;
use App\Services\IncomingOrders\CustomerArtworkRemovalService;
use Illuminate\Console\Command;

class ProcessCustomerArtworkRemovals extends Command
{
    protected $signature = 'customer-artwork:process-removals {--execute : Process only when the separately reviewed purge flag is enabled}';

    protected $description = 'Report or safely retry deferred customer artwork removals';

    public function handle(CustomerArtworkRemovalService $service): int
    {
        $records = CustomerArtworkRemoval::query()
            ->whereNull('purged_at')
            ->orderBy('id')
            ->get();
        $execute = (bool) $this->option('execute');
        if ($execute && ! (bool) config('incoming_order.customer_artwork.physical_purge_enabled', false)) {
            $this->error('Physical purge is disabled; nothing was changed.');

            return self::FAILURE;
        }

        $this->line(($execute ? 'Processing' : 'Dry-run reporting').' '.$records->count().' removal record(s).');
        foreach ($records as $record) {
            if ($execute) {
                $record = $service->attemptPhysicalPurge($record);
            }
            $this->line(sprintf(
                '#%d business=%d state=%s reason=%s path=%s',
                $record->id,
                $record->business_id,
                $record->state,
                $record->deferred_reason ?? '-',
                $record->asset_path,
            ));
        }
        $this->info($execute ? 'Processing complete.' : 'Dry run only; no files or rows were changed.');

        return self::SUCCESS;
    }
}
