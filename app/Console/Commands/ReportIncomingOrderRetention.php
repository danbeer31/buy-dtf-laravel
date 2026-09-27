<?php

namespace App\Console\Commands;

use App\Models\ApiAssetRecord;
use Illuminate\Console\Command;

class ReportIncomingOrderRetention extends Command
{
    protected $signature = 'incoming-orders:retention-report {--json : Emit a machine-readable dry-run report}';

    protected $description = 'Report future API assets eligible for retention cleanup without deleting anything';

    public function handle(): int
    {
        $candidates = ApiAssetRecord::query()
            ->where('origin', 'incoming_order_v1')
            ->where('retention_policy', 'expirable')
            ->where('retention_enabled', true)
            ->whereNotNull('expires_at')
            ->where('expires_at', '<=', now())
            ->whereNull('purged_at')
            ->orderBy('id')
            ->get();

        $report = [
            'mode' => 'report_only',
            'global_retention_enabled' => (bool) config('incoming_order.retention.enabled', false),
            'candidate_rows' => $candidates->count(),
            'candidate_files' => $candidates->pluck('asset_path')->unique()->count(),
            'candidate_bytes' => (int) $candidates->sum(fn (ApiAssetRecord $asset): int => (int) ($asset->bytes ?? 0)),
            'candidates' => $candidates->map(fn (ApiAssetRecord $asset): array => [
                'asset_record_id' => $asset->id,
                'incoming_order_job_id' => $asset->incoming_order_job_id,
                'asset_role' => $asset->asset_role,
                'asset_path' => $asset->asset_path,
                'bytes' => (int) ($asset->bytes ?? 0),
                'expires_at' => $asset->expires_at?->toIso8601String(),
            ])->all(),
        ];

        if ($this->option('json')) {
            $this->line(json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR));

            return self::SUCCESS;
        }

        $this->info('Incoming-order retention is report-only; no files or rows were changed.');
        $this->line('Global retention enabled: '.($report['global_retention_enabled'] ? 'yes' : 'no'));
        $this->line('Candidate rows: '.$report['candidate_rows']);
        $this->line('Candidate files: '.$report['candidate_files']);
        $this->line('Candidate bytes: '.$report['candidate_bytes']);
        foreach ($report['candidates'] as $candidate) {
            $this->line(sprintf(
                '#%d job=%d role=%s bytes=%d path=%s',
                $candidate['asset_record_id'],
                $candidate['incoming_order_job_id'],
                $candidate['asset_role'],
                $candidate['bytes'],
                $candidate['asset_path'],
            ));
        }

        return self::SUCCESS;
    }
}
