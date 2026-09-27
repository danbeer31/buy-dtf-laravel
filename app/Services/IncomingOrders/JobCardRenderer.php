<?php

namespace App\Services\IncomingOrders;

use App\Helpers\ImageHelper;
use Imagick;
use ImagickDraw;
use ImagickPixel;
use RuntimeException;

class JobCardRenderer
{
    /** @return array{ready: bool, reason: string|null, renderer_version: string, font_sha256: string|null, width_px: int, height_px: int, dpi: int} */
    public function readiness(): array
    {
        $dpi = max(72, (int) config('incoming_order.job_card.dpi', 300));
        $widthPx = max(1, (int) round((float) config('incoming_order.job_card.width_in', 5.0) * $dpi));
        $heightPx = max(1, (int) round((float) config('incoming_order.job_card.height_in', 3.0) * $dpi));
        $base = [
            'renderer_version' => (string) config('incoming_order.job_card.renderer_version', 'separate-job-card-v2'),
            'font_sha256' => null,
            'width_px' => $widthPx,
            'height_px' => $heightPx,
            'dpi' => $dpi,
        ];
        if (! extension_loaded('imagick')) {
            return ['ready' => false, 'reason' => 'imagick_unavailable'] + $base;
        }

        try {
            [, $fontHash] = $this->verifiedFont();

            return ['ready' => true, 'reason' => null] + array_merge($base, ['font_sha256' => $fontHash]);
        } catch (RuntimeException) {
            return ['ready' => false, 'reason' => 'pinned_font_unavailable'] + $base;
        }
    }

    /**
     * @param  array<string, mixed>  $metadata
     * @param  callable(): void|null  $heartbeat
     * @return array{relative_path: string, absolute_path: string, sha256: string, bytes: int, width_in: string, height_in: string, renderer_version: string, dpi: int, x_ppm: int, y_ppm: int, font_sha256: string}
     */
    public function render(
        int $jobId,
        string $fingerprint,
        array $metadata,
        int $totalQuantity,
        string $rendererVersion,
        ?string $expectedExistingHash = null,
        ?callable $heartbeat = null,
    ): array {
        if (! extension_loaded('imagick')) {
            throw new RuntimeException('Imagick is required to render production job cards.');
        }

        $supportedVersion = (string) config('incoming_order.job_card.renderer_version', 'separate-job-card-v2');
        if ($rendererVersion === '' || ! hash_equals($supportedVersion, $rendererVersion)) {
            throw new RuntimeException('The frozen job-card renderer version is not available.');
        }

        [$font, $fontHash] = $this->verifiedFont();
        $widthIn = (float) config('incoming_order.job_card.width_in', 5.0);
        $heightIn = (float) config('incoming_order.job_card.height_in', 3.0);
        $dpi = max(72, (int) config('incoming_order.job_card.dpi', 300));
        $widthPx = max(1, (int) round($widthIn * $dpi));
        $heightPx = max(1, (int) round($heightIn * $dpi));
        $relative = sprintf(
            'incoming-orders/job-cards/%d/%s-q%d.png',
            $jobId,
            $fingerprint,
            max(1, $totalQuantity),
        );
        $absolute = storage_path('app/private/'.$relative);
        $directory = dirname($absolute);
        if (! is_dir($directory) && ! mkdir($directory, 0770, true) && ! is_dir($directory)) {
            throw new RuntimeException('Unable to create job-card asset directory.');
        }

        $heartbeat && $heartbeat();
        $reuse = is_string($expectedExistingHash)
            && preg_match('/^[a-f0-9]{64}$/D', $expectedExistingHash)
            && is_file($absolute)
            && hash_equals($expectedExistingHash, (string) hash_file('sha256', $absolute));

        if (! $reuse) {
            $temporary = $absolute.'.'.bin2hex(random_bytes(8)).'.tmp.png';
            try {
                $this->drawCard(
                    $temporary,
                    $metadata,
                    $totalQuantity,
                    $widthPx,
                    $heightPx,
                    $dpi,
                    $font,
                    $heartbeat,
                );
                $this->publishAtomically($temporary, $absolute);
                @chmod($absolute, 0640);
            } finally {
                @unlink($temporary);
            }
        }

        $heartbeat && $heartbeat();
        $dimensions = @getimagesize($absolute);
        $hash = hash_file('sha256', $absolute);
        $bytes = filesize($absolute);
        $resolution = ImageHelper::pngResolution($absolute);
        $expectedPpm = (int) round($dpi * 39.3700787402);
        if (! is_array($dimensions)
            || (int) $dimensions[0] !== $widthPx
            || (int) $dimensions[1] !== $heightPx
            || ! is_string($hash)
            || $bytes === false
            || ! is_array($resolution)
            || $resolution['unit'] !== 1
            || $resolution['x_ppm'] !== $expectedPpm
            || $resolution['y_ppm'] !== $expectedPpm) {
            throw new RuntimeException('Rendered job-card verification failed.');
        }

        if (is_string($expectedExistingHash) && ! hash_equals($expectedExistingHash, $hash)) {
            throw new RuntimeException('Frozen job-card hash changed.');
        }

        return [
            'relative_path' => $relative,
            'absolute_path' => $absolute,
            'sha256' => $hash,
            'bytes' => (int) $bytes,
            'width_in' => number_format($widthIn, 4, '.', ''),
            'height_in' => number_format($heightIn, 4, '.', ''),
            'renderer_version' => $rendererVersion,
            'dpi' => $dpi,
            'x_ppm' => $resolution['x_ppm'],
            'y_ppm' => $resolution['y_ppm'],
            'font_sha256' => $fontHash,
        ];
    }

    /**
     * @param  array<string, mixed>  $metadata
     * @param  callable(): void|null  $heartbeat
     */
    private function drawCard(
        string $path,
        array $metadata,
        int $totalQuantity,
        int $width,
        int $height,
        int $dpi,
        string $font,
        ?callable $heartbeat,
    ): void {
        $image = new Imagick;
        try {
            $image->newImage($width, $height, new ImagickPixel('white'), 'png');
            $image->setImageUnits(Imagick::RESOLUTION_PIXELSPERINCH);
            $image->setImageResolution($dpi, $dpi);

            $border = new ImagickDraw;
            $border->setStrokeColor(new ImagickPixel('#111111'));
            $border->setStrokeWidth(8);
            $border->setFillColor(new ImagickPixel('transparent'));
            $border->rectangle(12, 12, $width - 12, $height - 12);
            $image->drawImage($border);

            $draw = new ImagickDraw;
            $draw->setFont($font);
            $draw->setFillColor(new ImagickPixel('#111111'));
            $left = 48;
            $right = $width - 48;
            $maximumWidth = $right - $left;

            $draw->setFontWeight(700);
            $draw->setFontSize(42);
            $title = 'PRODUCTION JOB CARD';
            if (! $this->fits($image, $draw, $title, $maximumWidth)) {
                throw new RuntimeException('Job-card title does not fit.');
            }
            $image->annotateImage($draw, $left, 70, 0, $title);

            $fields = [
                'Order' => '#'.(string) $metadata['order_number'],
                'Product' => (string) $metadata['product_name'],
                'SKU' => ($metadata['product_sku'] ?? null) !== null
                    ? (string) $metadata['product_sku']
                    : 'N/A',
                'Color' => (string) $metadata['color'],
                'Size' => (string) $metadata['size'],
                'Placement' => (string) $metadata['placement'],
                'Shop' => (string) $metadata['shop_domain'],
            ];
            [$fontSize, $lineHeight, $lines] = $this->layoutFields(
                $image,
                $draw,
                $fields,
                $maximumWidth,
                150,
                $height - 145,
            );

            $draw->setFontWeight(400);
            $draw->setFontSize($fontSize);
            $y = 150;
            foreach ($lines as $line) {
                if (! $this->fits($image, $draw, $line, $maximumWidth)) {
                    throw new RuntimeException('Job-card line exceeds its safe printable width.');
                }
                $image->annotateImage($draw, $left, $y, 0, $line);
                $y += $lineHeight;
                $heartbeat && $heartbeat();
            }

            $draw->setFontWeight(700);
            $draw->setFontSize(54);
            $quantityText = 'TOTAL QTY: '.max(1, $totalQuantity);
            $metrics = $image->queryFontMetrics($draw, $quantityText);
            $quantityWidth = (float) ($metrics['textWidth'] ?? 0);
            if ($quantityWidth > $maximumWidth || $y > $height - 145) {
                throw new RuntimeException('Job-card content does not fit the configured physical size.');
            }
            $quantityX = max($left, (int) ($right - $quantityWidth));
            $image->annotateImage($draw, $quantityX, $height - 65, 0, $quantityText);

            $image->setImageFormat('png');
            $image->setOption('png:color-type', '6');
            $image->setOption('png:compression-level', '9');
            $image->stripImage();
            if (! $image->writeImage($path)) {
                throw new RuntimeException('Unable to write production job card.');
            }
        } finally {
            $image->clear();
            $image->destroy();
        }

        $dpiResult = ImageHelper::setPngDpi($path, $dpi, $dpi);
        if (! ($dpiResult['success'] ?? false)) {
            throw new RuntimeException('Unable to write production job-card DPI metadata.');
        }
        $heartbeat && $heartbeat();
    }

    /**
     * @param  array<string, string>  $fields
     * @return array{0: int, 1: int, 2: list<string>}
     */
    private function layoutFields(
        Imagick $image,
        ImagickDraw $draw,
        array $fields,
        float $maximumWidth,
        int $top,
        int $bottom,
    ): array {
        foreach ([32, 30, 28, 26, 24, 22, 20] as $fontSize) {
            $draw->setFontWeight(400);
            $draw->setFontSize($fontSize);
            $lineHeight = (int) ceil($fontSize * 1.45);
            $lines = [];
            foreach ($fields as $label => $value) {
                foreach ($this->wrap($image, $draw, $label.': '.$value, $maximumWidth) as $line) {
                    $lines[] = $line;
                }
            }

            if ($top + (count($lines) * $lineHeight) <= $bottom) {
                return [$fontSize, $lineHeight, $lines];
            }
        }

        throw new RuntimeException('Job-card content exceeds the accepted layout limits.');
    }

    /** @return list<string> */
    private function wrap(Imagick $image, ImagickDraw $draw, string $text, float $maximumWidth): array
    {
        $words = preg_split('/\s+/u', trim($text), -1, PREG_SPLIT_NO_EMPTY) ?: [];
        $lines = [];
        $line = '';
        foreach ($words as $word) {
            $candidate = $line === '' ? $word : $line.' '.$word;
            if ($this->fits($image, $draw, $candidate, $maximumWidth)) {
                $line = $candidate;

                continue;
            }

            if ($line !== '') {
                $lines[] = $line;
                $line = '';
            }

            if ($this->fits($image, $draw, $word, $maximumWidth)) {
                $line = $word;

                continue;
            }

            $segments = $this->splitGraphemesToWidth($image, $draw, $word, $maximumWidth);
            while (count($segments) > 1) {
                $lines[] = array_shift($segments);
            }
            $line = $segments[0] ?? '';
        }

        if ($line !== '') {
            $lines[] = $line;
        }

        return $lines;
    }

    /** @return list<string> */
    private function splitGraphemesToWidth(
        Imagick $image,
        ImagickDraw $draw,
        string $word,
        float $maximumWidth,
    ): array {
        preg_match_all('/\X/u', $word, $matches);
        $graphemes = $matches[0] ?? [];
        if ($graphemes === []) {
            throw new RuntimeException('Job-card text contains an invalid grapheme sequence.');
        }

        $segments = [];
        $segment = '';
        foreach ($graphemes as $grapheme) {
            $candidate = $segment.$grapheme;
            if ($segment !== '' && ! $this->fits($image, $draw, $candidate, $maximumWidth)) {
                $segments[] = $segment;
                $segment = $grapheme;
            } else {
                $segment = $candidate;
            }
            if (! $this->fits($image, $draw, $segment, $maximumWidth)) {
                throw new RuntimeException('A job-card grapheme exceeds the printable width.');
            }
        }
        if ($segment !== '') {
            $segments[] = $segment;
        }

        return $segments;
    }

    private function fits(Imagick $image, ImagickDraw $draw, string $text, float $maximumWidth): bool
    {
        $metrics = $image->queryFontMetrics($draw, $text);

        return (float) ($metrics['textWidth'] ?? PHP_FLOAT_MAX) <= $maximumWidth;
    }

    /** @return array{0: string, 1: string} */
    private function verifiedFont(): array
    {
        $path = (string) config('incoming_order.job_card.font', '');
        $expectedHash = strtolower((string) config('incoming_order.job_card.font_sha256', ''));
        if ($path === '' || ! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException('The pinned job-card font is unavailable.');
        }
        if (! preg_match('/^[a-f0-9]{64}$/D', $expectedHash)) {
            throw new RuntimeException('The pinned job-card font hash is invalid.');
        }
        $actualHash = hash_file('sha256', $path);
        if (! is_string($actualHash) || ! hash_equals($expectedHash, $actualHash)) {
            throw new RuntimeException('The pinned job-card font hash does not match.');
        }

        return [$path, $actualHash];
    }

    private function publishAtomically(string $temporary, string $absolute): void
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

        // Production uses one Linux filesystem; rename replaces the target in
        // one operation. If the platform cannot do that, fail closed.
        if (! @rename($temporary, $absolute)) {
            throw new RuntimeException('Unable to atomically finalize job-card image.');
        }
    }
}
