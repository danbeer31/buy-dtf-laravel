<?php

namespace App\Console\Commands;

use App\Services\QboAdminSnapshotRefresher;
use App\Services\QboAdminSnapshotStore;
use Illuminate\Console\Command;
use Throwable;

class RefreshQboAdminSnapshots extends Command
{
    protected $signature = 'qbo:refresh-admin-cache {--status : Show the current refresh status}';

    protected $description = 'Refresh cached QBO open invoice balances and invoice history used by admin pages';

    public function handle(QboAdminSnapshotRefresher $refresher, QboAdminSnapshotStore $store): int
    {
        if ($this->option('status')) {
            $this->line(json_encode($store->status(), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        }

        try {
            $result = $refresher->refresh();
        } catch (Throwable $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

        return self::SUCCESS;
    }
}
