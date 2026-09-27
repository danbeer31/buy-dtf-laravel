<?php

namespace Tests\Feature\Api;

use App\Exceptions\ArtworkFetchException;
use App\Exceptions\ArtworkValidationException;
use App\Services\IncomingOrders\ArtworkInspector;
use App\Services\IncomingOrders\BoundedArtworkFetcher;
use App\Services\IncomingOrders\FetchedArtwork;
use GuzzleHttp\Psr7\Response;
use Psr\Http\Message\ResponseInterface;
use Tests\TestCase;

class BoundedArtworkFetcherTest extends TestCase
{
    private string $png;

    protected function setUp(): void
    {
        parent::setUp();
        $this->png = (string) base64_decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
            true,
        );
        config()->set('incoming_order.allowed_hosts', ['artifacts.example.test']);
    }

    public function test_private_dns_result_is_denied_before_any_http_request(): void
    {
        $fetcher = new class extends BoundedArtworkFetcher
        {
            public bool $requested = false;

            protected function resolveHost(string $host): array
            {
                return ['127.0.0.1'];
            }

            protected function request(string $url, string $host, string $pinnedIp, ?string &$primaryIp): ResponseInterface
            {
                $this->requested = true;

                return new Response(200, ['Content-Type' => 'image/png'], 'x');
            }
        };

        try {
            $fetcher->fetch('https://artifacts.example.test/art.png', $this->owner());
            $this->fail('Private destination must be rejected.');
        } catch (ArtworkFetchException $exception) {
            $this->assertSame('artwork_network_denied', $exception->reason);
        }
        $this->assertFalse($fetcher->requested);
    }

    public function test_redirect_target_is_revalidated_against_the_allowlist(): void
    {
        $fetcher = new class extends BoundedArtworkFetcher
        {
            protected function resolveHost(string $host): array
            {
                return ['93.184.216.34'];
            }

            protected function request(string $url, string $host, string $pinnedIp, ?string &$primaryIp): ResponseInterface
            {
                $primaryIp = '93.184.216.34';

                return new Response(302, ['Location' => 'https://evil.example.test/private.png']);
            }
        };

        try {
            $fetcher->fetch('https://artifacts.example.test/art.png', $this->owner());
            $this->fail('Unapproved redirect host must be rejected.');
        } catch (ArtworkFetchException $exception) {
            $this->assertSame('artwork_host_not_allowed', $exception->reason);
        }
    }

    public function test_connected_address_must_match_the_pinned_dns_result(): void
    {
        $fetcher = new class extends BoundedArtworkFetcher
        {
            protected function resolveHost(string $host): array
            {
                return ['93.184.216.34'];
            }

            protected function request(string $url, string $host, string $pinnedIp, ?string &$primaryIp): ResponseInterface
            {
                $primaryIp = '93.184.216.35';

                return new Response(200, ['Content-Type' => 'image/png'], 'x');
            }
        };

        try {
            $fetcher->fetch('https://artifacts.example.test/art.png', $this->owner());
            $this->fail('A changed destination must be rejected.');
        } catch (ArtworkFetchException $exception) {
            $this->assertSame('artwork_destination_changed', $exception->reason);
            $this->assertTrue($exception->retryable);
        }
    }

    public function test_streaming_size_limit_fails_closed_and_removes_partial_file(): void
    {
        config()->set('incoming_order.fetch.max_bytes', 4);
        $owner = $this->owner();
        $fetcher = $this->responseFetcher(new Response(
            200,
            ['Content-Type' => 'image/png', 'Content-Length' => '5'],
            '12345',
        ));

        try {
            $fetcher->fetch('https://artifacts.example.test/art.png', $owner);
            $this->fail('Oversized response must be rejected.');
        } catch (ArtworkFetchException $exception) {
            $this->assertSame('artwork_download_too_large', $exception->reason);
        }
        $this->assertDirectoryDoesNotExist(storage_path('app/private/incoming-orders/tmp/'.$owner));
    }

    public function test_source_5xx_is_retryable_without_exposing_provider_body(): void
    {
        $fetcher = $this->responseFetcher(new Response(503, [], 'provider secret detail'));

        try {
            $fetcher->fetch('https://artifacts.example.test/art.png', $this->owner());
            $this->fail('Source error must fail.');
        } catch (ArtworkFetchException $exception) {
            $this->assertSame('artwork_source_unavailable', $exception->reason);
            $this->assertTrue($exception->retryable);
            $this->assertStringNotContainsString('provider secret', $exception->getMessage());
        }
    }

    public function test_inspector_rejects_declared_mime_mismatch_multi_frame_marker_and_pixel_limit(): void
    {
        $inspector = app(ArtworkInspector::class);

        $mismatch = $this->temporaryArtwork($this->png, 'image/jpeg');
        try {
            $inspector->inspect($mismatch);
            $this->fail('MIME mismatch must fail.');
        } catch (ArtworkValidationException $exception) {
            $this->assertSame('artwork_mime_mismatch', $exception->reason);
        } finally {
            @unlink($mismatch->temporaryPath);
        }

        $animated = $this->temporaryArtwork($this->png.'acTL', 'image/png');
        try {
            $inspector->inspect($animated);
            $this->fail('APNG marker must fail.');
        } catch (ArtworkValidationException $exception) {
            $this->assertSame('artwork_multiple_frames', $exception->reason);
        } finally {
            @unlink($animated->temporaryPath);
        }

        config()->set('incoming_order.fetch.max_width_px', 0);
        $limited = $this->temporaryArtwork($this->png, 'image/png');
        try {
            $inspector->inspect($limited);
            $this->fail('Pixel limit must fail.');
        } catch (ArtworkValidationException $exception) {
            $this->assertSame('artwork_limits_exceeded', $exception->reason);
        } finally {
            @unlink($limited->temporaryPath);
        }
    }

    private function responseFetcher(ResponseInterface $response): BoundedArtworkFetcher
    {
        return new class($response) extends BoundedArtworkFetcher
        {
            public function __construct(private readonly ResponseInterface $response) {}

            protected function resolveHost(string $host): array
            {
                return ['93.184.216.34'];
            }

            protected function request(string $url, string $host, string $pinnedIp, ?string &$primaryIp): ResponseInterface
            {
                $primaryIp = '93.184.216.34';

                return $this->response;
            }
        };
    }

    private function temporaryArtwork(string $bytes, string $contentType): FetchedArtwork
    {
        $path = tempnam(sys_get_temp_dir(), 'buy-dtf-artwork-inspection-');
        file_put_contents($path, $bytes);

        return new FetchedArtwork(
            temporaryPath: $path,
            approvedHost: 'artifacts.example.test',
            bytes: strlen($bytes),
            declaredContentType: $contentType,
        );
    }

    private function owner(): string
    {
        return '00000000-0000-4000-8000-'.bin2hex(random_bytes(6));
    }
}
