<?php

namespace Tests\Feature\Api;

use App\Models\Business;
use App\Models\DtfImage;
use Illuminate\Filesystem\Filesystem;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class IncomingOrderAuthenticationTest extends TestCase
{
    private string|false $originalSecret;

    private ?string $temporaryPublicPath = null;

    protected function setUp(): void
    {
        parent::setUp();

        $this->originalSecret = getenv('BUY_DTF_SECRET');
        $this->setSecret('incoming-step1-secret');
        Http::preventStrayRequests();
    }

    protected function tearDown(): void
    {
        if ($this->temporaryPublicPath !== null) {
            (new Filesystem)->deleteDirectory($this->temporaryPublicPath);
        }

        if ($this->originalSecret === false) {
            putenv('BUY_DTF_SECRET');
            unset($_ENV['BUY_DTF_SECRET'], $_SERVER['BUY_DTF_SECRET']);
        } else {
            $this->setSecret($this->originalSecret);
        }

        parent::tearDown();
    }

    public function test_invalid_hmac_is_rejected_before_remote_image_fetch(): void
    {
        $payload = $this->unsignedPayload();
        $payload['signature'] = 'not-a-valid-hmac';

        $this->postJson('/api/incomingorder', $payload)
            ->assertStatus(401)
            ->assertExactJson(['error' => 'Invalid signature']);

        Http::assertNothingSent();
    }

    public function test_valid_hmac_converts_a_local_data_uri_into_an_ordered_image(): void
    {
        $this->temporaryPublicPath = sys_get_temp_dir()
            .DIRECTORY_SEPARATOR
            .'buy-dtf-incoming-'.bin2hex(random_bytes(8));
        $this->assertTrue(mkdir($this->temporaryPublicPath, 0700));
        $this->app->usePublicPath($this->temporaryPublicPath);

        $business = Business::query()->create([
            'business_name' => 'Incoming Step 1',
            'contact_name' => 'API Test',
            'email' => 'incoming-step1@example.test',
            'status' => 'confirmed',
        ]);
        $this->assertSame(1, $business->id);

        $png = $this->png(600, 300);
        $payload = [
            'source_order_id' => 'step1-conversion',
            'file_name' => 'converted-artwork.png',
            'design' => [
                'image_url' => 'data:image/png;base64,'.base64_encode($png),
                'width' => 4,
                'height' => 2,
                'quantity' => 3,
            ],
        ];
        $payload['signature'] = hash_hmac(
            'sha256',
            (string) json_encode($payload),
            'incoming-step1-secret'
        );

        $response = $this->postJson('/api/incomingorder', $payload)
            ->assertOk()
            ->assertJsonPath('success', true)
            ->assertJsonPath('duplicate', false)
            ->assertJsonPath('orig_width_in', 2)
            ->assertJsonPath('orig_height_in', 1)
            ->assertJsonPath('width_ratio', 2)
            ->assertJsonPath('height_ratio', 2);

        $image = DtfImage::query()->sole();
        $this->assertSame($response->json('order_id'), $image->dtforder_id);
        $this->assertSame('converted-artwork.png', $image->image_name);
        $this->assertSame(4.0, $image->width);
        $this->assertSame(2.0, $image->height);
        $this->assertSame(3, $image->quantity);
        $this->assertSame(2.0, $image->orig_width);
        $this->assertSame(1.0, $image->orig_height);
        $this->assertSame(hash('sha256', $png), $image->sha256_original);

        $storedPath = $this->temporaryPublicPath
            .DIRECTORY_SEPARATOR
            .str_replace('/', DIRECTORY_SEPARATOR, ltrim($image->image, '/'));
        $this->assertFileExists($storedPath);
        $this->assertSame($png, file_get_contents($storedPath));
        Http::assertNothingSent();
    }

    public function test_valid_hmac_passes_authentication_without_remote_image_fetch(): void
    {
        $payload = $this->unsignedPayload();
        $payload['signature'] = hash_hmac(
            'sha256',
            (string) json_encode($payload),
            'incoming-step1-secret'
        );

        // The isolated database intentionally has no legacy Business #1. Reaching
        // this 404 proves HMAC verification passed and exits before file_get_contents.
        $this->postJson('/api/incomingorder', $payload)
            ->assertStatus(404)
            ->assertExactJson(['error' => 'Business not found']);

        Http::assertNothingSent();
    }

    private function unsignedPayload(): array
    {
        return [
            'source_order_id' => 'step1-order',
            'file_name' => 'step1.png',
            'design' => [
                // A local data URI guarantees this test never depends on a network.
                'image_url' => 'data:image/png;base64,not-read-during-auth-tests',
                'width' => 1,
                'height' => 1,
                'quantity' => 1,
            ],
        ];
    }

    private function setSecret(string $secret): void
    {
        putenv("BUY_DTF_SECRET={$secret}");
        $_ENV['BUY_DTF_SECRET'] = $secret;
        $_SERVER['BUY_DTF_SECRET'] = $secret;
    }

    private function png(int $width, int $height): string
    {
        $row = "\0".str_repeat("\0", $width * 4);
        $pixels = str_repeat($row, $height);

        return "\x89PNG\r\n\x1a\n"
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
