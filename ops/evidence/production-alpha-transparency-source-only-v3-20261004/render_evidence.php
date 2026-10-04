<?php

declare(strict_types=1);

use App\Helpers\ImageHelper;

require dirname(__DIR__, 3).'/vendor/autoload.php';

$root = dirname(__DIR__, 3);
$fixture = $root.'/tests/Fixtures/ImageProcessing/shadow-glow.png';
$fixtureHash = hash_file('sha256', $fixture);
$source = __DIR__.'/source-shadow-glow.png';
$before = __DIR__.'/before-buggy-threshold.png';
$afterImagick = __DIR__.'/after-fixed-imagick.png';
$afterGd = __DIR__.'/after-fixed-gd.png';
$comparison = __DIR__.'/comparison.png';

copy($fixture, $source);
mustSucceed(ImageHelper::setPngDpi($source, 300, 300), 'source DPI');

// Reproduce the old cart operation exactly: transparent trim followed by an
// 8-bit fraction supplied to a Q16/Q32 Imagick threshold operation.
copy($fixture, $before);
mustSucceed(ImageHelper::trimTransparentBorder($before), 'legacy trim');
$legacy = new Imagick($before);
if (! $legacy->getImageAlphaChannel()) {
    $legacy->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
}
$legacy->evaluateImage(Imagick::EVALUATE_THRESHOLD, 128 / 255, Imagick::CHANNEL_ALPHA);
$legacy->setImageFormat('png');
$legacy->setOption('png:color-type', '6');
$legacy->setOption('png:compression-level', '9');
if (! $legacy->writeImage($before)) {
    throw new RuntimeException('Unable to write legacy reproduction.');
}
$legacy->clear();
$legacy->destroy();
mustSucceed(ImageHelper::setPngDpi($before, 300, 300), 'legacy DPI');
removePngChunks($before, ['tIME']);

$bounds = ImageHelper::productionAlphaBounds($fixture, 128, 'imagick');
mustSucceed($bounds, 'fixed bounds');
$widthIn = (int) $bounds['width'] / 300;
$heightIn = (int) $bounds['height'] / 300;
mustSucceed(
    ImageHelper::prepareForProduction($fixture, $afterImagick, $widthIn, $heightIn, 300, 128, 'imagick'),
    'fixed Imagick render',
);
mustSucceed(
    ImageHelper::prepareForProduction($fixture, $afterGd, $widthIn, $heightIn, 300, 128, 'gd'),
    'fixed GD render',
);
removePngChunks($afterImagick, ['tIME']);
removePngChunks($afterGd, ['tIME']);

if (! hash_equals($fixtureHash, hash_file('sha256', $fixture))) {
    throw new RuntimeException('Evidence generation modified the frozen source fixture.');
}

renderComparison([
    ['SOURCE', $source],
    ['BEFORE: BUGGY', $before],
    ['AFTER: FIXED', $afterImagick],
], $comparison);
mustSucceed(ImageHelper::setPngDpi($comparison, 300, 300), 'comparison DPI');
removePngChunks($comparison, ['tIME']);

$metrics = [
    'schema_version' => 1,
    'threshold' => 128,
    'source_fixture' => [
        'relative_path' => '../../../tests/Fixtures/ImageProcessing/shadow-glow.png',
        'sha256' => $fixtureHash,
    ],
    'renders' => [],
];
foreach ([$source, $before, $afterImagick, $afterGd, $comparison] as $path) {
    $metrics['renders'][basename($path)] = inspectPng($path);
}
file_put_contents(
    __DIR__.'/metrics.json',
    json_encode($metrics, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR)."\n",
);

/** @param array{success?: bool, message?: string} $result */
function mustSucceed(array $result, string $step): void
{
    if (! ($result['success'] ?? false)) {
        throw new RuntimeException($step.' failed: '.($result['message'] ?? 'unknown error'));
    }
}

/** @param array<int, string> $chunkTypes */
function removePngChunks(string $path, array $chunkTypes): void
{
    $bytes = file_get_contents($path);
    $signature = "\x89PNG\x0D\x0A\x1A\x0A";
    if (! is_string($bytes) || ! str_starts_with($bytes, $signature)) {
        throw new RuntimeException('Cannot canonicalize non-PNG evidence: '.$path);
    }
    $output = $signature;
    $offset = 8;
    while ($offset + 12 <= strlen($bytes)) {
        $lengthData = unpack('Nlength', substr($bytes, $offset, 4));
        $length = (int) ($lengthData['length'] ?? -1);
        $total = 12 + $length;
        if ($length < 0 || $offset + $total > strlen($bytes)) {
            throw new RuntimeException('Malformed PNG evidence: '.$path);
        }
        $type = substr($bytes, $offset + 4, 4);
        if (! in_array($type, $chunkTypes, true)) {
            $output .= substr($bytes, $offset, $total);
        }
        $offset += $total;
    }
    if (file_put_contents($path, $output) === false) {
        throw new RuntimeException('Unable to canonicalize PNG evidence: '.$path);
    }
}

/** @param array<int, array{string, string}> $panels */
function renderComparison(array $panels, string $output): void
{
    $canvas = new Imagick;
    $canvas->newImage(1050, 390, new ImagickPixel('white'), 'png');
    $font = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';
    if (! is_file($font)) {
        throw new RuntimeException('Evidence font is unavailable: '.$font);
    }

    foreach ($panels as $index => [$label, $path]) {
        $left = 30 + ($index * 340);
        $checker = new Imagick;
        $checker->newImage(310, 310, new ImagickPixel('#eeeeee'), 'png');
        $drawChecker = new ImagickDraw;
        $drawChecker->setFillColor('#c9c9c9');
        for ($y = 0; $y < 310; $y += 20) {
            for ($x = 0; $x < 310; $x += 20) {
                if ((intdiv($x, 20) + intdiv($y, 20)) % 2 === 0) {
                    $drawChecker->rectangle($x, $y, min(309, $x + 19), min(309, $y + 19));
                }
            }
        }
        $checker->drawImage($drawChecker);

        $art = new Imagick($path);
        $art->setImageInterpolateMethod(Imagick::INTERPOLATE_NEARESTNEIGHBOR);
        // One source pixel is always twenty evidence pixels, so the panels
        // show the physical change in visible bounds instead of auto-fitting
        // every result to the same apparent size.
        $art->resizeImage(
            $art->getImageWidth() * 20,
            $art->getImageHeight() * 20,
            Imagick::FILTER_POINT,
            1,
        );
        $checker->compositeImage(
            $art,
            Imagick::COMPOSITE_OVER,
            intdiv(310 - $art->getImageWidth(), 2),
            intdiv(310 - $art->getImageHeight(), 2),
        );
        $canvas->compositeImage($checker, Imagick::COMPOSITE_OVER, $left, 55);

        $labelDraw = new ImagickDraw;
        $labelDraw->setFont($font);
        $labelDraw->setFontSize(22);
        $labelDraw->setFillColor('#111111');
        $labelDraw->setTextAlignment(Imagick::ALIGN_CENTER);
        $canvas->annotateImage($labelDraw, $left + 155, 35, 0, $label);

        $art->clear();
        $art->destroy();
        $checker->clear();
        $checker->destroy();
    }

    $canvas->setImageFormat('png');
    $canvas->setOption('png:color-type', '2');
    $canvas->setOption('png:compression-level', '9');
    $canvas->stripImage();
    if (! $canvas->writeImage($output)) {
        throw new RuntimeException('Unable to write comparison image.');
    }
    $canvas->clear();
    $canvas->destroy();
}

/** @return array<string, mixed> */
function inspectPng(string $path): array
{
    $image = new Imagick($path);
    $alphas = [];
    $rgbaBytes = '';
    $minX = $image->getImageWidth();
    $minY = $image->getImageHeight();
    $maxX = -1;
    $maxY = -1;
    foreach ($image->getPixelIterator() as $y => $row) {
        foreach ($row as $x => $pixel) {
            $alpha = (int) round($pixel->getColorValue(Imagick::COLOR_ALPHA) * 255);
            $rgbaBytes .= pack(
                'CCCC',
                (int) round($pixel->getColorValue(Imagick::COLOR_RED) * 255),
                (int) round($pixel->getColorValue(Imagick::COLOR_GREEN) * 255),
                (int) round($pixel->getColorValue(Imagick::COLOR_BLUE) * 255),
                $alpha,
            );
            $alphas[$alpha] = true;
            if ($alpha > 0) {
                $minX = min($minX, $x);
                $minY = min($minY, $y);
                $maxX = max($maxX, $x);
                $maxY = max($maxY, $y);
            }
        }
    }
    $width = $image->getImageWidth();
    $height = $image->getImageHeight();
    $image->clear();
    $image->destroy();
    $resolution = ImageHelper::pngResolution($path);
    $alphaValues = array_map('intval', array_keys($alphas));
    sort($alphaValues, SORT_NUMERIC);

    return [
        'bytes' => filesize($path),
        'sha256' => hash_file('sha256', $path),
        'rgba_sha256' => hash('sha256', $rgbaBytes),
        'width_px' => $width,
        'height_px' => $height,
        'aspect_ratio' => round($width / $height, 8),
        'x_dpi' => round((float) ($resolution['x_dpi'] ?? 0), 5),
        'y_dpi' => round((float) ($resolution['y_dpi'] ?? 0), 5),
        'alpha_values' => $alphaValues,
        'visible_bounds' => $maxX < 0 ? null : [
            'x' => $minX,
            'y' => $minY,
            'width' => $maxX - $minX + 1,
            'height' => $maxY - $minY + 1,
        ],
    ];
}
