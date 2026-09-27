<?php

namespace App\Services\IncomingOrders;

use App\Helpers\ImageHelper;
use App\Helpers\ProductionHelper;
use App\Models\ApiAssetRecord;
use App\Models\DtfImage;
use App\Models\IncomingOrderJob;
use Carbon\CarbonImmutable;
use Illuminate\Database\Eloquent\Collection as EloquentCollection;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;
use Throwable;

class ApiProductionHandoffService
{
    public function __construct(private readonly JobCardRenderer $jobCardRenderer) {}

    /**
     * @param  EloquentCollection<int, DtfImage>  $groupRows
     * @return array<string, mixed>
     */
    public function handoff(EloquentCollection $groupRows, int $totalQuantity): array
    {
        $groupRows->loadMissing('incomingOrderJob');
        $representative = $groupRows->first();
        if (! $representative) {
            throw new RuntimeException('Production group is empty.');
        }

        $jobs = $groupRows->map(fn (DtfImage $image) => $image->incomingOrderJob)->filter()->values();
        if ($jobs->count() !== $groupRows->count()
            || $jobs->contains(fn (IncomingOrderJob $job) => ! $job->hasAcceptedJobCard())) {
            throw new RuntimeException('Production group has incomplete job-card metadata.');
        }

        $fingerprints = $jobs->pluck('job_label_fingerprint')->unique()->values();
        if ($fingerprints->count() !== 1) {
            throw new RuntimeException('Production group contains different job-card metadata.');
        }
        $rendererVersions = $jobs->pluck('renderer_version')->filter()->unique()->values();
        if ($rendererVersions->count() !== 1) {
            throw new RuntimeException('Production group contains incompatible job-card renderer versions.');
        }
        $fingerprint = (string) $fingerprints->first();
        $rendererVersion = (string) $rendererVersions->first();
        $metadata = $jobs->first()->job_label_metadata;
        if (! is_array($metadata)) {
            throw new RuntimeException('Frozen job-card metadata is unavailable.');
        }

        $dimensions = $jobs->map(fn (IncomingOrderJob $job): string => $job->art_width_in.'x'.$job->art_height_in)
            ->unique()
            ->values();
        if ($dimensions->count() !== 1) {
            throw new RuntimeException('Production group contains different frozen artwork dimensions.');
        }
        $artWidth = (float) $jobs->first()->art_width_in;
        $artHeight = (float) $jobs->first()->art_height_in;
        $frozenTotalQuantity = (int) $jobs->sum(function (IncomingOrderJob $job): int {
            $jobMetadata = $job->job_label_metadata;

            return is_array($jobMetadata) ? max(0, (int) ($jobMetadata['quantity'] ?? 0)) : 0;
        });
        if ($artWidth <= 0 || $artHeight <= 0 || $frozenTotalQuantity < 1) {
            throw new RuntimeException('Frozen production dimensions or quantity are invalid.');
        }
        $totalQuantity = $frozenTotalQuantity;

        $sourceHashes = $jobs->map(function (IncomingOrderJob $job): string {
            return (string) ($job->actual_art_sha256
                ?: $job->original_asset_sha256
                ?: $job->expected_art_sha256);
        })->unique()->values();
        if ($sourceHashes->count() !== 1
            || ! preg_match('/^[a-f0-9]{64}$/D', (string) $sourceHashes->first())) {
            throw new RuntimeException('Frozen source-artwork identity is unavailable or inconsistent.');
        }
        $sourceHash = (string) $sourceHashes->first();
        $expectedCardHash = $this->frozenDerivedHash($jobs, 'job_card_asset_sha256');
        $expectedProductionHash = $this->frozenDerivedHash($jobs, 'normalized_asset_sha256');

        $groupKey = hash('sha256', implode('|', [
            (string) $representative->dtforder_id,
            (string) $representative->image,
            number_format($artWidth, 4, '.', ''),
            number_format($artHeight, 4, '.', ''),
            $sourceHash,
            $fingerprint,
            $rendererVersion,
            (string) max(1, $totalQuantity),
        ]));
        $connection = (string) config('database.fuel_connection');
        $jobIds = $jobs->pluck('id')->map(fn ($id): int => (int) $id)->sort()->values()->all();
        $owner = (string) Str::uuid();
        $leaseSeconds = max(30, (int) config('incoming_order.job_card.production_lease_seconds', 300));

        DB::connection($connection)->transaction(function () use (
            $jobIds,
            $groupKey,
            $owner,
            $leaseSeconds,
            $connection,
        ): void {
            $now = $this->databaseNow($connection);
            $lockedJobs = IncomingOrderJob::query()
                ->whereIn('id', $jobIds)
                ->orderBy('id')
                ->lockForUpdate()
                ->get();
            if ($lockedJobs->count() !== count($jobIds)) {
                throw new RuntimeException('Production group changed before handoff.');
            }

            if ($lockedJobs->contains(fn (IncomingOrderJob $job): bool => $job->production_state === 'processing'
                && $job->production_lease_expires_at !== null
                && $job->production_lease_expires_at->greaterThan($now))) {
                throw new RuntimeException('Production handoff is already processing.');
            }

            $affected = IncomingOrderJob::query()->whereIn('id', $jobIds)->update([
                'production_state' => 'processing',
                'production_group_key' => $groupKey,
                'production_owner' => $owner,
                'production_attempt_count' => DB::raw('production_attempt_count + 1'),
                'production_started_at' => $now,
                'production_heartbeat_at' => $now,
                'production_lease_expires_at' => $now->addSeconds($leaseSeconds),
                'production_completed_at' => null,
                'last_error_code' => null,
                'updated_at' => $now,
            ]);
            if ($affected !== count($jobIds)) {
                throw new RuntimeException('Production group could not be claimed atomically.');
            }
        }, 3);

        $heartbeat = function () use (
            $jobIds,
            $owner,
            $groupKey,
            $connection,
            $leaseSeconds,
        ): void {
            $now = $this->databaseNow($connection);
            $affected = IncomingOrderJob::query()
                ->whereIn('id', $jobIds)
                ->where('production_state', 'processing')
                ->where('production_owner', $owner)
                ->where('production_group_key', $groupKey)
                ->update([
                    'production_heartbeat_at' => $now,
                    'production_lease_expires_at' => $now->addSeconds($leaseSeconds),
                    'updated_at' => $now,
                ]);
            if ($affected !== count($jobIds)) {
                throw new RuntimeException('Production handoff claim was lost.');
            }
        };

        try {
            $heartbeat();
            $productionArt = $this->buildProductionArtwork(
                $representative,
                $groupKey,
                $artWidth,
                $artHeight,
                $sourceHash,
                $expectedProductionHash,
                $heartbeat,
            );
            $card = $this->jobCardRenderer->render(
                (int) $jobs->first()->id,
                $fingerprint,
                $metadata,
                max(1, $totalQuantity),
                $rendererVersion,
                $expectedCardHash,
                $heartbeat,
            );

            $sourceBase = pathinfo(basename((string) $representative->image), PATHINFO_FILENAME);
            $sourceBase = $sourceBase !== '' ? $sourceBase : 'artwork';
            $correlation = substr($groupKey, 0, 12);

            $artworkResult = ProductionHelper::addToProduction($representative, [
                'quantity' => max(1, $totalQuantity),
                'mark_production' => false,
                'prepared_image_path' => $productionArt['absolute_path'],
                'width_in' => $artWidth,
                'height_in' => $artHeight,
                'remote_image_name' => sprintf('%s--art-%s.png', $sourceBase, $correlation),
                'heartbeat' => $heartbeat,
            ]);

            $cardBase = sprintf(
                '%d-%s--job-card-%s',
                $representative->id,
                $sourceBase,
                $correlation,
            );
            $cardResult = ProductionHelper::addCompanionArtifact(
                $card['absolute_path'],
                $cardBase,
                (float) $card['width_in'],
                (float) $card['height_in'],
                ['heartbeat' => $heartbeat],
            );

            $result = [
                'artwork_remote_paths' => array_values((array) ($artworkResult['uploaded_paths'] ?? [])),
                'job_card_remote_paths' => array_values((array) ($cardResult['uploaded_paths'] ?? [])),
                'job_card_quantity' => 1,
                'total_artwork_quantity' => max(1, $totalQuantity),
                'renderer_version' => $card['renderer_version'],
                'job_card_sha256' => $card['sha256'],
                'production_artwork_sha256' => $productionArt['sha256'],
                'job_card_dpi' => $card['dpi'],
                'job_card_font_sha256' => $card['font_sha256'],
            ];

            DB::connection($connection)->transaction(function () use (
                $jobIds,
                $owner,
                $groupKey,
                $card,
                $productionArt,
                $result,
                $connection,
            ): void {
                $now = $this->databaseNow($connection);
                $lockedJobs = IncomingOrderJob::query()
                    ->whereIn('id', $jobIds)
                    ->orderBy('id')
                    ->lockForUpdate()
                    ->get();
                if ($lockedJobs->count() !== count($jobIds)
                    || $lockedJobs->contains(fn (IncomingOrderJob $job): bool => $job->production_state !== 'processing'
                        || ! hash_equals((string) $job->production_owner, $owner)
                        || ! hash_equals((string) $job->production_group_key, $groupKey))) {
                    throw new RuntimeException('Production handoff claim was lost before completion.');
                }

                $affected = IncomingOrderJob::query()
                    ->whereIn('id', $jobIds)
                    ->where('production_state', 'processing')
                    ->where('production_owner', $owner)
                    ->where('production_group_key', $groupKey)
                    ->update([
                        'job_label_status' => 'rendered',
                        'job_card_asset_path' => $card['relative_path'],
                        'job_card_asset_sha256' => $card['sha256'],
                        'normalized_asset_path' => $productionArt['relative_path'],
                        'normalized_asset_sha256' => $productionArt['sha256'],
                        'production_state' => 'completed',
                        'production_owner' => null,
                        'production_heartbeat_at' => null,
                        'production_lease_expires_at' => null,
                        'production_result' => json_encode($result, JSON_THROW_ON_ERROR),
                        'production_completed_at' => $now,
                        'last_error_code' => null,
                        'updated_at' => $now,
                    ]);
                if ($affected !== count($jobIds)) {
                    throw new RuntimeException('Production handoff completion lost ownership.');
                }

                foreach ($lockedJobs as $job) {
                    $this->recordAsset($job, 'production_artwork', $productionArt);
                    $this->recordAsset($job, 'job_card', $card);
                }
            }, 3);

            return $result;
        } catch (Throwable $exception) {
            $now = $this->databaseNow($connection);
            IncomingOrderJob::query()
                ->whereIn('id', $jobIds)
                ->where('production_state', 'processing')
                ->where('production_owner', $owner)
                ->where('production_group_key', $groupKey)
                ->update([
                    'production_state' => 'retryable_failure',
                    'production_owner' => null,
                    'production_heartbeat_at' => null,
                    'production_lease_expires_at' => null,
                    'last_error_code' => 'job_card_handoff_failed',
                    'updated_at' => $now,
                ]);
            throw $exception;
        }
    }

    /**
     * @param  callable(): void  $heartbeat
     * @return array{relative_path: string, absolute_path: string, sha256: string, bytes: int}
     */
    private function buildProductionArtwork(
        DtfImage $image,
        string $groupKey,
        float $widthIn,
        float $heightIn,
        string $expectedSourceHash,
        ?string $expectedExistingHash,
        callable $heartbeat,
    ): array {
        $relative = sprintf('incoming-orders/production/%d/%s.png', $image->id, $groupKey);
        $absolute = storage_path('app/private/'.$relative);
        $directory = dirname($absolute);
        if (! is_dir($directory) && ! mkdir($directory, 0770, true) && ! is_dir($directory)) {
            throw new RuntimeException('Unable to create production-artwork directory.');
        }

        $source = public_path(ltrim((string) $image->image, '/'));
        if (! is_file($source)) {
            throw new RuntimeException('Immutable source artwork is missing.');
        }
        $heartbeat();
        $sourceHashBefore = hash_file('sha256', $source);
        if (! is_string($sourceHashBefore) || ! hash_equals($expectedSourceHash, $sourceHashBefore)) {
            throw new RuntimeException('Immutable source artwork hash does not match the frozen job.');
        }

        $reuse = is_string($expectedExistingHash)
            && preg_match('/^[a-f0-9]{64}$/D', $expectedExistingHash)
            && is_file($absolute)
            && hash_equals($expectedExistingHash, (string) hash_file('sha256', $absolute));
        if (! $reuse) {
            $temporary = $absolute.'.'.bin2hex(random_bytes(8)).'.tmp.png';
            try {
                $prepared = ImageHelper::prepareForProductionAspectSafe(
                    $source,
                    $temporary,
                    $widthIn,
                    $heightIn,
                    300,
                );
                if (! ($prepared['success'] ?? false)) {
                    throw new RuntimeException('Unable to generate aspect-safe production artwork.');
                }
                $heartbeat();
                $sourceHashAfter = hash_file('sha256', $source);
                if (! is_string($sourceHashAfter) || ! hash_equals($expectedSourceHash, $sourceHashAfter)) {
                    throw new RuntimeException('Immutable source artwork changed during production preparation.');
                }
                $this->publishAtomically($temporary, $absolute, 'production artwork');
                @chmod($absolute, 0640);
            } finally {
                @unlink($temporary);
            }
        }

        $heartbeat();
        $hash = hash_file('sha256', $absolute);
        $bytes = filesize($absolute);
        if (! is_string($hash) || $bytes === false) {
            throw new RuntimeException('Production artwork verification failed.');
        }
        if (is_string($expectedExistingHash) && ! hash_equals($expectedExistingHash, $hash)) {
            throw new RuntimeException('Frozen production artwork hash changed.');
        }

        return [
            'relative_path' => $relative,
            'absolute_path' => $absolute,
            'sha256' => $hash,
            'bytes' => (int) $bytes,
        ];
    }

    /**
     * @param  EloquentCollection<int, IncomingOrderJob>  $jobs
     */
    private function frozenDerivedHash(EloquentCollection $jobs, string $column): ?string
    {
        $hashes = $jobs->pluck($column)->filter()->unique()->values();
        if ($hashes->count() > 1) {
            throw new RuntimeException('Frozen production derivative identities are inconsistent.');
        }
        if ($hashes->isEmpty()) {
            return null;
        }

        $hash = (string) $hashes->first();
        if (! preg_match('/^[a-f0-9]{64}$/D', $hash)) {
            throw new RuntimeException('Frozen production derivative identity is invalid.');
        }

        return $hash;
    }

    private function publishAtomically(string $temporary, string $absolute, string $description): void
    {
        if (is_file($absolute)) {
            $temporaryHash = hash_file('sha256', $temporary);
            $existingHash = hash_file('sha256', $absolute);
            if (is_string($temporaryHash)
                && is_string($existingHash)
                && hash_equals($temporaryHash, $existingHash)) {
                return;
            }
        }

        if (! @rename($temporary, $absolute)) {
            throw new RuntimeException("Unable to atomically finalize {$description}.");
        }
    }

    private function databaseNow(string $connection): CarbonImmutable
    {
        $database = DB::connection($connection);
        $sql = $database->getDriverName() === 'mysql'
            ? 'SELECT UTC_TIMESTAMP(6) AS current_time'
            : 'SELECT CURRENT_TIMESTAMP AS current_time';
        $row = $database->selectOne($sql);
        $value = is_object($row) ? ($row->current_time ?? null) : null;

        return CarbonImmutable::parse((string) $value, 'UTC')->utc();
    }

    /** @param array<string, mixed> $asset */
    private function recordAsset(IncomingOrderJob $job, string $role, array $asset): void
    {
        $path = (string) $asset['relative_path'];
        ApiAssetRecord::query()->updateOrCreate(
            [
                'incoming_order_job_id' => $job->id,
                'asset_role' => $role,
                'path_hash' => hash('sha256', $path),
            ],
            [
                'dtfimage_id' => $job->dtfimage_id,
                'origin' => 'incoming_order_v1',
                'storage_scope' => 'private',
                'asset_path' => $path,
                'sha256' => $asset['sha256'],
                'bytes' => $asset['bytes'],
                'retention_policy' => 'forever',
                'retention_enabled' => false,
                'retention_days' => null,
                'expires_at' => null,
            ],
        );
    }
}
