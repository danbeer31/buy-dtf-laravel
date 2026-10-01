<?php

namespace Tests\Feature\Cart;

use App\Http\Controllers\CartController;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\SavedImage;
use App\Models\User;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Mockery;
use PHPUnit\Framework\Attributes\PreserveGlobalState;
use PHPUnit\Framework\Attributes\RunInSeparateProcess;
use Tests\TestCase;

class UploadAttachmentTest extends TestCase
{
    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_png_upload_uses_processed_pixel_dimensions_and_attaches_to_an_isolated_open_order(): void
    {
        [$user, $business] = $this->customerWithBusiness();
        $png = $this->solidPng(600, 300);

        $this->fakeUnavailableImageExtensions();

        $imageHelper = Mockery::mock('alias:App\Helpers\ImageHelper');
        $imageHelper->shouldReceive('trimTransparentBorder')
            ->once()
            ->andReturn(['success' => true]);
        $imageHelper->shouldNotReceive('thresholdAlphaMask');
        $imageHelper->shouldReceive('productionAlphaBounds')
            ->once()
            ->withArgs(fn (string $path, int $threshold): bool => is_file($path) && $threshold === 128)
            ->andReturn([
                'success' => true,
                'renderer' => 'imagick',
                'x' => 0,
                'y' => 0,
                'width' => 600,
                'height' => 300,
            ]);
        $imageHelper->shouldReceive('setPngDpi')
            ->once()
            ->withArgs(fn (string $path, int $x, int $y): bool => is_file($path) && $x === 300 && $y === 300)
            ->andReturn(['success' => true]);
        $imageHelper->shouldReceive('generateThumbnail')
            ->once()
            ->andReturn(['success' => false, 'message' => 'deliberately isolated from native image libraries']);

        $file = UploadedFile::fake()
            ->createWithContent('Two By One.PNG', $png)
            ->mimeType('image/png');

        $preflight = $this->actingAs($user)->postJson(route('cart.preflight'), [
            'name' => $file->getClientOriginalName(),
            'size' => $file->getSize(),
            'mime' => 'image/png',
        ])->assertOk();

        $uploadId = (string) $preflight->json('upload_id');
        $storedAbsolutePath = null;
        $originalAbsolutePath = null;

        try {
            $response = $this->actingAs($user)->post(
                route('cart.put', ['upload_id' => $uploadId]),
                [
                    'file' => $file,
                    'name' => $file->getClientOriginalName(),
                    'size' => $file->getSize(),
                    'mime' => 'image/png',
                ],
                ['Accept' => 'application/json']
            );

            $response
                ->assertOk()
                ->assertJsonPath('success', true)
                ->assertJsonPath('status', 'uploaded')
                ->assertJsonPath('meta.width_px', 600)
                ->assertJsonPath('meta.height_px', 300)
                ->assertJsonPath('meta.width_in', 2)
                ->assertJsonPath('meta.height_in', 1)
                ->assertJsonPath('meta.cleanup_skipped', false);

            $order = DtfOrder::findOrFail((int) $response->json('order_id'));
            $image = DtfImage::findOrFail((int) $response->json('dtfimage_id'));

            $this->assertSame($business->id, (int) $order->business_id);
            $this->assertSame(1, (int) $order->status);
            $this->assertSame($order->id, (int) $image->dtforder_id);
            $this->assertSame(2.0, (float) $image->width);
            $this->assertSame(1.0, (float) $image->height);
            $this->assertSame('two by one.png', $image->native_filename);
            $this->assertSame('image/png', $image->upload_mime);
            $this->assertSame(hash('sha256', $png), $image->sha256_original);
            $this->assertSame(hash('sha256', $png), $image->sha256_bitmap);
            $this->assertSame($image->image, $image->thumbnail);
            $this->assertSame(128, $image->productionAlphaThreshold());
            $this->assertSame('local_private', data_get($image->item_meta, 'source_artwork.disk'));
            $this->assertSame('production_derivative', data_get($image->item_meta, 'alpha_processing.scope'));

            $storedAbsolutePath = public_path(ltrim((string) $image->image, '/'));
            $originalAbsolutePath = storage_path('app/private/'.data_get($image->item_meta, 'source_artwork.path'));
            $this->assertFileExists($storedAbsolutePath);
            $this->assertFileExists($originalAbsolutePath);
            $this->assertSame($png, file_get_contents($originalAbsolutePath));
            $this->assertSame([600, 300], array_slice(getimagesize($storedAbsolutePath), 0, 2));
            $this->assertSame('ready', session("uploader_pending.{$uploadId}.phase"));
            $this->assertSame($image->id, session("uploader_pending.{$uploadId}.dtfimage_id"));
            Http::assertNothingSent();
        } finally {
            if ($storedAbsolutePath && is_file($storedAbsolutePath)) {
                unlink($storedAbsolutePath);
            }
            if ($originalAbsolutePath && is_file($originalAbsolutePath)) {
                unlink($originalAbsolutePath);
            }
        }
    }

    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_png_svg_and_pdf_flows_preserve_the_exact_source_and_defer_alpha_changes(): void
    {
        self::assertTrue(extension_loaded('imagick'), 'Imagick is required for the cart format flow matrix.');
        [, $business] = $this->customerWithBusiness();
        $controller = new class extends CartController
        {
            public function attachFixture(
                string $path,
                string $mime,
                string $name,
                int $businessId,
                string $sourceOrderId,
            ): array {
                return $this->processAndAttach(
                    $path,
                    $mime,
                    $name,
                    $businessId,
                    $sourceOrderId,
                    (int) filesize($path),
                );
            }
        };
        $fixtures = [
            ['antialiased-edges.png', 'image/png'],
            ['cart-source.svg', 'image/svg+xml'],
            ['cart-source.pdf', 'application/pdf'],
        ];
        $createdPaths = [];

        try {
            foreach ($fixtures as [$name, $mime]) {
                $sourcePath = dirname(__DIR__, 2).'/Fixtures/ImageProcessing/'.$name;
                $sourceHash = hash_file('sha256', $sourcePath);
                $sourceBytes = file_get_contents($sourcePath);
                $result = $controller->attachFixture(
                    $sourcePath,
                    $mime,
                    $name,
                    $business->id,
                    'format-'.pathinfo($name, PATHINFO_EXTENSION),
                );
                $image = DtfImage::findOrFail($result['dtfimage_id']);
                $previewPath = public_path(ltrim((string) $image->image, '/'));
                $thumbnailPath = public_path(ltrim((string) $image->thumbnail, '/'));
                $originalPath = storage_path('app/private/'.data_get($image->item_meta, 'source_artwork.path'));
                $createdPaths = array_merge($createdPaths, [$previewPath, $thumbnailPath, $originalPath]);

                self::assertSame($mime, $image->upload_mime, $name);
                self::assertSame(128, $image->productionAlphaThreshold(), $name);
                self::assertSame($sourceHash, hash_file('sha256', $sourcePath), "$name source fixture changed");
                self::assertSame($sourceHash, hash_file('sha256', $originalPath), "$name preserved source hash differs");
                self::assertSame($sourceBytes, file_get_contents($originalPath), "$name preserved source bytes differ");
                self::assertGreaterThan(0, $result['meta']['width_px'], $name);
                self::assertGreaterThan(0, $result['meta']['height_px'], $name);
                self::assertFileExists($previewPath);
                $resolution = \App\Helpers\ImageHelper::pngResolution($previewPath);
                self::assertNotNull($resolution, "$name preview omitted pHYs");
                self::assertEqualsWithDelta(300.0, $resolution['x_dpi'], 0.02, $name);
                self::assertEqualsWithDelta(300.0, $resolution['y_dpi'], 0.02, $name);

                if ($name !== 'cart-source.pdf') {
                    self::assertTrue($this->containsPartialAlpha($previewPath), "$name preview lost anti-aliased alpha");
                }
            }
        } finally {
            foreach (array_unique($createdPaths) as $path) {
                if (is_file($path)) {
                    unlink($path);
                }
            }
        }
    }

    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_fully_transparent_cart_upload_fails_without_persisting_artwork(): void
    {
        self::assertTrue(extension_loaded('imagick'));
        [, $business] = $this->customerWithBusiness();
        $controller = new class extends CartController
        {
            public function attachFixture(string $path, int $businessId): array
            {
                return $this->processAndAttach(
                    $path,
                    'image/png',
                    'fully-transparent.png',
                    $businessId,
                    'fully-transparent',
                    (int) filesize($path),
                );
            }
        };
        $sourcePath = dirname(__DIR__, 2).'/Fixtures/ImageProcessing/fully-transparent.png';
        $sourceHash = hash_file('sha256', $sourcePath);
        $beforeTemps = glob(storage_path('app/tmp/*.png')) ?: [];
        sort($beforeTemps);

        try {
            $controller->attachFixture($sourcePath, $business->id);
            self::fail('A fully transparent upload should not attach to the cart.');
        } catch (\RuntimeException $exception) {
            self::assertSame('Uploaded artwork is fully transparent.', $exception->getMessage());
        }

        $afterTemps = glob(storage_path('app/tmp/*.png')) ?: [];
        sort($afterTemps);
        self::assertSame($beforeTemps, $afterTemps);
        self::assertSame($sourceHash, hash_file('sha256', $sourcePath));
        self::assertSame(0, DtfImage::query()->count());
    }

    public function test_existing_and_saved_artwork_reuse_preserves_the_deferred_alpha_policy(): void
    {
        [$user, $business] = $this->customerWithBusiness();
        $sourceOrder = DtfOrder::create([
            'business_id' => $business->id,
            'status' => 2,
            'order_date' => now(),
        ]);
        $policy = [
            'source_artwork' => [
                'version' => 1,
                'disk' => 'local_private',
                'path' => 'customer-artwork/frozen-source.png',
                'sha256' => str_repeat('a', 64),
            ],
            'alpha_processing' => [
                'version' => 1,
                'scope' => 'production_derivative',
                'threshold' => 128,
            ],
        ];
        $source = DtfImage::create([
            'dtforder_id' => $sourceOrder->id,
            'image' => '/uploads/images/policy-source.png',
            'thumbnail' => '/uploads/images/thumbs/policy-source.png',
            'item_type' => 'standard',
            'item_meta' => $policy,
            'upload_mime' => 'image/png',
            'image_name' => 'Policy Source',
            'width' => 2,
            'height' => 1,
            'quantity' => 1,
            'production' => 0,
        ]);
        $saved = SavedImage::create([
            'business_id' => $business->id,
            'image' => $source->image,
            'thumbnail' => $source->thumbnail,
            'image_name' => $source->image_name,
            'width' => $source->width,
            'height' => $source->height,
            'date_uploaded' => now(),
        ]);

        $existingResponse = $this->actingAs($user)->postJson(route('cart.use_existing'), [
            'dtfimage_id' => $source->id,
        ])->assertOk()->assertJsonPath('success', true);
        $savedResponse = $this->actingAs($user)->postJson(route('cart.use_saved'), [
            'saved_id' => $saved->id,
        ])->assertOk()->assertJsonPath('success', true);

        foreach ([$existingResponse->json('id'), $savedResponse->json('id')] as $id) {
            $reused = DtfImage::findOrFail((int) $id);
            self::assertSame(128, $reused->productionAlphaThreshold());
            self::assertSame($policy, $reused->getItemMetadata());
            self::assertSame('image/png', $reused->upload_mime);
            self::assertSame($source->thumbnail, $reused->thumbnail);
        }
    }

    /** @return array{User, Business} */
    private function customerWithBusiness(): array
    {
        $email = 'upload-'.uniqid().'@example.test';
        $business = Business::create([
            'business_name' => 'Upload Test Business',
            'contact_name' => 'Upload Customer',
            'email' => $email,
            'status' => 1,
        ]);

        $user = User::factory()->create([
            'email' => $email,
            'role' => 'customer',
            'fuel_business_id' => $business->id,
        ]);

        return [$user, $business];
    }

    private function fakeUnavailableImageExtensions(): void
    {
        if (class_exists('Imagick', false)) {
            return;
        }

        $imagick = Mockery::mock('overload:Imagick');
        $imagick->shouldReceive('pingImage')->once();
        $imagick->shouldReceive('clear')->once();
        $imagick->shouldReceive('destroy')->once();
    }

    private function solidPng(int $width, int $height): string
    {
        $scanline = "\x00".str_repeat("\x00\x00\x00\xFF", $width);
        $pixels = str_repeat($scanline, $height);

        return "\x89PNG\x0D\x0A\x1A\x0A"
            .$this->pngChunk('IHDR', pack('NNCCCCC', $width, $height, 8, 6, 0, 0, 0))
            .$this->pngChunk('IDAT', gzcompress($pixels, 9))
            .$this->pngChunk('IEND', '');
    }

    private function pngChunk(string $type, string $data): string
    {
        return pack('N', strlen($data))
            .$type
            .$data
            .pack('N', crc32($type.$data));
    }

    private function containsPartialAlpha(string $path): bool
    {
        $image = new \Imagick($path);
        try {
            foreach ($image->getPixelIterator() as $row) {
                foreach ($row as $pixel) {
                    $alpha = (int) round($pixel->getColorValue(\Imagick::COLOR_ALPHA) * 255);
                    if ($alpha > 0 && $alpha < 255) {
                        return true;
                    }
                }
            }

            return false;
        } finally {
            $image->clear();
            $image->destroy();
        }
    }
}
