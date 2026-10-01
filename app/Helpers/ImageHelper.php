<?php

namespace App\Helpers;

use Imagick;
use ImagickPixel;

class ImageHelper
{
    private const DEFAULT_ALPHA_THRESHOLD = 128;

    protected static function upsertPngPhysChunk(string $file, int $dpiX, int $dpiY): array
    {
        $bytes = @file_get_contents($file);
        if ($bytes === false || strlen($bytes) < 8) {
            return ['success' => false, 'message' => 'Unable to read PNG bytes'];
        }

        $pngSig = "\x89PNG\x0D\x0A\x1A\x0A";
        if (substr($bytes, 0, 8) !== $pngSig) {
            return ['success' => false, 'message' => 'Not a PNG file'];
        }

        $ppmX = max(1, (int) round($dpiX * 39.3700787402));
        $ppmY = max(1, (int) round($dpiY * 39.3700787402));
        $physData = pack('NNC', $ppmX, $ppmY, 1);
        $physType = 'pHYs';
        $physCrc = (int) sprintf('%u', crc32($physType.$physData));
        $physChunk = pack('N', strlen($physData)).$physType.$physData.pack('N', $physCrc);

        $out = substr($bytes, 0, 8);
        $offset = 8;
        $inserted = false;

        while ($offset + 8 <= strlen($bytes)) {
            $len = unpack('N', substr($bytes, $offset, 4))[1];
            $type = substr($bytes, $offset + 4, 4);
            $chunkTotal = 12 + $len;
            if ($offset + $chunkTotal > strlen($bytes)) {
                return ['success' => false, 'message' => 'Invalid PNG chunk structure'];
            }

            // Skip existing pHYs; we'll insert one canonical chunk.
            if ($type !== 'pHYs') {
                $out .= substr($bytes, $offset, $chunkTotal);
            }

            // Insert pHYs immediately after IHDR.
            if (! $inserted && $type === 'IHDR') {
                $out .= $physChunk;
                $inserted = true;
            }

            $offset += $chunkTotal;
        }

        if (! $inserted) {
            return ['success' => false, 'message' => 'IHDR not found in PNG'];
        }

        $ok = @file_put_contents($file, $out);

        return ($ok !== false) ? ['success' => true] : ['success' => false, 'message' => 'Failed to write PNG pHYs chunk'];
    }

    /** @return array{x_ppm: int, y_ppm: int, unit: int, x_dpi: float, y_dpi: float}|null */
    public static function pngResolution(string $file): ?array
    {
        $bytes = @file_get_contents($file);
        if (! is_string($bytes) || substr($bytes, 0, 8) !== "\x89PNG\x0D\x0A\x1A\x0A") {
            return null;
        }

        $offset = 8;
        $length = strlen($bytes);
        while ($offset + 12 <= $length) {
            $chunkLength = unpack('Nlength', substr($bytes, $offset, 4));
            $chunkLength = is_array($chunkLength) ? (int) $chunkLength['length'] : -1;
            $type = substr($bytes, $offset + 4, 4);
            if ($chunkLength < 0 || $offset + 12 + $chunkLength > $length) {
                return null;
            }
            if ($type === 'pHYs' && $chunkLength === 9) {
                $values = unpack('Nx/Ny/Cunit', substr($bytes, $offset + 8, 9));
                if (! is_array($values)) {
                    return null;
                }

                return [
                    'x_ppm' => (int) $values['x'],
                    'y_ppm' => (int) $values['y'],
                    'unit' => (int) $values['unit'],
                    'x_dpi' => (float) $values['x'] / 39.3700787402,
                    'y_dpi' => (float) $values['y'] / 39.3700787402,
                ];
            }

            $offset += 12 + $chunkLength;
        }

        return null;
    }

    protected static function trimTransparentBorderGd(string $inputFile, int $guard = 2, int $leave = 0): array
    {
        if (! function_exists('imagecreatefromstring')) {
            return ['success' => false, 'message' => 'GD not available for trim fallback'];
        }

        $raw = @file_get_contents($inputFile);
        if ($raw === false) {
            return ['success' => false, 'message' => 'Unable to read file bytes for GD trim'];
        }

        $src = @imagecreatefromstring($raw);
        if (! $src) {
            return ['success' => false, 'message' => 'GD could not decode image'];
        }

        $w = imagesx($src);
        $h = imagesy($src);
        if ($w <= 0 || $h <= 0) {
            imagedestroy($src);

            return ['success' => false, 'message' => 'Invalid source dimensions for GD trim'];
        }

        $minX = $w;
        $minY = $h;
        $maxX = -1;
        $maxY = -1;

        for ($y = 0; $y < $h; $y++) {
            for ($x = 0; $x < $w; $x++) {
                $rgba = imagecolorat($src, $x, $y);
                $alpha = ($rgba >> 24) & 0x7F;
                if ($alpha < 127) {
                    if ($x < $minX) {
                        $minX = $x;
                    }
                    if ($y < $minY) {
                        $minY = $y;
                    }
                    if ($x > $maxX) {
                        $maxX = $x;
                    }
                    if ($y > $maxY) {
                        $maxY = $y;
                    }
                }
            }
        }

        if ($maxX < 0 || $maxY < 0) {
            imagedestroy($src);

            return ['success' => true, 'message' => 'Fully transparent image; nothing to trim'];
        }

        $minX = max(0, $minX - $leave);
        $minY = max(0, $minY - $leave);
        $maxX = min($w - 1, $maxX + $leave);
        $maxY = min($h - 1, $maxY + $leave);

        $newW = max(1, $maxX - $minX + 1);
        $newH = max(1, $maxY - $minY + 1);

        $dst = imagecreatetruecolor($newW, $newH);
        if (! $dst) {
            imagedestroy($src);

            return ['success' => false, 'message' => 'GD could not allocate destination image'];
        }

        imagealphablending($dst, false);
        imagesavealpha($dst, true);
        $transparent = imagecolorallocatealpha($dst, 0, 0, 0, 127);
        imagefilledrectangle($dst, 0, 0, $newW, $newH, $transparent);
        imagecopy($dst, $src, 0, 0, $minX, $minY, $newW, $newH);

        if ($guard > 0) {
            $guardW = $newW + ($guard * 2);
            $guardH = $newH + ($guard * 2);
            $guarded = imagecreatetruecolor($guardW, $guardH);
            if ($guarded) {
                imagealphablending($guarded, false);
                imagesavealpha($guarded, true);
                $t2 = imagecolorallocatealpha($guarded, 0, 0, 0, 127);
                imagefilledrectangle($guarded, 0, 0, $guardW, $guardH, $t2);
                imagecopy($guarded, $dst, $guard, $guard, 0, 0, $newW, $newH);
                imagedestroy($dst);
                $dst = $guarded;
            }
        }

        $ok = imagepng($dst, $inputFile, 9);
        imagedestroy($src);
        imagedestroy($dst);

        return $ok ? ['success' => true, 'message' => 'Trimmed with GD fallback'] : ['success' => false, 'message' => 'GD could not write trimmed PNG'];
    }

    /**
     * Lightweight fallback resize path using GD when Imagick cache is exhausted.
     * Uses nearest-neighbor style scaling via imagecopyresized to preserve hard edges.
     */
    protected static function prepareForProductionWithGd(
        string $inputFile,
        string $outputFile,
        int $widthPx,
        int $heightPx,
        int $dpi = 300,
        ?int $alphaThreshold = null
    ): array {
        if (! function_exists('imagecreatefromstring') || ! function_exists('imagecreatetruecolor')) {
            return ['success' => false, 'message' => 'GD extension not available'];
        }

        $srcInfo = @getimagesize($inputFile);
        if (! is_array($srcInfo) || ! isset($srcInfo[0], $srcInfo[1])) {
            return ['success' => false, 'message' => 'Unable to read source image dimensions'];
        }

        $srcPixels = (int) $srcInfo[0] * (int) $srcInfo[1];
        $dstPixels = (int) $widthPx * (int) $heightPx;
        $maxPixels = (int) env('PRODUCTION_GD_MAX_PIXELS', 75000000);
        if ($srcPixels > $maxPixels || $dstPixels > $maxPixels) {
            return ['success' => false, 'message' => 'GD fallback pixel budget exceeded'];
        }

        $raw = @file_get_contents($inputFile);
        if ($raw === false) {
            return ['success' => false, 'message' => 'Failed to read source image bytes'];
        }

        $src = @imagecreatefromstring($raw);
        if (! $src) {
            return ['success' => false, 'message' => 'GD could not decode source image'];
        }

        $resizeSource = $src;
        $sourceBounds = null;
        if ($alphaThreshold !== null) {
            $sourceBounds = self::gdVisibleBounds($src, $alphaThreshold);
            if ($sourceBounds === null) {
                imagedestroy($src);

                return [
                    'success' => false,
                    'reason' => 'fully_transparent_image',
                    'message' => 'Artwork contains no pixels at or above the alpha threshold.',
                ];
            }

            $resizeSource = self::gdThresholdedCrop($src, $sourceBounds, $alphaThreshold);
            if (! $resizeSource) {
                imagedestroy($src);

                return ['success' => false, 'message' => 'GD could not create the thresholded source crop'];
            }
        }

        $dst = imagecreatetruecolor($widthPx, $heightPx);
        if (! $dst) {
            if ($resizeSource !== $src) {
                imagedestroy($resizeSource);
            }
            imagedestroy($src);

            return ['success' => false, 'message' => 'GD could not allocate destination image'];
        }

        imagealphablending($dst, false);
        imagesavealpha($dst, true);
        $transparent = imagecolorallocatealpha($dst, 0, 0, 0, 127);
        imagefilledrectangle($dst, 0, 0, $widthPx, $heightPx, $transparent);

        $okResize = imagecopyresized(
            $dst,
            $resizeSource,
            0,
            0,
            0,
            0,
            $widthPx,
            $heightPx,
            imagesx($resizeSource),
            imagesy($resizeSource)
        );

        $okWrite = $okResize ? imagepng($dst, $outputFile, 9) : false;

        if ($resizeSource !== $src) {
            imagedestroy($resizeSource);
        }
        imagedestroy($src);
        imagedestroy($dst);

        if (! $okWrite) {
            return ['success' => false, 'message' => 'GD failed to write output PNG'];
        }

        $phys = self::upsertPngPhysChunk($outputFile, $dpi, $dpi);
        if (! ($phys['success'] ?? false)) {
            return ['success' => false, 'message' => 'GD wrote PNG but failed to set pHYs: '.($phys['message'] ?? 'Unknown error')];
        }

        return [
            'success' => true,
            'fallback' => 'gd',
            'source_bounds' => $sourceBounds,
        ];
    }

    /**
     * Return the printable bounds after applying the production alpha policy.
     * This method never modifies the source file.
     *
     * @return array{success: bool, x?: int, y?: int, width?: int, height?: int, renderer?: string, reason?: string, message?: string}
     */
    public static function productionAlphaBounds(
        string $inputFile,
        int $threshold = self::DEFAULT_ALPHA_THRESHOLD,
        ?string $renderer = null
    ): array {
        $renderer = self::validatedRenderer($renderer);
        if ($renderer === null) {
            return ['success' => false, 'message' => 'Unsupported image renderer.'];
        }

        if ($renderer === 'gd' || ($renderer === 'auto' && ! extension_loaded('imagick'))) {
            return self::productionAlphaBoundsWithGd($inputFile, $threshold);
        }

        try {
            $image = new Imagick($inputFile);
            self::normalizeCmykToRgb($image);
            if (! $image->getImageAlphaChannel()) {
                $image->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            }
            self::applyImagickAlphaThreshold($image, $threshold);
            $bounds = self::imagickVisibleBounds($image);
            $image->clear();
            $image->destroy();

            if ($bounds === null) {
                return [
                    'success' => false,
                    'reason' => 'fully_transparent_image',
                    'message' => 'Artwork contains no pixels at or above the alpha threshold.',
                ];
            }

            return ['success' => true, 'renderer' => 'imagick'] + $bounds;
        } catch (\Throwable $exception) {
            if ($renderer === 'imagick') {
                return ['success' => false, 'message' => $exception->getMessage()];
            }

            $fallback = self::productionAlphaBoundsWithGd($inputFile, $threshold);
            if ($fallback['success'] ?? false) {
                return $fallback;
            }

            return [
                'success' => false,
                'message' => $exception->getMessage().'; GD fallback failed: '.($fallback['message'] ?? 'Unknown error'),
            ];
        }
    }

    /**
     * Trim transparent border from PNG/GIF with alpha.
     */
    public static function trimTransparentBorder(string $inputFile, int $guard = 2, int $leave = 0): array
    {
        if (! extension_loaded('imagick')) {
            return ['success' => false, 'message' => 'Imagick not available'];
        }

        try {
            if (defined('\Imagick::RESOURCETYPE_MEMORY')) {
                Imagick::setResourceLimit(Imagick::RESOURCETYPE_MEMORY, (int) (1024 * 1024 * 1024));
            }
            if (defined('\Imagick::RESOURCETYPE_MAP')) {
                Imagick::setResourceLimit(Imagick::RESOURCETYPE_MAP, (int) (2 * 1024 * 1024 * 1024));
            }
            if (defined('\Imagick::RESOURCETYPE_DISK')) {
                Imagick::setResourceLimit(Imagick::RESOURCETYPE_DISK, (int) (8 * 1024 * 1024 * 1024));
            }

            $im = new Imagick($inputFile);

            if (! $im->getImageAlphaChannel()) {
                $im->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            }

            $im->setImageBackgroundColor(new ImagickPixel('transparent'));
            $im->borderImage(new ImagickPixel('transparent'), $guard, $guard);

            $im->trimImage(0);
            $im->setImagePage(0, 0, 0, 0);

            if ($leave > 0) {
                $im->borderImage(new ImagickPixel('transparent'), $leave, $leave);
            }

            $im->stripImage();
            $im->writeImage($inputFile);
            $im->clear();
            $im->destroy();

            return ['success' => true, 'message' => 'Trimmed safely with guard border'];
        } catch (\Exception $e) {
            $msg = (string) $e->getMessage();
            $cacheOrReadFail = stripos($msg, 'cache resources exhausted') !== false
                || stripos($msg, 'Failed to read the file') !== false;
            if ($cacheOrReadFail) {
                $gd = self::trimTransparentBorderGd($inputFile, $guard, $leave);
                if ($gd['success'] ?? false) {
                    return $gd;
                }

                return ['success' => false, 'message' => 'Imagick trim failed; GD fallback failed: '.($gd['message'] ?? 'Unknown error')];
            }

            return ['success' => false, 'message' => 'Exception: '.$msg];
        }
    }

    /**
     * Hard-threshold the alpha channel.
     */
    public static function thresholdAlphaMask(
        string $inputFile,
        int $threshold = self::DEFAULT_ALPHA_THRESHOLD,
        ?string $renderer = null
    ): array {
        $renderer = self::validatedRenderer($renderer);
        if ($renderer === null) {
            return ['success' => false, 'message' => 'Unsupported image renderer.'];
        }
        if ($renderer === 'gd' || ($renderer === 'auto' && ! extension_loaded('imagick'))) {
            return self::thresholdAlphaMaskWithGd($inputFile, $threshold);
        }

        try {
            $img = new Imagick($inputFile);
            self::normalizeCmykToRgb($img);

            if (! $img->getImageAlphaChannel()) {
                $img->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            }

            self::applyImagickAlphaThreshold($img, $threshold);

            $img->setImageFormat('png');
            $img->setOption('png:color-type', '6'); // RGBA

            $ok = $img->writeImage($inputFile);
            $img->clear();
            $img->destroy();

            return $ok ? ['success' => true] : ['success' => false];
        } catch (\Throwable $e) {
            if ($renderer === 'imagick') {
                return ['success' => false, 'message' => $e->getMessage()];
            }

            $fallback = self::thresholdAlphaMaskWithGd($inputFile, $threshold);
            if ($fallback['success'] ?? false) {
                return $fallback;
            }

            return ['success' => false, 'message' => $e->getMessage().'; GD fallback failed: '.($fallback['message'] ?? 'Unknown error')];
        }
    }

    /**
     * Set PNG DPI (pHYs)
     */
    public static function setPngDpi(string $file, int $dpiX, int $dpiY): array
    {
        if (! extension_loaded('imagick')) {
            return self::upsertPngPhysChunk($file, $dpiX, $dpiY);
        }

        try {
            $im = new Imagick($file);
            $im->setImageFormat('png');
            self::normalizeCmykToRgb($im);
            $im->setOption('png:color-type', '6'); // RGBA
            $im->setImageUnits(Imagick::RESOLUTION_PIXELSPERINCH);
            $im->setImageResolution(max(1, $dpiX), max(1, $dpiY));
            $im->setImageProperty('png:pHYs', "x={$dpiX},y={$dpiY},units=1");
            $im->setImageProperty('density', max(1, $dpiX).'x'.max(1, $dpiY));
            $ok = $im->writeImage($file);
            $im->clear();
            $im->destroy();
            if (! $ok) {
                return ['success' => false];
            }

            // ImageMagick builds differ in whether resolution properties are
            // serialized as a PNG pHYs chunk. Canonicalize the bytes so every
            // renderer and RIP sees the same physical resolution.
            return self::upsertPngPhysChunk($file, $dpiX, $dpiY);
        } catch (\Exception $e) {
            $fallback = self::upsertPngPhysChunk($file, $dpiX, $dpiY);
            if ($fallback['success'] ?? false) {
                return ['success' => true, 'fallback' => 'png_chunk'];
            }

            return ['success' => false, 'message' => $e->getMessage().'; fallback failed: '.($fallback['message'] ?? 'Unknown error')];
        }
    }

    /**
     * Prepare image for production in hard-edge mode:
     * - nearest-neighbor resize (no anti-aliasing)
     * - 300 DPI metadata
     * - optional alpha threshold if explicitly requested
     */
    public static function prepareForProduction(
        string $inputFile,
        string $outputFile,
        float $widthIn,
        float $heightIn,
        int $dpi = 300,
        ?int $alphaThreshold = null,
        ?string $renderer = null
    ): array {
        $widthPx = max(1, (int) round($widthIn * $dpi));
        $heightPx = max(1, (int) round($heightIn * $dpi));
        $allowFallback = (bool) filter_var(env('PRODUCTION_PREP_ALLOW_FALLBACK', true), FILTER_VALIDATE_BOOL);
        $renderer = self::validatedRenderer($renderer);
        if ($renderer === null) {
            return ['success' => false, 'message' => 'Unsupported image renderer.'];
        }
        if ($renderer === 'gd' || ($renderer === 'auto' && ! extension_loaded('imagick'))) {
            return self::prepareForProductionWithGd(
                $inputFile,
                $outputFile,
                $widthPx,
                $heightPx,
                $dpi,
                $alphaThreshold
            );
        }

        try {
            $im = new Imagick($inputFile);
            self::normalizeCmykToRgb($im);

            // Ensure alpha channel exists
            if (! $im->getImageAlphaChannel()) {
                $im->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            }

            $sourceBounds = null;
            if ($alphaThreshold !== null) {
                // Apply the hard threshold to the derived image only, before
                // cropping, so discarded edge pixels cannot leave padding.
                self::applyImagickAlphaThreshold($im, $alphaThreshold);
                $sourceBounds = self::imagickVisibleBounds($im);
                if ($sourceBounds === null) {
                    $im->clear();
                    $im->destroy();

                    return [
                        'success' => false,
                        'reason' => 'fully_transparent_image',
                        'message' => 'Artwork contains no pixels at or above the alpha threshold.',
                    ];
                }
                $im->cropImage(
                    $sourceBounds['width'],
                    $sourceBounds['height'],
                    $sourceBounds['x'],
                    $sourceBounds['y']
                );
                $im->setImagePage(0, 0, 0, 0);
            }

            // Hard-edge resize: nearest-neighbor / point sampling (no anti-aliasing).
            if (defined('\Imagick::INTERPOLATE_NEARESTNEIGHBOR')) {
                $im->setImageInterpolateMethod(\Imagick::INTERPOLATE_NEARESTNEIGHBOR);
            }
            $im->resizeImage($widthPx, $heightPx, Imagick::FILTER_POINT, 1);

            // Ensure PNG32/RGBA
            $im->setImageFormat('png');
            $im->setOption('png:color-type', '6');
            $im->setOption('png:compression-level', '9');

            // Set Resolution again right before writing, and ensure we use PixelsPerInch
            $im->setImageUnits(Imagick::RESOLUTION_PIXELSPERINCH);
            $im->setImageResolution($dpi, $dpi);
            $im->setImageProperty('png:pHYs', "x={$dpi},y={$dpi},units=1");

            $ok = $im->writeImage($outputFile);

            $im->clear();
            $im->destroy();

            if (! $ok) {
                return ['success' => false, 'message' => 'Failed to write image'];
            }

            $dpiResult = self::setPngDpi($outputFile, $dpi, $dpi);
            if (! ($dpiResult['success'] ?? false)) {
                return $dpiResult;
            }

            return [
                'success' => true,
                'renderer' => 'imagick',
                'source_bounds' => $sourceBounds,
            ];
        } catch (\Throwable $e) {
            $message = $e->getMessage();
            $isCacheError = stripos($message, 'cache resources exhausted') !== false;
            $isReadError = stripos($message, 'Failed to read the file') !== false;
            if ($renderer === 'auto' && $allowFallback && ($isCacheError || $isReadError)) {
                $gd = self::prepareForProductionWithGd(
                    $inputFile,
                    $outputFile,
                    $widthPx,
                    $heightPx,
                    $dpi,
                    $alphaThreshold
                );
                if ($gd['success'] ?? false) {
                    return [
                        'success' => true,
                        'fallback' => $gd['fallback'] ?? 'gd',
                        'message' => 'Used GD fallback because Imagick could not process the source image',
                    ];
                }
            }

            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Build an exact-size production canvas while uniformly scaling the
     * artwork. Any sub-pixel aspect difference becomes transparent edge
     * padding instead of independent X/Y scaling.
     */
    public static function prepareForProductionAspectSafe(
        string $inputFile,
        string $outputFile,
        float $widthIn,
        float $heightIn,
        int $dpi = 300
    ): array {
        $targetWidth = max(1, (int) round($widthIn * $dpi));
        $targetHeight = max(1, (int) round($heightIn * $dpi));

        if (! extension_loaded('imagick')) {
            return self::prepareForProductionAspectSafeWithGd(
                $inputFile,
                $outputFile,
                $targetWidth,
                $targetHeight,
                $dpi
            );
        }

        try {
            $source = new Imagick($inputFile);
            if ($source->getNumberImages() !== 1) {
                throw new \RuntimeException('Artwork must contain exactly one frame.');
            }
            $source->setIteratorIndex(0);
            self::normalizeCmykToRgb($source);
            if (! $source->getImageAlphaChannel()) {
                $source->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            }

            $sourceWidth = $source->getImageWidth();
            $sourceHeight = $source->getImageHeight();
            if ($sourceWidth < 1 || $sourceHeight < 1) {
                throw new \RuntimeException('Artwork has invalid pixel dimensions.');
            }

            $scale = min($targetWidth / $sourceWidth, $targetHeight / $sourceHeight);
            $scaledWidth = max(1, min($targetWidth, (int) round($sourceWidth * $scale)));
            $scaledHeight = max(1, min($targetHeight, (int) round($sourceHeight * $scale)));

            if (defined('\Imagick::INTERPOLATE_NEARESTNEIGHBOR')) {
                $source->setImageInterpolateMethod(\Imagick::INTERPOLATE_NEARESTNEIGHBOR);
            }
            $source->resizeImage($scaledWidth, $scaledHeight, Imagick::FILTER_POINT, 1);

            $canvas = new Imagick;
            $canvas->newImage($targetWidth, $targetHeight, new ImagickPixel('transparent'), 'png');
            $canvas->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            $canvas->compositeImage(
                $source,
                Imagick::COMPOSITE_OVER,
                intdiv($targetWidth - $scaledWidth, 2),
                intdiv($targetHeight - $scaledHeight, 2)
            );
            $canvas->setImageFormat('png');
            $canvas->setOption('png:color-type', '6');
            $canvas->setOption('png:compression-level', '9');
            $canvas->stripImage();
            $canvas->setImageUnits(Imagick::RESOLUTION_PIXELSPERINCH);
            $canvas->setImageResolution($dpi, $dpi);
            $canvas->setImageProperty('png:pHYs', "x={$dpi},y={$dpi},units=1");
            $ok = $canvas->writeImage($outputFile);

            $source->clear();
            $source->destroy();
            $canvas->clear();
            $canvas->destroy();

            if (! $ok) {
                return ['success' => false, 'message' => 'Failed to write aspect-safe production image'];
            }

            $dpiResult = self::setPngDpi($outputFile, $dpi, $dpi);

            return ($dpiResult['success'] ?? false)
                ? [
                    'success' => true,
                    'canvas_width_px' => $targetWidth,
                    'canvas_height_px' => $targetHeight,
                    'art_width_px' => $scaledWidth,
                    'art_height_px' => $scaledHeight,
                ]
                : $dpiResult;
        } catch (\Throwable $exception) {
            return ['success' => false, 'message' => $exception->getMessage()];
        }
    }

    private static function prepareForProductionAspectSafeWithGd(
        string $inputFile,
        string $outputFile,
        int $targetWidth,
        int $targetHeight,
        int $dpi
    ): array {
        if (! function_exists('imagecreatefromstring') || ! function_exists('imagecreatetruecolor')) {
            return ['success' => false, 'message' => 'No supported image renderer is available'];
        }

        $raw = @file_get_contents($inputFile);
        $source = is_string($raw) ? @imagecreatefromstring($raw) : false;
        if (! $source) {
            return ['success' => false, 'message' => 'GD could not decode source artwork'];
        }

        $sourceWidth = imagesx($source);
        $sourceHeight = imagesy($source);
        if ($sourceWidth < 1 || $sourceHeight < 1) {
            imagedestroy($source);

            return ['success' => false, 'message' => 'Artwork has invalid pixel dimensions'];
        }
        $scale = min($targetWidth / $sourceWidth, $targetHeight / $sourceHeight);
        $scaledWidth = max(1, min($targetWidth, (int) round($sourceWidth * $scale)));
        $scaledHeight = max(1, min($targetHeight, (int) round($sourceHeight * $scale)));

        $canvas = imagecreatetruecolor($targetWidth, $targetHeight);
        if (! $canvas) {
            imagedestroy($source);

            return ['success' => false, 'message' => 'GD could not allocate production canvas'];
        }
        imagealphablending($canvas, false);
        imagesavealpha($canvas, true);
        $transparent = imagecolorallocatealpha($canvas, 0, 0, 0, 127);
        imagefilledrectangle($canvas, 0, 0, $targetWidth, $targetHeight, $transparent);
        $ok = imagecopyresized(
            $canvas,
            $source,
            intdiv($targetWidth - $scaledWidth, 2),
            intdiv($targetHeight - $scaledHeight, 2),
            0,
            0,
            $scaledWidth,
            $scaledHeight,
            $sourceWidth,
            $sourceHeight
        ) && imagepng($canvas, $outputFile, 9);
        imagedestroy($source);
        imagedestroy($canvas);

        if (! $ok) {
            return ['success' => false, 'message' => 'GD failed to write production canvas'];
        }
        $dpiResult = self::upsertPngPhysChunk($outputFile, $dpi, $dpi);

        return ($dpiResult['success'] ?? false)
            ? [
                'success' => true,
                'fallback' => 'gd',
                'canvas_width_px' => $targetWidth,
                'canvas_height_px' => $targetHeight,
                'art_width_px' => $scaledWidth,
                'art_height_px' => $scaledHeight,
            ]
            : $dpiResult;
    }

    /**
     * Generate a thumbnail for an image.
     */
    public static function generateThumbnail(string $inputFile, string $outputFile, int $maxWidth = 300, int $maxHeight = 300): array
    {
        if (! extension_loaded('imagick')) {
            return self::generateThumbnailWithGd($inputFile, $outputFile, $maxWidth, $maxHeight);
        }

        try {
            $im = new Imagick($inputFile);

            // Strip metadata to reduce size
            $im->stripImage();

            // Resize while maintaining aspect ratio
            $im->thumbnailImage($maxWidth, $maxHeight, true);

            // Set format to webp if supported, otherwise stay with original or png
            // For now let's use PNG as it supports transparency which is crucial here
            $im->setImageFormat('png');

            // Optimize PNG
            $im->setOption('png:compression-level', '9');

            $ok = $im->writeImage($outputFile);
            $im->clear();
            $im->destroy();

            return $ok ? ['success' => true] : ['success' => false, 'message' => 'Failed to write thumbnail'];
        } catch (\Exception $e) {
            $gd = self::generateThumbnailWithGd($inputFile, $outputFile, $maxWidth, $maxHeight);
            if ($gd['success'] ?? false) {
                return $gd;
            }

            return ['success' => false, 'message' => $e->getMessage().'; GD fallback failed: '.($gd['message'] ?? 'Unknown error')];
        }
    }

    protected static function generateThumbnailWithGd(string $inputFile, string $outputFile, int $maxWidth = 300, int $maxHeight = 300): array
    {
        if (! function_exists('imagecreatefromstring') || ! function_exists('imagecreatetruecolor')) {
            return ['success' => false, 'message' => 'GD extension not available'];
        }

        $srcInfo = @getimagesize($inputFile);
        if (! is_array($srcInfo) || empty($srcInfo[0]) || empty($srcInfo[1])) {
            return ['success' => false, 'message' => 'Unable to read source image dimensions'];
        }

        $srcW = (int) $srcInfo[0];
        $srcH = (int) $srcInfo[1];
        $scale = min($maxWidth / $srcW, $maxHeight / $srcH, 1);
        $dstW = max(1, (int) round($srcW * $scale));
        $dstH = max(1, (int) round($srcH * $scale));

        $raw = @file_get_contents($inputFile);
        if ($raw === false) {
            return ['success' => false, 'message' => 'Failed to read source image bytes'];
        }

        $src = @imagecreatefromstring($raw);
        if (! $src) {
            return ['success' => false, 'message' => 'GD could not decode source image'];
        }

        $dst = imagecreatetruecolor($dstW, $dstH);
        if (! $dst) {
            imagedestroy($src);

            return ['success' => false, 'message' => 'GD could not allocate thumbnail'];
        }

        imagealphablending($dst, false);
        imagesavealpha($dst, true);
        $transparent = imagecolorallocatealpha($dst, 0, 0, 0, 127);
        imagefilledrectangle($dst, 0, 0, $dstW, $dstH, $transparent);

        $okResize = imagecopyresampled($dst, $src, 0, 0, 0, 0, $dstW, $dstH, $srcW, $srcH);
        $okWrite = $okResize ? imagepng($dst, $outputFile, 9) : false;

        imagedestroy($src);
        imagedestroy($dst);

        return $okWrite
            ? ['success' => true, 'fallback' => 'gd']
            : ['success' => false, 'message' => 'GD failed to write thumbnail'];
    }

    private static function normalizeCmykToRgb(Imagick $image): void
    {
        if ($image->getImageColorspace() === Imagick::COLORSPACE_CMYK) {
            $image->transformImageColorspace(Imagick::COLORSPACE_RGB);
        }
    }

    private static function validatedRenderer(?string $renderer): ?string
    {
        $renderer = strtolower(trim((string) ($renderer ?? 'auto')));

        return in_array($renderer, ['auto', 'imagick', 'gd'], true) ? $renderer : null;
    }

    private static function applyImagickAlphaThreshold(Imagick $image, int $threshold): void
    {
        $threshold = max(1, min(255, $threshold));
        $range = Imagick::getQuantumRange();
        $quantum = (float) ($range['quantumRangeLong'] ?? $range['quantumRangeString'] ?? 65535);
        // EVALUATE_THRESHOLD uses a strict greater-than comparison. Subtract
        // half an 8-bit step so alpha=threshold remains visible.
        $level = max(0.0, ($threshold - 0.5) / 255.0) * $quantum;
        $image->evaluateImage(Imagick::EVALUATE_THRESHOLD, $level, Imagick::CHANNEL_ALPHA);
    }

    /** @return array{x: int, y: int, width: int, height: int}|null */
    private static function imagickVisibleBounds(Imagick $image): ?array
    {
        $range = $image->getImageChannelRange(Imagick::CHANNEL_ALPHA);
        if ((float) ($range['maxima'] ?? 0) <= 0.0) {
            return null;
        }

        // trimImage() collapses a uniform mask to 1x1. A mask whose minimum
        // alpha is non-zero is instead visible across the complete canvas.
        if ((float) ($range['minima'] ?? 0) > 0.0) {
            return [
                'x' => 0,
                'y' => 0,
                'width' => $image->getImageWidth(),
                'height' => $image->getImageHeight(),
            ];
        }

        $mask = clone $image;
        $mask->setImagePage(0, 0, 0, 0);
        $mask->separateImageChannel(Imagick::CHANNEL_ALPHA);
        $mask->setImageBackgroundColor(new ImagickPixel('black'));
        $mask->trimImage(0);
        $page = $mask->getImagePage();
        $bounds = [
            'x' => max(0, (int) ($page['x'] ?? 0)),
            'y' => max(0, (int) ($page['y'] ?? 0)),
            'width' => $mask->getImageWidth(),
            'height' => $mask->getImageHeight(),
        ];
        $mask->clear();
        $mask->destroy();

        return $bounds;
    }

    private static function productionAlphaBoundsWithGd(string $inputFile, int $threshold): array
    {
        if (! function_exists('imagecreatefromstring')) {
            return ['success' => false, 'message' => 'GD extension not available.'];
        }
        $raw = @file_get_contents($inputFile);
        $image = is_string($raw) ? @imagecreatefromstring($raw) : false;
        if (! $image) {
            return ['success' => false, 'message' => 'GD could not decode source artwork.'];
        }
        $bounds = self::gdVisibleBounds($image, $threshold);
        imagedestroy($image);
        if ($bounds === null) {
            return [
                'success' => false,
                'reason' => 'fully_transparent_image',
                'message' => 'Artwork contains no pixels at or above the alpha threshold.',
            ];
        }

        return ['success' => true, 'renderer' => 'gd'] + $bounds;
    }

    /** @return array{x: int, y: int, width: int, height: int}|null */
    private static function gdVisibleBounds(\GdImage $image, int $threshold): ?array
    {
        $threshold = max(1, min(255, $threshold));
        $width = imagesx($image);
        $height = imagesy($image);
        $minX = $width;
        $minY = $height;
        $maxX = -1;
        $maxY = -1;

        for ($y = 0; $y < $height; $y++) {
            for ($x = 0; $x < $width; $x++) {
                if (self::gdOpacity(imagecolorat($image, $x, $y)) < $threshold) {
                    continue;
                }
                $minX = min($minX, $x);
                $minY = min($minY, $y);
                $maxX = max($maxX, $x);
                $maxY = max($maxY, $y);
            }
        }

        if ($maxX < 0 || $maxY < 0) {
            return null;
        }

        return [
            'x' => $minX,
            'y' => $minY,
            'width' => $maxX - $minX + 1,
            'height' => $maxY - $minY + 1,
        ];
    }

    private static function gdThresholdedCrop(\GdImage $source, array $bounds, int $threshold): \GdImage|false
    {
        $crop = imagecreatetruecolor($bounds['width'], $bounds['height']);
        if (! $crop) {
            return false;
        }
        imagealphablending($crop, false);
        imagesavealpha($crop, true);
        $transparent = imagecolorallocatealpha($crop, 0, 0, 0, 127);
        imagefilledrectangle($crop, 0, 0, $bounds['width'], $bounds['height'], $transparent);

        for ($y = 0; $y < $bounds['height']; $y++) {
            for ($x = 0; $x < $bounds['width']; $x++) {
                $rgba = imagecolorat($source, $bounds['x'] + $x, $bounds['y'] + $y);
                $alpha = self::gdOpacity($rgba) >= max(1, min(255, $threshold)) ? 0 : 127;
                imagesetpixel($crop, $x, $y, ($alpha << 24) | ($rgba & 0x00FFFFFF));
            }
        }

        return $crop;
    }

    private static function thresholdAlphaMaskWithGd(string $inputFile, int $threshold): array
    {
        if (! function_exists('imagecreatefromstring')) {
            return ['success' => false, 'message' => 'GD extension not available.'];
        }
        $raw = @file_get_contents($inputFile);
        $source = is_string($raw) ? @imagecreatefromstring($raw) : false;
        if (! $source) {
            return ['success' => false, 'message' => 'GD could not decode source artwork.'];
        }
        $bounds = ['x' => 0, 'y' => 0, 'width' => imagesx($source), 'height' => imagesy($source)];
        $thresholded = self::gdThresholdedCrop($source, $bounds, $threshold);
        imagedestroy($source);
        if (! $thresholded) {
            return ['success' => false, 'message' => 'GD could not allocate thresholded image.'];
        }
        $ok = imagepng($thresholded, $inputFile, 9);
        imagedestroy($thresholded);

        return $ok
            ? ['success' => true, 'fallback' => 'gd']
            : ['success' => false, 'message' => 'GD could not write thresholded image.'];
    }

    private static function gdOpacity(int $rgba): int
    {
        $alpha = ($rgba >> 24) & 0x7F;

        return (int) round((127 - $alpha) * 255 / 127);
    }
}
