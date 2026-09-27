<?php

namespace App\Services\IncomingOrders;

use Imagick;
use ImagickDraw;
use ImagickPixel;
use RuntimeException;

class JobCardRenderer
{
    /**
     * @param  array<string, mixed>  $metadata
     * @return array{relative_path: string, absolute_path: string, sha256: string, bytes: int, width_in: string, height_in: string, renderer_version: string}
     */
    public function render(
        int $jobId,
        string $fingerprint,
        array $metadata,
        int $totalQuantity,
        string $rendererVersion,
    ): array {
        if (! extension_loaded('imagick')) {
            throw new RuntimeException('Imagick is required to render production job cards.');
        }

        $supportedVersion = (string) config('incoming_order.job_card.renderer_version', 'separate-job-card-v1');
        if ($rendererVersion === '' || ! hash_equals($supportedVersion, $rendererVersion)) {
            throw new RuntimeException('The frozen job-card renderer version is not available.');
        }

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

        if (! is_file($absolute)) {
            $temporary = $absolute.'.'.bin2hex(random_bytes(8)).'.tmp.png';
            try {
                $this->drawCard($temporary, $metadata, $totalQuantity, $widthPx, $heightPx, $dpi);
                if (! @rename($temporary, $absolute)) {
                    throw new RuntimeException('Unable to finalize job-card image.');
                }
                @chmod($absolute, 0640);
            } finally {
                @unlink($temporary);
            }
        }

        $dimensions = @getimagesize($absolute);
        $hash = hash_file('sha256', $absolute);
        $bytes = filesize($absolute);
        if (! is_array($dimensions)
            || (int) $dimensions[0] !== $widthPx
            || (int) $dimensions[1] !== $heightPx
            || ! is_string($hash)
            || $bytes === false) {
            throw new RuntimeException('Rendered job-card verification failed.');
        }

        return [
            'relative_path' => $relative,
            'absolute_path' => $absolute,
            'sha256' => $hash,
            'bytes' => (int) $bytes,
            'width_in' => number_format($widthIn, 4, '.', ''),
            'height_in' => number_format($heightIn, 4, '.', ''),
            'renderer_version' => $rendererVersion,
        ];
    }

    /** @param array<string, mixed> $metadata */
    private function drawCard(
        string $path,
        array $metadata,
        int $totalQuantity,
        int $width,
        int $height,
        int $dpi,
    ): void {
        $font = $this->fontPath();
        $image = new Imagick;
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
        $y = 70;

        $draw->setFontWeight(700);
        $draw->setFontSize(42);
        $image->annotateImage($draw, $left, $y, 0, 'PRODUCTION JOB CARD');
        $y += 70;

        $draw->setFontSize(38);
        $image->annotateImage($draw, $left, $y, 0, 'ORDER #'.(string) $metadata['order_number']);
        $y += 62;

        $draw->setFontWeight(400);
        $draw->setFontSize(28);
        $lines = [
            'Product: '.(string) $metadata['product_name'],
            'SKU: '.(($metadata['product_sku'] ?? null) !== null ? (string) $metadata['product_sku'] : 'N/A'),
            'Color: '.(string) $metadata['color'].'    Size: '.(string) $metadata['size'],
            'Placement: '.(string) $metadata['placement'],
            'Origin: '.(string) $metadata['shop_domain'],
        ];

        foreach ($lines as $line) {
            foreach ($this->wrap($image, $draw, $line, $right - $left) as $wrapped) {
                $image->annotateImage($draw, $left, $y, 0, $wrapped);
                $y += 42;
            }
        }

        $draw->setFontWeight(700);
        $draw->setFontSize(54);
        $quantityText = 'TOTAL QTY: '.max(1, $totalQuantity);
        $metrics = $image->queryFontMetrics($draw, $quantityText);
        $quantityX = max($left, (int) ($right - ($metrics['textWidth'] ?? 0)));
        $quantityY = $height - 65;
        if ($y > $quantityY - 50) {
            throw new RuntimeException('Job-card content does not fit the configured physical size.');
        }
        $image->annotateImage($draw, $quantityX, $quantityY, 0, $quantityText);

        $image->setImageFormat('png');
        $image->setOption('png:color-type', '6');
        $image->setOption('png:compression-level', '9');
        $image->stripImage();
        $image->setImageUnits(Imagick::RESOLUTION_PIXELSPERINCH);
        $image->setImageResolution($dpi, $dpi);
        $image->setImageProperty('png:pHYs', "x={$dpi},y={$dpi},units=1");
        if (! $image->writeImage($path)) {
            throw new RuntimeException('Unable to write production job card.');
        }
        $image->clear();
        $image->destroy();
    }

    /** @return list<string> */
    private function wrap(Imagick $image, ImagickDraw $draw, string $text, float $maxWidth): array
    {
        $words = preg_split('/\s+/u', trim($text)) ?: [];
        $lines = [];
        $line = '';
        foreach ($words as $word) {
            $candidate = $line === '' ? $word : $line.' '.$word;
            $metrics = $image->queryFontMetrics($draw, $candidate);
            if ($line !== '' && (float) ($metrics['textWidth'] ?? 0) > $maxWidth) {
                $lines[] = $line;
                $line = $word;
            } else {
                $line = $candidate;
            }
        }
        if ($line !== '') {
            $lines[] = $line;
        }

        return $lines;
    }

    private function fontPath(): string
    {
        $configured = config('incoming_order.job_card.font');
        $candidates = array_filter([
            is_string($configured) ? $configured : null,
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            'C:\\Windows\\Fonts\\arial.ttf',
        ]);
        foreach ($candidates as $candidate) {
            if (is_file($candidate) && is_readable($candidate)) {
                return $candidate;
            }
        }

        throw new RuntimeException('No reviewed Unicode job-card font is available.');
    }
}
