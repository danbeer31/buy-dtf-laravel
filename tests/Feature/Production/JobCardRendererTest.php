<?php

namespace Tests\Feature\Production;

use App\Helpers\ImageHelper;
use App\Services\IncomingOrders\JobCardRenderer;
use Tests\TestCase;

class JobCardRendererTest extends TestCase
{
    /** @var list<string> */
    private array $paths = [];

    protected function tearDown(): void
    {
        foreach ($this->paths as $path) {
            @unlink($path);
            @rmdir(dirname($path));
        }

        parent::tearDown();
    }

    public function test_real_renderer_emits_1500_by_900_card_with_verified_300_dpi_and_max_fields_fit(): void
    {
        $renderer = app(JobCardRenderer::class);
        $readiness = $renderer->readiness();
        if (! $readiness['ready']) {
            $this->markTestSkipped('Real job-card renderer is unavailable: '.$readiness['reason']);
        }

        $metadata = [
            'version' => 1,
            'required' => false,
            'mode' => 'metadata_only',
            'order_number' => str_repeat('O', 64),
            'order_item_id' => 1,
            'production_print_snapshot_id' => 1,
            'product_name' => str_repeat('W', 160),
            'product_sku' => str_repeat('S', 80),
            'color' => str_repeat('C', 80),
            'size' => str_repeat('Z', 40),
            'placement' => str_repeat('P', 80),
            'quantity' => 10_000,
            'shop_domain' => str_repeat('a', 63).'.'.str_repeat('b', 63).'.'.str_repeat('c', 63).'.'.str_repeat('d', 61),
        ];

        $result = $renderer->render(
            990001,
            hash('sha256', 'maximum-field-card'),
            $metadata,
            10_000,
            JobCardRenderer::RENDERER_VERSION,
        );
        $this->paths[] = $result['absolute_path'];

        $size = getimagesize($result['absolute_path']);
        $resolution = ImageHelper::pngResolution($result['absolute_path']);
        $this->assertIsArray($size);
        $this->assertSame(1500, $size[0]);
        $this->assertSame(900, $size[1]);
        $this->assertSame(300, $result['dpi']);
        $this->assertSame(11811, $result['x_ppm']);
        $this->assertSame(11811, $result['y_ppm']);
        $this->assertSame(11811, $resolution['x_ppm'] ?? null);
        $this->assertSame(11811, $resolution['y_ppm'] ?? null);
        $this->assertEqualsWithDelta(300.0, $resolution['x_dpi'] ?? 0.0, 0.02);
        $this->assertSame(
            JobCardRenderer::FONT_SHA256,
            $result['font_sha256'],
        );
    }

    public function test_renderer_v2_uses_the_bundled_immutable_font_identity(): void
    {
        $font = resource_path(JobCardRenderer::FONT_RELATIVE_PATH);
        $license = resource_path(JobCardRenderer::FONT_LICENSE_RELATIVE_PATH);

        $this->assertFileExists($font);
        $this->assertFileExists($license);
        $this->assertSame(759_720, filesize($font));
        $this->assertSame(JobCardRenderer::FONT_SHA256, hash_file('sha256', $font));
        $this->assertStringContainsString(
            'Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved.',
            (string) file_get_contents($license),
        );
        $this->assertStringContainsString(
            'Permission is hereby granted, free of charge',
            (string) file_get_contents($license),
        );
        $this->assertSame('separate-job-card-v2', JobCardRenderer::RENDERER_VERSION);
        $this->assertArrayNotHasKey('font', config('incoming_order.job_card'));
        $this->assertArrayNotHasKey('font_sha256', config('incoming_order.job_card'));
        $this->assertArrayNotHasKey('renderer_version', config('incoming_order.job_card'));

        config()->set('incoming_order.job_card.font', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf');
        config()->set('incoming_order.job_card.font_sha256', str_repeat('0', 64));
        config()->set('incoming_order.job_card.renderer_version', 'unreviewed-renderer');

        $readiness = app(JobCardRenderer::class)->readiness();
        $this->assertSame(extension_loaded('imagick'), $readiness['ready']);
        $this->assertSame(
            extension_loaded('imagick') ? null : 'imagick_unavailable',
            $readiness['reason'],
        );
        $this->assertSame(JobCardRenderer::RENDERER_VERSION, $readiness['renderer_version']);
        $this->assertSame(JobCardRenderer::FONT_SHA256, $readiness['font_sha256']);
    }
}
