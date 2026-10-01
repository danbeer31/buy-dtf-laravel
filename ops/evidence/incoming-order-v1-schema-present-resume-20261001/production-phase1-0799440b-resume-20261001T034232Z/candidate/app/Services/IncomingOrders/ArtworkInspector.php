<?php

namespace App\Services\IncomingOrders;

use App\Exceptions\ArtworkValidationException;
use Imagick;

class ArtworkInspector
{
    public function inspect(FetchedArtwork $fetched): InspectedArtwork
    {
        $sha256 = hash_file('sha256', $fetched->temporaryPath);
        $bytes = filesize($fetched->temporaryPath);
        if (! is_string($sha256) || $bytes === false || $bytes < 1) {
            throw new ArtworkValidationException('artwork_decode_failed');
        }

        $finfo = new \finfo(FILEINFO_MIME_TYPE);
        $mime = strtolower((string) $finfo->file($fetched->temporaryPath));
        $format = match ($mime) {
            'image/png' => 'png',
            'image/jpeg' => 'jpeg',
            'image/webp' => 'webp',
            default => throw new ArtworkValidationException('artwork_format_unsupported'),
        };

        if ($fetched->declaredContentType !== null
            && ! $this->contentTypesAgree($fetched->declaredContentType, $mime)) {
            throw new ArtworkValidationException('artwork_mime_mismatch');
        }

        $dimensions = @getimagesize($fetched->temporaryPath);
        if (! is_array($dimensions) || empty($dimensions[0]) || empty($dimensions[1])) {
            throw new ArtworkValidationException('artwork_decode_failed');
        }
        $width = (int) $dimensions[0];
        $height = (int) $dimensions[1];
        $this->assertPixelLimits($width, $height);
        $this->assertSingleFrame($fetched->temporaryPath, $format);

        return new InspectedArtwork(
            path: $fetched->temporaryPath,
            sha256: $sha256,
            bytes: (int) $bytes,
            format: $format,
            mime: $mime,
            widthPx: $width,
            heightPx: $height,
        );
    }

    public function assertRequestedAspect(InspectedArtwork $artwork, string $widthIn, string $heightIn): void
    {
        $sourceRatio = $artwork->widthPx / $artwork->heightPx;
        $requestedRatio = (float) $widthIn / (float) $heightIn;
        $relativeError = abs(($requestedRatio / $sourceRatio) - 1.0);

        if ($relativeError > (float) config('incoming_order.aspect_ratio_max_relative_error', 0.001)) {
            throw new ArtworkValidationException('artwork_dimension_mismatch');
        }

        $targetWidth = (int) round((float) $widthIn * 300);
        $targetHeight = (int) round((float) $heightIn * 300);
        if ($targetWidth < 1 || $targetHeight < 1
            || $targetWidth * $targetHeight > (int) config('incoming_order.fetch.max_area_px', 100_000_000)) {
            throw new ArtworkValidationException('artwork_limits_exceeded');
        }
    }

    private function assertPixelLimits(int $width, int $height): void
    {
        if ($width > (int) config('incoming_order.fetch.max_width_px', 30_000)
            || $height > (int) config('incoming_order.fetch.max_height_px', 30_000)
            || $width * $height > (int) config('incoming_order.fetch.max_area_px', 100_000_000)) {
            throw new ArtworkValidationException('artwork_limits_exceeded');
        }
    }

    private function assertSingleFrame(string $path, string $format): void
    {
        $prefix = (string) @file_get_contents($path, false, null, 0, 2 * 1024 * 1024);
        if ($format === 'png' && str_contains($prefix, 'acTL')) {
            throw new ArtworkValidationException('artwork_multiple_frames');
        }
        if ($format === 'webp' && (str_contains($prefix, 'ANIM') || str_contains($prefix, 'ANMF'))) {
            throw new ArtworkValidationException('artwork_multiple_frames');
        }

        if (extension_loaded('imagick')) {
            $this->setImagickLimits();
            try {
                $image = new Imagick;
                $image->pingImage($path);
                $frames = $image->getNumberImages();
                $image->clear();
                $image->destroy();
                if ($frames !== 1) {
                    throw new ArtworkValidationException('artwork_multiple_frames');
                }
            } catch (ArtworkValidationException $exception) {
                throw $exception;
            } catch (\Throwable) {
                throw new ArtworkValidationException('artwork_decode_failed');
            }
        }
    }

    private function setImagickLimits(): void
    {
        $limits = [
            'RESOURCETYPE_MEMORY' => 256 * 1024 * 1024,
            'RESOURCETYPE_MAP' => 512 * 1024 * 1024,
            'RESOURCETYPE_DISK' => 1024 * 1024 * 1024,
            'RESOURCETYPE_THREAD' => 2,
            'RESOURCETYPE_TIME' => 30,
        ];
        foreach ($limits as $constant => $limit) {
            $name = Imagick::class.'::'.$constant;
            if (defined($name)) {
                Imagick::setResourceLimit(constant($name), $limit);
            }
        }
    }

    private function contentTypesAgree(string $declared, string $detected): bool
    {
        $declared = match ($declared) {
            'image/jpg', 'image/pjpeg' => 'image/jpeg',
            default => $declared,
        };

        return $declared === $detected;
    }
}
