<?php

declare(strict_types=1);

use App\Helpers\ImageHelper;
use App\Services\IncomingOrders\JobCardRenderer;
use Illuminate\Contracts\Console\Kernel;

require dirname(__DIR__).'/vendor/autoload.php';

$app = require dirname(__DIR__).'/bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();

$outputDirectory = $argv[1] ?? dirname(__DIR__).'/ops/evidence/incoming-order-v1-job-card-v2';
if (! is_dir($outputDirectory)
    && ! mkdir($outputDirectory, 0770, true)
    && ! is_dir($outputDirectory)) {
    throw new RuntimeException('Unable to create evidence directory.');
}

$renderer = $app->make(JobCardRenderer::class);
$readiness = $renderer->readiness();
if (! $readiness['ready']) {
    throw new RuntimeException('Renderer is not ready: '.($readiness['reason'] ?? 'unknown'));
}

$normal = [
    'version' => 1,
    'required' => false,
    'mode' => 'metadata_only',
    'order_number' => '1725',
    'order_item_id' => 1671,
    'production_print_snapshot_id' => 31,
    'product_name' => 'Urey Cheer Port Authority Jacket',
    'product_sku' => 'JST81',
    'color' => 'Black/Light Oxford',
    'size' => 'S',
    'placement' => 'Full Back',
    'quantity' => 1,
    'shop_domain' => 'urey.localschoolgear.com',
];
$maximum = [
    'version' => 1,
    'required' => false,
    'mode' => 'metadata_only',
    'order_number' => str_repeat('O', 64),
    'order_item_id' => PHP_INT_MAX,
    'production_print_snapshot_id' => PHP_INT_MAX,
    'product_name' => str_repeat('W', 160),
    'product_sku' => str_repeat('S', 80),
    'color' => str_repeat('C', 80),
    'size' => str_repeat('Z', 40),
    'placement' => str_repeat('P', 80),
    'quantity' => 10_000,
    'shop_domain' => str_repeat('a', 63).'.'.str_repeat('b', 63).'.'.str_repeat('c', 63).'.'.str_repeat('d', 61),
];

$cases = [
    'normal' => [$normal, 1],
    'maximum-fields' => [$maximum, 10_000],
];
$receipt = [
    'evidence_version' => 1,
    'renderer_readiness' => $readiness,
    'cases' => [],
];

foreach ($cases as $name => [$metadata, $quantity]) {
    $result = $renderer->render(
        $name === 'normal' ? 990101 : 990102,
        hash('sha256', 'review-evidence-'.$name),
        $metadata,
        $quantity,
        (string) config('incoming_order.job_card.renderer_version'),
    );
    $destination = $outputDirectory.'/buy-dtf-job-card-review-'.$name.'.png';
    if (! copy($result['absolute_path'], $destination)) {
        throw new RuntimeException("Unable to copy {$name} evidence.");
    }
    $size = getimagesize($destination);
    $resolution = ImageHelper::pngResolution($destination);
    if (! is_array($size) || ! is_array($resolution)) {
        throw new RuntimeException("Unable to inspect {$name} evidence.");
    }

    $receipt['cases'][$name] = [
        'file' => basename($destination),
        'sha256' => hash_file('sha256', $destination),
        'bytes' => filesize($destination),
        'width_px' => $size[0],
        'height_px' => $size[1],
        'x_ppm' => $resolution['x_ppm'],
        'y_ppm' => $resolution['y_ppm'],
        'x_dpi' => round($resolution['x_dpi'], 6),
        'y_dpi' => round($resolution['y_dpi'], 6),
        'font_sha256' => $result['font_sha256'],
        'renderer_version' => $result['renderer_version'],
    ];
}

$receiptPath = $outputDirectory.'/render-receipt.json';
$encoded = json_encode($receipt, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR).PHP_EOL;
if (file_put_contents($receiptPath, $encoded) === false) {
    throw new RuntimeException('Unable to write evidence receipt.');
}

echo $encoded;
