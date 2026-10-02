<?php

namespace Tests\Feature\Admin;

use App\Helpers\ImageHelper;
use App\Helpers\ProductionHelper;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\User;
use App\Services\DropboxService;
use Imagick;
use Mockery;
use PHPUnit\Framework\Attributes\PreserveGlobalState;
use PHPUnit\Framework\Attributes\RunInSeparateProcess;
use ReflectionMethod;
use Tests\TestCase;

class ProductionComparisonAlphaPolicyTest extends TestCase
{
    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_admin_comparison_matches_actual_production_for_policy_and_legacy_records(): void
    {
        self::assertTrue(extension_loaded('imagick'));
        $admin = User::factory()->create(['role' => 'admin']);
        $business = Business::create([
            'business_name' => 'Comparison Policy Business',
            'email' => 'comparison-policy-'.uniqid().'@example.test',
            'status' => 1,
        ]);
        $order = DtfOrder::create([
            'business_id' => $business->id,
            'status' => 2,
            'order_date' => now(),
        ]);
        $fixture = dirname(__DIR__, 2).'/Fixtures/ImageProcessing/antialiased-edges.png';
        $createdPaths = [];

        try {
            foreach ([
                'policy' => [
                    'width' => 6 / 300,
                    'height' => 6 / 300,
                    'item_meta' => [
                        'alpha_processing' => [
                            'version' => 1,
                            'scope' => 'production_derivative',
                            'threshold' => 128,
                        ],
                    ],
                    'expected_alpha' => [0, 255],
                    'expected_bounds' => ['x' => 0, 'y' => 0, 'width' => 6, 'height' => 6],
                ],
                'legacy' => [
                    'width' => 6 / 300,
                    'height' => 6 / 300,
                    'item_meta' => null,
                    'expected_alpha' => [0, 127, 128, 192, 255],
                    'expected_bounds' => ['x' => 1, 'y' => 1, 'width' => 4, 'height' => 4],
                ],
            ] as $case => $expectation) {
                $basename = 'admin-production-comparison-'.$case.'-'.bin2hex(random_bytes(4)).'.png';
                $relativePath = '/uploads/images/'.$basename;
                $sourcePath = public_path(ltrim($relativePath, '/'));
                if (! is_dir(dirname($sourcePath))) {
                    mkdir(dirname($sourcePath), 0777, true);
                }
                copy($fixture, $sourcePath);
                $createdPaths[] = $sourcePath;
                $sourceHash = hash_file('sha256', $sourcePath);

                $image = DtfImage::create([
                    'dtforder_id' => $order->id,
                    'image' => $relativePath,
                    'item_type' => 'standard',
                    'item_meta' => $expectation['item_meta'],
                    'image_name' => ucfirst($case).' comparison',
                    'width' => $expectation['width'],
                    'height' => $expectation['height'],
                    'quantity' => 1,
                    'production' => 0,
                ]);
                $image->refresh();

                $comparisonResponse = $this->actingAs($admin)
                    ->getJson(route('admin.orders.images.compare', ['image' => $image->id]))
                    ->assertOk()
                    ->assertJsonPath('success', true);
                $comparisonPath = public_path(ltrim((string) $comparisonResponse->json('production_url'), '/'));
                $createdPaths[] = $comparisonPath;
                $this->assertFileExists($comparisonPath);

                $expectedVersion = md5(implode('|', [
                    (string) $image->id,
                    (string) $image->width,
                    (string) $image->height,
                    (string) filemtime($sourcePath),
                    (string) ($image->updated_at?->timestamp ?? ''),
                    $image->productionAlphaPolicyIdentity(),
                ]));
                $this->assertSame(
                    'production_'.$image->id.'_'.$expectedVersion.'.png',
                    basename($comparisonPath),
                    "{$case} comparison cache omitted the alpha-policy identity",
                );

                $productionCapture = storage_path('app/production-comparison-'.$case.'-'.bin2hex(random_bytes(4)).'.png');
                $createdPaths[] = $productionCapture;
                $dropbox = Mockery::mock(DropboxService::class);
                $dropbox->shouldReceive('upload')
                    ->once()
                    ->andReturnUsing(function (string $localPath, string $remotePath) use ($productionCapture): array {
                        copy($localPath, $productionCapture);

                        return ['path' => $remotePath];
                    });

                $method = new ReflectionMethod(ProductionHelper::class, 'uploadProductionImage');
                $uploaded = $method->invoke(
                    null,
                    $dropbox,
                    $image,
                    '/DTF_Files/coldesi/'.$basename,
                    null,
                    false,
                    (float) $image->width,
                    (float) $image->height,
                    null,
                );

                $this->assertTrue($uploaded);
                $this->assertFileExists($productionCapture);
                $this->assertSame($this->rgbaPixels($productionCapture), $this->rgbaPixels($comparisonPath), "{$case} pixels differ");
                $this->assertSame(getimagesize($productionCapture), getimagesize($comparisonPath), "{$case} dimensions differ");
                $this->assertSame($expectation['expected_bounds'], $this->visibleBounds($comparisonPath), "{$case} bounds differ");
                $this->assertSame($expectation['expected_alpha'], $this->alphaValues($comparisonPath), "{$case} alpha values differ");

                foreach ([$comparisonPath, $productionCapture] as $resultPath) {
                    $resolution = ImageHelper::pngResolution($resultPath);
                    $this->assertNotNull($resolution, "{$case} result omitted pHYs");
                    $this->assertEqualsWithDelta(300.0, $resolution['x_dpi'], 0.02, "{$case} X DPI differs");
                    $this->assertEqualsWithDelta(300.0, $resolution['y_dpi'], 0.02, "{$case} Y DPI differs");
                }
                $this->assertSame($sourceHash, hash_file('sha256', $sourcePath), "{$case} source was modified");
            }
        } finally {
            foreach (array_unique($createdPaths) as $path) {
                if (is_file($path)) {
                    unlink($path);
                }
            }
        }
    }

    /** @return array<int, int> */
    private function rgbaPixels(string $path): array
    {
        $image = new Imagick($path);
        try {
            return $image->exportImagePixels(
                0,
                0,
                $image->getImageWidth(),
                $image->getImageHeight(),
                'RGBA',
                Imagick::PIXEL_CHAR,
            );
        } finally {
            $image->clear();
            $image->destroy();
        }
    }

    /** @return array<int, int> */
    private function alphaValues(string $path): array
    {
        $image = new Imagick($path);
        $values = [];
        try {
            foreach ($image->getPixelIterator() as $row) {
                foreach ($row as $pixel) {
                    $values[] = (int) round($pixel->getColorValue(Imagick::COLOR_ALPHA) * 255);
                }
            }
        } finally {
            $image->clear();
            $image->destroy();
        }
        $values = array_values(array_unique($values));
        sort($values);

        return $values;
    }

    /** @return array{x:int,y:int,width:int,height:int}|null */
    private function visibleBounds(string $path): ?array
    {
        $image = new Imagick($path);
        $minX = $image->getImageWidth();
        $minY = $image->getImageHeight();
        $maxX = -1;
        $maxY = -1;
        try {
            foreach ($image->getPixelIterator() as $y => $row) {
                foreach ($row as $x => $pixel) {
                    if ($pixel->getColorValue(Imagick::COLOR_ALPHA) <= 0) {
                        continue;
                    }
                    $minX = min($minX, $x);
                    $minY = min($minY, $y);
                    $maxX = max($maxX, $x);
                    $maxY = max($maxY, $y);
                }
            }
        } finally {
            $image->clear();
            $image->destroy();
        }

        return $maxX < 0 ? null : [
            'x' => $minX,
            'y' => $minY,
            'width' => $maxX - $minX + 1,
            'height' => $maxY - $minY + 1,
        ];
    }
}
