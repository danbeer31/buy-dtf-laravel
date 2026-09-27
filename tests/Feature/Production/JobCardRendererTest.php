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
            (string) config('incoming_order.job_card.renderer_version'),
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
            (string) config('incoming_order.job_card.font_sha256'),
            $result['font_sha256'],
        );
    }
}
