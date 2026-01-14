<?php

namespace App\Helpers;

use Imagick;
use ImagickPixel;

class ImageHelper
{
    /**
     * Trim transparent border from PNG/GIF with alpha.
     */
    public static function trimTransparentBorder(string $inputFile, int $guard = 2, int $leave = 0): array
    {
        if (!extension_loaded('imagick')) {
            return ['success' => false, 'message' => 'Imagick not available'];
        }

        try {
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
            return ['success' => false, 'message' => 'Exception: '.$e->getMessage()];
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
            $img->setImageColorspace(Imagick::COLORSPACE_RGB);

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
        if (!extension_loaded('imagick')) return ['success' => false, 'message' => 'Imagick not available'];

        try {
            $im = new Imagick($file);
            $im->setImageFormat('png');
            $im->setImageColorspace(Imagick::COLORSPACE_RGB);
            $im->setOption('png:color-type', '6'); // RGBA
            $im->setImageUnits(Imagick::RESOLUTION_PIXELSPERINCH);
            $im->setImageResolution(max(1, $dpiX), max(1, $dpiY));
            $im->setImageProperty('density', max(1, $dpiX) . 'x' . max(1, $dpiY));
            $ok = $im->writeImage($file);
            $im->clear();
            $im->destroy();
            return $ok ? ['success' => true] : ['success' => false];
        } catch (\Exception $e) {
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }
}
