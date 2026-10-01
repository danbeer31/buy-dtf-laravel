<?php

declare(strict_types=1);

/**
 * Generate deterministic RGBA PNG fixtures without GD or Imagick.
 *
 * Rows use PNG filter 0 and include a canonical 300-PPI pHYs chunk.
 */
function pngChunk(string $type, string $data): string
{
    return pack('N', strlen($data))
        .$type
        .$data
        .pack('N', (int) sprintf('%u', crc32($type.$data)));
}

/** @param callable(int, int): array{int, int, int, int} $pixel */
function writeFixture(string $name, int $width, int $height, callable $pixel): void
{
    $scanlines = '';
    for ($y = 0; $y < $height; $y++) {
        $scanlines .= "\x00";
        for ($x = 0; $x < $width; $x++) {
            [$red, $green, $blue, $alpha] = $pixel($x, $y);
            $scanlines .= pack('CCCC', $red, $green, $blue, $alpha);
        }
    }

    $png = "\x89PNG\x0D\x0A\x1A\x0A"
        .pngChunk('IHDR', pack('NNCCCCC', $width, $height, 8, 6, 0, 0, 0))
        .pngChunk('pHYs', pack('NNC', 11811, 11811, 1))
        .pngChunk('IDAT', gzcompress($scanlines, 9))
        .pngChunk('IEND', '');

    file_put_contents(__DIR__.DIRECTORY_SEPARATOR.$name, $png);
}

function writeSvgFixture(): void
{
    $svg = <<<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80">
  <rect x="20" y="15" width="80" height="50" rx="4" fill="#2457d6" fill-opacity="0.45"/>
  <rect x="25" y="20" width="70" height="40" rx="2" fill="#2457d6"/>
</svg>
SVG;

    file_put_contents(__DIR__.DIRECTORY_SEPARATOR.'cart-source.svg', $svg."\n");
}

function writePdfFixture(): void
{
    $stream = "q\n0 0 0 rg\n12 6 48 24 re\nf\nQ\n";
    $objects = [
        '<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 36] /Resources << >> /Contents 4 0 R >>',
        '<< /Length '.strlen($stream)." >>\nstream\n{$stream}endstream",
    ];
    $pdf = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n";
    $offsets = [0];
    foreach ($objects as $number => $object) {
        $offsets[] = strlen($pdf);
        $pdf .= ($number + 1)." 0 obj\n{$object}\nendobj\n";
    }
    $xref = strlen($pdf);
    $pdf .= "xref\n0 ".(count($objects) + 1)."\n";
    $pdf .= "0000000000 65535 f\r\n";
    foreach (array_slice($offsets, 1) as $offset) {
        $pdf .= sprintf("%010d 00000 n\r\n", $offset);
    }
    $pdf .= 'trailer'."\n<< /Size ".(count($objects) + 1).' /Root 1 0 R >>'."\n";
    $pdf .= "startxref\n{$xref}\n%%EOF\n";

    file_put_contents(__DIR__.DIRECTORY_SEPARATOR.'cart-source.pdf', $pdf);
}

writeFixture('transparent-padding.png', 12, 10, static function (int $x, int $y): array {
    return $x >= 3 && $x <= 8 && $y >= 3 && $y <= 6
        ? [220, 20, 30, 255]
        : [13, 27, 41, 0];
});

writeFixture('antialiased-edges.png', 10, 10, static function (int $x, int $y): array {
    if ($x >= 3 && $x <= 6 && $y >= 3 && $y <= 6) {
        return [20, 190, 70, 255];
    }
    if (($x === 2 || $x === 7) && $y >= 3 && $y <= 6) {
        return [20, 190, 70, 128];
    }
    if (($y === 2 || $y === 7) && $x >= 3 && $x <= 6) {
        return [20, 190, 70, 192];
    }
    if (($x === 2 || $x === 7) && ($y === 2 || $y === 7)) {
        return [20, 190, 70, 127];
    }
    if (($x === 1 || $x === 8) && $y >= 2 && $y <= 7) {
        return [20, 190, 70, 64];
    }

    return [91, 47, 13, 0];
});

writeFixture('shadow-glow.png', 14, 12, static function (int $x, int $y): array {
    if ($x >= 4 && $x <= 8 && $y >= 3 && $y <= 7) {
        return [30, 80, 230, 255];
    }
    if ($x >= 3 && $x <= 9 && $y >= 2 && $y <= 8) {
        return [30, 80, 230, 160];
    }
    if ($x >= 2 && $x <= 10 && $y >= 1 && $y <= 9) {
        return [30, 80, 230, 96];
    }
    if ($x >= 1 && $x <= 11 && $y <= 10) {
        return [30, 80, 230, 32];
    }

    return [200, 10, 190, 0];
});

writeFixture('hard-edged-opaque.png', 9, 7, static function (int $x, int $y): array {
    return $x >= 2 && $x <= 6 && $y >= 1 && $y <= 5
        ? [10, 10, 10, 255]
        : [255, 255, 255, 0];
});

writeFixture('no-transparent-padding.png', 8, 6, static function (int $x, int $y): array {
    return [40 + ($x * 10), 30 + ($y * 12), 120, 255];
});

writeFixture('fully-transparent.png', 7, 5, static function (int $x, int $y): array {
    return [17 + $x, 33 + $y, 201, 0];
});

writeSvgFixture();
writePdfFixture();
