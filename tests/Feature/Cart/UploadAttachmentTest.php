<?php

namespace Tests\Feature\Cart;

use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
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
        $imageHelper->shouldReceive('thresholdAlphaMask')
            ->once()
            ->andReturn(['success' => true]);
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

            $storedAbsolutePath = public_path(ltrim((string) $image->image, '/'));
            $this->assertFileExists($storedAbsolutePath);
            $this->assertSame([600, 300], array_slice(getimagesize($storedAbsolutePath), 0, 2));
            $this->assertSame('ready', session("uploader_pending.{$uploadId}.phase"));
            $this->assertSame($image->id, session("uploader_pending.{$uploadId}.dtfimage_id"));
            Http::assertNothingSent();
        } finally {
            if ($storedAbsolutePath && is_file($storedAbsolutePath)) {
                unlink($storedAbsolutePath);
            }
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
}
