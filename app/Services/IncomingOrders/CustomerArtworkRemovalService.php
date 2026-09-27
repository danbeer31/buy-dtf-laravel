<?php

namespace App\Services\IncomingOrders;

use App\Models\ApiAssetRecord;
use App\Models\Business;
use App\Models\CustomerArtworkRemoval;
use App\Models\DtfImage;
use App\Models\SavedImage;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use RuntimeException;

class CustomerArtworkRemovalService
{
    /** @return Collection<int, string> */
    public function hiddenPaths(int $businessId): Collection
    {
        if (! $this->tableExists()) {
            return collect();
        }

        return CustomerArtworkRemoval::query()
            ->where('business_id', $businessId)
            ->pluck('asset_path')
            ->filter(fn ($path): bool => is_string($path) && $path !== '')
            ->values();
    }

    public function requestRemoval(Business $business, DtfImage $image): CustomerArtworkRemoval
    {
        if ((int) $image->dtfOrder?->business_id !== (int) $business->id) {
            throw new RuntimeException('Artwork does not belong to this business.');
        }

        $path = (string) $image->image;
        if ($path === '') {
            throw new RuntimeException('Artwork path is unavailable.');
        }
        $pathHash = hash('sha256', $path);
        $connection = (string) config('database.fuel_connection');

        $removal = DB::connection($connection)->transaction(function () use (
            $business,
            $image,
            $path,
            $pathHash,
        ): CustomerArtworkRemoval {
            $record = CustomerArtworkRemoval::query()->updateOrCreate(
                [
                    'business_id' => $business->id,
                    'path_hash' => $pathHash,
                ],
                [
                    'asset_path' => $path,
                    'thumbnail_path' => $image->thumbnail,
                    'state' => 'requested',
                    'deferred_reason' => null,
                    'customer_deleted_at' => now(),
                    'purged_at' => null,
                ],
            );

            SavedImage::query()
                ->where('business_id', $business->id)
                ->where('image', $path)
                ->delete();

            return $record;
        });

        return $this->attemptPhysicalPurge($removal);
    }

    public function attemptPhysicalPurge(CustomerArtworkRemoval $removal): CustomerArtworkRemoval
    {
        if (! (bool) config('incoming_order.customer_artwork.physical_purge_enabled', false)) {
            return $this->defer($removal, 'physical_purge_disabled');
        }

        $path = (string) $removal->asset_path;
        $pathHash = (string) $removal->path_hash;
        $businessId = (int) $removal->business_id;

        if (ApiAssetRecord::query()
            ->where('path_hash', $pathHash)
            ->whereNull('purged_at')
            ->exists()) {
            return $this->defer($removal, 'api_managed_asset');
        }

        $activeReference = DtfImage::query()
            ->where('image', $path)
            ->whereHas('dtfOrder', fn ($query) => $query->whereIn('status', [1, 2, 3]))
            ->exists();
        if ($activeReference) {
            return $this->defer($removal, 'active_reference');
        }

        $otherBusinessReference = DtfImage::query()
            ->where('image', $path)
            ->whereHas('dtfOrder', fn ($query) => $query->where('business_id', '<>', $businessId))
            ->exists()
            || SavedImage::query()
                ->where('image', $path)
                ->where('business_id', '<>', $businessId)
                ->exists();
        if ($otherBusinessReference) {
            return $this->defer($removal, 'shared_reference');
        }

        $thumbnail = (string) ($removal->thumbnail_path ?? '');
        if ($thumbnail !== '' && (
            DtfImage::query()->where('thumbnail', $thumbnail)
                ->whereHas('dtfOrder', fn ($query) => $query->where('business_id', '<>', $businessId))
                ->exists()
            || SavedImage::query()->where('thumbnail', $thumbnail)
                ->where('business_id', '<>', $businessId)
                ->exists()
        )) {
            return $this->defer($removal, 'shared_derivative_reference');
        }

        $this->deletePublicFile($path);
        if ($thumbnail !== '' && $thumbnail !== $path) {
            $this->deletePublicFile($thumbnail);
        }

        $removal->forceFill([
            'state' => 'purged',
            'deferred_reason' => null,
            'purged_at' => now(),
        ])->save();

        return $removal->fresh();
    }

    private function defer(CustomerArtworkRemoval $removal, string $reason): CustomerArtworkRemoval
    {
        $removal->forceFill([
            'state' => 'deferred',
            'deferred_reason' => $reason,
            'purged_at' => null,
        ])->save();

        return $removal->fresh();
    }

    private function deletePublicFile(string $relativePath): void
    {
        $urlPath = parse_url($relativePath, PHP_URL_PATH);
        if (! is_string($urlPath) || $urlPath === '') {
            return;
        }
        $relative = ltrim(str_replace('\\', '/', $urlPath), '/');
        if ($relative === '' || str_contains($relative, '../')) {
            throw new RuntimeException('Artwork path is outside the public asset root.');
        }

        $publicRoot = realpath(public_path());
        $parent = realpath(dirname(public_path($relative)));
        if ($publicRoot === false || $parent === false
            || ($parent !== $publicRoot && ! str_starts_with($parent, $publicRoot.DIRECTORY_SEPARATOR))) {
            throw new RuntimeException('Artwork path is outside the public asset root.');
        }

        $absolute = $parent.DIRECTORY_SEPARATOR.basename($relative);
        if (is_file($absolute) && ! @unlink($absolute)) {
            throw new RuntimeException('Unable to delete customer artwork file.');
        }
    }

    private function tableExists(): bool
    {
        $connection = (string) config('database.fuel_connection');

        return $connection !== '' && Schema::connection($connection)->hasTable('customer_artwork_removals');
    }
}
