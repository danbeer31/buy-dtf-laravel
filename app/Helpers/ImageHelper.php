<?php

namespace App\Helpers;

use Imagick;
use ImagickPixel;

class ImageHelper
{
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
        $physCrc = (int) sprintf('%u', crc32($physType . $physData));
        $physChunk = pack('N', strlen($physData)) . $physType . $physData . pack('N', $physCrc);

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
            if (!$inserted && $type === 'IHDR') {
                $out .= $physChunk;
                $inserted = true;
            }

            $offset += $chunkTotal;
        }

        if (!$inserted) {
            return ['success' => false, 'message' => 'IHDR not found in PNG'];
        }

        $ok = @file_put_contents($file, $out);
        return ($ok !== false) ? ['success' => true] : ['success' => false, 'message' => 'Failed to write PNG pHYs chunk'];
    }

    protected static function trimTransparentBorderGd(string $inputFile, int $guard = 2, int $leave = 0): array
    {
        if (!function_exists('imagecreatefromstring')) {
            return ['success' => false, 'message' => 'GD not available for trim fallback'];
        }

        $raw = @file_get_contents($inputFile);
        if ($raw === false) {
            return ['success' => false, 'message' => 'Unable to read file bytes for GD trim'];
        }

        $src = @imagecreatefromstring($raw);
        if (!$src) {
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
                    if ($x < $minX) $minX = $x;
                    if ($y < $minY) $minY = $y;
                    if ($x > $maxX) $maxX = $x;
                    if ($y > $maxY) $maxY = $y;
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
        if (!$dst) {
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
    protected static function prepareForProductionWithGd(string $inputFile, string $outputFile, int $widthPx, int $heightPx, int $dpi = 300): array
    {
        if (!function_exists('imagecreatefromstring') || !function_exists('imagecreatetruecolor')) {
            return ['success' => false, 'message' => 'GD extension not available'];
        }

        $srcInfo = @getimagesize($inputFile);
        if (!is_array($srcInfo) || !isset($srcInfo[0], $srcInfo[1])) {
            return ['success' => false, 'message' => 'Unable to read source image dimensions'];
        }

        $srcPixels = (int)$srcInfo[0] * (int)$srcInfo[1];
        $dstPixels = (int)$widthPx * (int)$heightPx;
        $maxPixels = (int)env('PRODUCTION_GD_MAX_PIXELS', 75000000);
        if ($srcPixels > $maxPixels || $dstPixels > $maxPixels) {
            return ['success' => false, 'message' => 'GD fallback pixel budget exceeded'];
        }

        $raw = @file_get_contents($inputFile);
        if ($raw === false) {
            return ['success' => false, 'message' => 'Failed to read source image bytes'];
        }

        $src = @imagecreatefromstring($raw);
        if (!$src) {
            return ['success' => false, 'message' => 'GD could not decode source image'];
        }

        $dst = imagecreatetruecolor($widthPx, $heightPx);
        if (!$dst) {
            imagedestroy($src);
            return ['success' => false, 'message' => 'GD could not allocate destination image'];
        }

        imagealphablending($dst, false);
        imagesavealpha($dst, true);
        $transparent = imagecolorallocatealpha($dst, 0, 0, 0, 127);
        imagefilledrectangle($dst, 0, 0, $widthPx, $heightPx, $transparent);

        $okResize = imagecopyresized(
            $dst,
            $src,
            0,
            0,
            0,
            0,
            $widthPx,
            $heightPx,
            imagesx($src),
            imagesy($src)
        );

        $okWrite = $okResize ? imagepng($dst, $outputFile, 9) : false;

        imagedestroy($src);
        imagedestroy($dst);

        if (!$okWrite) {
            return ['success' => false, 'message' => 'GD failed to write output PNG'];
        }

        $phys = self::upsertPngPhysChunk($outputFile, $dpi, $dpi);
        if (!($phys['success'] ?? false)) {
            return ['success' => false, 'message' => 'GD wrote PNG but failed to set pHYs: ' . ($phys['message'] ?? 'Unknown error')];
        }

        return ['success' => true, 'fallback' => 'gd'];
    }

    /**
     * Trim transparent border from PNG/GIF with alpha.
     */
    public static function trimTransparentBorder(string $inputFile, int $guard = 2, int $leave = 0): array
    {
        if (!extension_loaded('imagick')) {
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

            if (!$im->getImageAlphaChannel()) {
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
                return ['success' => false, 'message' => 'Imagick trim failed; GD fallback failed: ' . ($gd['message'] ?? 'Unknown error')];
            }
            return ['success' => false, 'message' => 'Exception: '.$msg];
        }
    }

    /**
     * Hard-threshold the alpha channel.
     */
    public static function thresholdAlphaMask(string $inputFile, int $threshold = 128): array
    {
        if (!extension_loaded('imagick')) {
            return ['success' => false, 'message' => 'Imagick extension not available.'];
        }

        try {
            $img = new Imagick($inputFile);
            self::normalizeCmykToRgb($img);

            if (!$img->getImageAlphaChannel()) {
                $img->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            }

            $lvl = max(0, min(255, $threshold)) / 255.0;
            $img->evaluateImage(Imagick::EVALUATE_THRESHOLD, $lvl, Imagick::CHANNEL_ALPHA);

            $img->setImageFormat('png');
            $img->setOption('png:color-type', '6'); // RGBA

            $ok = $img->writeImage($inputFile);
            $img->clear();
            $img->destroy();

            return $ok ? ['success' => true] : ['success' => false];
        } catch (\Exception $e) {
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Set PNG DPI (pHYs)
     */
    public static function setPngDpi(string $file, int $dpiX, int $dpiY): array
    {
        if (!extension_loaded('imagick')) {
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
            $im->setImageProperty('density', max(1, $dpiX) . 'x' . max(1, $dpiY));
            $ok = $im->writeImage($file);
            $im->clear();
            $im->destroy();
            return $ok ? ['success' => true] : ['success' => false];
        } catch (\Exception $e) {
            $fallback = self::upsertPngPhysChunk($file, $dpiX, $dpiY);
            if ($fallback['success'] ?? false) {
                return ['success' => true, 'fallback' => 'png_chunk'];
            }
            return ['success' => false, 'message' => $e->getMessage() . '; fallback failed: ' . ($fallback['message'] ?? 'Unknown error')];
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
        ?int $alphaThreshold = null
    ): array
    {
        if (!extension_loaded('imagick')) {
            return ['success' => false, 'message' => 'Imagick not available'];
        }

        $widthPx = max(1, (int) round($widthIn * $dpi));
        $heightPx = max(1, (int) round($heightIn * $dpi));
        $allowFallback = (bool)filter_var(env('PRODUCTION_PREP_ALLOW_FALLBACK', true), FILTER_VALIDATE_BOOL);

        try {
            $im = new Imagick($inputFile);

            // Ensure alpha channel exists
            if (!$im->getImageAlphaChannel()) {
                $im->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            }

            // Set Resolution/DPI
            $im->setImageUnits(Imagick::RESOLUTION_PIXELSPERINCH);
            $im->setImageResolution($dpi, $dpi);
            $im->setImageProperty('png:pHYs', "x={$dpi},y={$dpi},units=1");

            // Hard-edge resize: nearest-neighbor / point sampling (no anti-aliasing).
            if (defined('\Imagick::INTERPOLATE_NEARESTNEIGHBOR')) {
                $im->setImageInterpolateMethod(\Imagick::INTERPOLATE_NEARESTNEIGHBOR);
            }
            $im->resizeImage($widthPx, $heightPx, Imagick::FILTER_POINT, 1);

            // Optional alpha hard-threshold only when explicitly requested.
            if ($alphaThreshold !== null) {
                $level = max(0, min(255, (int) $alphaThreshold)) / 255.0;
                $im->evaluateImage(Imagick::EVALUATE_THRESHOLD, $level, Imagick::CHANNEL_ALPHA);
            }

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

            return $ok ? ['success' => true] : ['success' => false, 'message' => 'Failed to write image'];
        } catch (\Exception $e) {
            $message = $e->getMessage();
            $isCacheError = stripos($message, 'cache resources exhausted') !== false;
            $isReadError = stripos($message, 'Failed to read the file') !== false;
            if ($allowFallback && ($isCacheError || $isReadError)) {
                $gd = self::prepareForProductionWithGd($inputFile, $outputFile, $widthPx, $heightPx, $dpi);
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
     * Generate a thumbnail for an image.
     */
    public static function generateThumbnail(string $inputFile, string $outputFile, int $maxWidth = 300, int $maxHeight = 300): array
    {
        if (!extension_loaded('imagick')) {
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

            return ['success' => false, 'message' => $e->getMessage() . '; GD fallback failed: ' . ($gd['message'] ?? 'Unknown error')];
        }
    }

    protected static function generateThumbnailWithGd(string $inputFile, string $outputFile, int $maxWidth = 300, int $maxHeight = 300): array
    {
        if (!function_exists('imagecreatefromstring') || !function_exists('imagecreatetruecolor')) {
            return ['success' => false, 'message' => 'GD extension not available'];
        }

        $srcInfo = @getimagesize($inputFile);
        if (!is_array($srcInfo) || empty($srcInfo[0]) || empty($srcInfo[1])) {
            return ['success' => false, 'message' => 'Unable to read source image dimensions'];
        }

        $srcW = (int)$srcInfo[0];
        $srcH = (int)$srcInfo[1];
        $scale = min($maxWidth / $srcW, $maxHeight / $srcH, 1);
        $dstW = max(1, (int)round($srcW * $scale));
        $dstH = max(1, (int)round($srcH * $scale));

        $raw = @file_get_contents($inputFile);
        if ($raw === false) {
            return ['success' => false, 'message' => 'Failed to read source image bytes'];
        }

        $src = @imagecreatefromstring($raw);
        if (!$src) {
            return ['success' => false, 'message' => 'GD could not decode source image'];
        }

        $dst = imagecreatetruecolor($dstW, $dstH);
        if (!$dst) {
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
}
