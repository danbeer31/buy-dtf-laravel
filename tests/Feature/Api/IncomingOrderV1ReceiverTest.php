<?php

namespace Tests\Feature\Api;

use App\Exceptions\ArtworkFetchException;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\IncomingOrderJob;
use App\Services\IncomingOrders\BoundedArtworkFetcher;
use App\Services\IncomingOrders\FetchedArtwork;
use App\Support\JsonCanonicalizer;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class IncomingOrderV1ReceiverTest extends TestCase
{
    private string $artworkBytes;

    private string $artworkHash;

    private string|false $originalSecret;

    protected function setUp(): void
    {
        parent::setUp();

        $this->artworkBytes = (string) base64_decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
            true,
        );
        $this->artworkHash = hash('sha256', $this->artworkBytes);

        $this->originalSecret = getenv('BUY_DTF_SECRET');
        putenv('BUY_DTF_SECRET=synthetic-incoming-order-test-secret');
        $_ENV['BUY_DTF_SECRET'] = 'synthetic-incoming-order-test-secret';
        $_SERVER['BUY_DTF_SECRET'] = 'synthetic-incoming-order-test-secret';

        config()->set('incoming_order.shared_secret', 'synthetic-incoming-order-test-secret');
        config()->set('incoming_order.receiver_enabled', true);
        config()->set('incoming_order.job_label_enabled', true);
        config()->set('incoming_order.allowed_hosts', ['artifacts.example.test']);
        config()->set('incoming_order.integration_client', 'shopnltees');
        config()->set('incoming_order.business_id', 1);

        Business::create([
            'business_name' => 'API Production',
            'contact_name' => 'Integration',
            'email' => 'integration@example.test',
            'status' => 1,
        ]);
    }

    protected function tearDown(): void
    {
        $path = public_path(sprintf(
            'uploads/images/api/v1/%s/%s.png',
            substr($this->artworkHash, 0, 2),
            $this->artworkHash,
        ));
        if (is_file($path)) {
            unlink($path);
        }
        $directory = dirname($path);
        if (is_dir($directory) && scandir($directory) === ['.', '..']) {
            rmdir($directory);
        }

        if ($this->originalSecret === false) {
            putenv('BUY_DTF_SECRET');
            unset($_ENV['BUY_DTF_SECRET'], $_SERVER['BUY_DTF_SECRET']);
        } else {
            putenv('BUY_DTF_SECRET='.$this->originalSecret);
            $_ENV['BUY_DTF_SECRET'] = $this->originalSecret;
            $_SERVER['BUY_DTF_SECRET'] = $this->originalSecret;
        }

        parent::tearDown();
    }

    public function test_capabilities_are_disabled_by_default_configuration(): void
    {
        config()->set('incoming_order.receiver_enabled', false);
        config()->set('incoming_order.job_label_enabled', false);

        $this->getJson('/api/incomingorder/capabilities')
            ->assertOk()
            ->assertHeader('Cache-Control', 'max-age=60, public')
            ->assertJsonPath('capabilities.receiver_idempotency_v1.enabled', false)
            ->assertJsonPath('capabilities.job_label_metadata_v1.enabled', false)
            ->assertJsonPath('capabilities.job_label_metadata_v1.supported_modes', ['metadata_only'])
            ->assertJsonPath('capabilities.job_label_metadata_v1.modes', []);
    }

    public function test_legacy_payload_keeps_its_existing_response_shape_and_persistence_path(): void
    {
        $payload = [
            'source_order_id' => 852,
            'file_name' => 'legacy-production-art.png',
            'shop' => 'Legacy Shop',
            'design' => [
                'image_url' => 'data://application/octet-stream;base64,'.base64_encode($this->artworkBytes),
                'width' => 1,
                'height' => 1,
                'quantity' => 2,
            ],
        ];
        $payload['signature'] = hash_hmac(
            'sha256',
            json_encode($payload, JSON_THROW_ON_ERROR),
            (string) config('incoming_order.shared_secret'),
        );

        $response = $this->postJson('/api/incomingorder', $payload)
            ->assertOk()
            ->assertJsonPath('success', true)
            ->assertJsonMissingPath('receiver')
            ->assertJsonMissingPath('job_label');

        $this->assertSame([
            'success',
            'duplicate',
            'file',
            'order_id',
            'dtfimage_id',
            'job_id',
            'file_size',
            'sha256',
            'orig_width_in',
            'orig_height_in',
            'width_ratio',
            'height_ratio',
        ], array_keys($response->json()));
        $this->assertDatabaseCount('incoming_order_jobs', 0, 'fuelmysql');
        $this->assertDatabaseCount('dtfimages', 1, 'fuelmysql');

        $stored = public_path(ltrim((string) $response->json('file'), '/'));
        if (is_file($stored)) {
            unlink($stored);
        }
    }

    public function test_receiver_capability_rejects_opt_in_requests_while_disabled_without_persistence(): void
    {
        config()->set('incoming_order.receiver_enabled', false);
        $this->bindArtworkFetcher();

        $this->submit($this->payload())
            ->assertStatus(503)
            ->assertJsonPath('error.reason', 'receiver_idempotency_v1_disabled');

        $this->assertDatabaseCount('incoming_order_jobs', 0, 'fuelmysql');
        $this->assertDatabaseCount('dtfimages', 0, 'fuelmysql');
    }

    public function test_oversized_v1_body_is_rejected_before_signature_or_persistence(): void
    {
        config()->set('incoming_order.request_max_bytes', 1024);
        $payload = $this->payload();
        $payload['shop'] = str_repeat('x', 1500);

        $this->submit($payload)
            ->assertStatus(413)
            ->assertJsonPath('error.code', 'request_too_large')
            ->assertJsonPath('error.reason', 'request_body_too_large');

        $this->assertDatabaseCount('incoming_order_jobs', 0, 'fuelmysql');
        $this->assertDatabaseCount('dtfimages', 0, 'fuelmysql');
    }

    public function test_key_only_v1_can_run_before_label_capability_is_enabled(): void
    {
        config()->set('incoming_order.job_label_enabled', false);
        $this->bindArtworkFetcher();
        $payload = $this->payload();
        unset($payload['job_label']);

        $this->submit($payload)
            ->assertOk()
            ->assertJsonMissingPath('job_label')
            ->assertJsonPath('receiver.status', 'completed');

        $job = IncomingOrderJob::firstOrFail();
        $this->assertNull($job->job_label_status);
        $this->assertNull($job->production_state);
    }

    public function test_optional_label_is_explicitly_ignored_while_label_capability_is_disabled(): void
    {
        config()->set('incoming_order.job_label_enabled', false);
        $this->bindArtworkFetcher();

        $this->submit($this->payload())
            ->assertOk()
            ->assertJsonPath('job_label.status', 'ignored')
            ->assertJsonPath('job_label.reason', 'capability_disabled');
    }

    public function test_required_label_is_rejected_while_label_capability_is_disabled(): void
    {
        config()->set('incoming_order.job_label_enabled', false);
        $fetcher = $this->bindArtworkFetcher();
        $payload = $this->payload();
        $payload['job_label']['required'] = true;

        $this->submit($payload)
            ->assertStatus(422)
            ->assertJsonPath('error.reason', 'capability_disabled');

        $this->assertSame(0, $fetcher->calls);
        $this->assertDatabaseCount('incoming_order_jobs', 0, 'fuelmysql');
    }

    public function test_metadata_only_job_is_frozen_without_modifying_original_artwork(): void
    {
        $fetcher = $this->bindArtworkFetcher();

        $response = $this->submit($this->payload())
            ->assertOk()
            ->assertJsonPath('success', true)
            ->assertJsonPath('receiver.status', 'completed')
            ->assertJsonPath('receiver.replayed', false)
            ->assertJsonPath('job_label.status', 'accepted')
            ->assertJsonPath('job_label.mode', 'metadata_only')
            ->assertJsonPath('job_label.artwork_modified', false)
            ->assertJsonPath('job_label.job_card.artifact', 'separate')
            ->assertJsonPath('job_label.job_card.status', 'pending_production')
            ->assertJsonPath('job_label.job_card.quantity', 1);

        $this->assertSame(1, $fetcher->calls);
        $job = IncomingOrderJob::firstOrFail();
        $image = DtfImage::firstOrFail();
        $this->assertSame('completed', $job->state);
        $this->assertSame('accepted', $job->job_label_status);
        $this->assertSame('pending', $job->production_state);
        $this->assertSame('1725', $job->job_label_metadata['order_number']);
        $this->assertSame($image->id, $job->dtfimage_id);
        $this->assertSame($this->artworkBytes, file_get_contents(public_path(ltrim($image->image, '/'))));
        $this->assertDatabaseHas('api_asset_records', [
            'incoming_order_job_id' => $job->id,
            'asset_role' => 'original',
            'retention_policy' => 'forever',
            'retention_enabled' => 0,
        ], 'fuelmysql');
        $this->assertArrayHasKey('job_label', $response->json());
    }

    public function test_transport_retry_replays_the_frozen_response_without_refetching_or_recreating(): void
    {
        $fetcher = $this->bindArtworkFetcher();
        $payload = $this->payload();

        $first = $this->submit($payload)->assertOk();
        $payload['sent_at'] = '2026-09-27T12:01:00Z';
        $payload['design']['image_url'] = 'https://artifacts.example.test/refreshed-token.png?token=two';
        $second = $this->submit($payload)
            ->assertOk()
            ->assertJsonPath('receiver.replayed', true);

        $this->assertSame($first->json('dtfimage_id'), $second->json('dtfimage_id'));
        $this->assertSame(1, $fetcher->calls);
        $this->assertDatabaseCount('incoming_order_jobs', 1, 'fuelmysql');
        $this->assertDatabaseCount('dtfimages', 1, 'fuelmysql');
    }

    public function test_expired_url_can_be_refreshed_after_retryable_403_without_idempotency_conflict(): void
    {
        $bytes = $this->artworkBytes;
        $fetcher = new class($bytes) extends BoundedArtworkFetcher
        {
            public int $calls = 0;

            public function __construct(private readonly string $bytes) {}

            public function fetch(
                string $initialUrl,
                string $owner,
                ?callable $heartbeat = null,
                ?int $deadlineNs = null,
            ): FetchedArtwork {
                $this->calls++;
                if ($this->calls === 1) {
                    throw new ArtworkFetchException('artwork_source_unavailable', true);
                }
                $directory = storage_path('app/private/incoming-orders/tmp/'.$owner);
                if (! is_dir($directory)) {
                    mkdir($directory, 0700, true);
                }
                $path = $directory.DIRECTORY_SEPARATOR.'refreshed-fixture.png';
                file_put_contents($path, $this->bytes);
                $heartbeat && $heartbeat();

                return new FetchedArtwork($path, 'artifacts.example.test', strlen($this->bytes), 'image/png');
            }
        };
        $this->app->instance(BoundedArtworkFetcher::class, $fetcher);

        $payload = $this->payload();
        $this->submit($payload)
            ->assertStatus(503)
            ->assertJsonPath('error.reason', 'artwork_source_unavailable');

        $payload['sent_at'] = '2026-09-27T12:02:00Z';
        $payload['design']['image_url'] = 'https://artifacts.example.test/refreshed.png?token=two';
        $this->submit($payload)
            ->assertOk()
            ->assertJsonPath('receiver.attempt_count', 2)
            ->assertJsonPath('receiver.status', 'completed');

        $this->assertSame(2, $fetcher->calls);
        $this->assertDatabaseCount('incoming_order_jobs', 1, 'fuelmysql');
        $this->assertDatabaseCount('dtfimages', 1, 'fuelmysql');
    }

    public function test_valid_ignored_label_replays_after_capability_enablement_with_omitted_required_default(): void
    {
        config()->set('incoming_order.job_label_enabled', false);
        $this->bindArtworkFetcher();
        $payload = $this->payload();
        unset($payload['job_label']['required']);

        $first = $this->submit($payload)
            ->assertOk()
            ->assertJsonPath('job_label.status', 'ignored')
            ->assertJsonPath('job_label.reason', 'capability_disabled');
        $fingerprint = $first->json('receiver.request_fingerprint');

        config()->set('incoming_order.job_label_enabled', true);
        $payload['sent_at'] = '2026-09-27T12:03:00Z';
        $payload['design']['image_url'] = 'https://artifacts.example.test/refreshed.png?token=three';
        $this->submit($payload)
            ->assertOk()
            ->assertJsonPath('receiver.replayed', true)
            ->assertJsonPath('receiver.request_fingerprint', $fingerprint)
            ->assertJsonPath('job_label.status', 'ignored')
            ->assertJsonPath('job_label.reason', 'capability_disabled');
    }

    public function test_attempt_exhaustion_status_and_reason_are_stable_on_every_later_retry(): void
    {
        config()->set('incoming_order.max_attempts', 1);
        $fetcher = new class extends BoundedArtworkFetcher
        {
            public function fetch(
                string $initialUrl,
                string $owner,
                ?callable $heartbeat = null,
                ?int $deadlineNs = null,
            ): FetchedArtwork {
                throw new ArtworkFetchException('artwork_source_unavailable', true);
            }
        };
        $this->app->instance(BoundedArtworkFetcher::class, $fetcher);
        $payload = $this->payload();

        $this->submit($payload)->assertStatus(503);
        foreach ([2, 3] as $attempt) {
            $this->submit($payload)
                ->assertStatus(503)
                ->assertHeader('Retry-After', '60')
                ->assertJsonPath('error.code', 'receiver_unavailable')
                ->assertJsonPath('error.reason', 'idempotency_attempts_exhausted');
        }
    }

    public function test_same_key_with_changed_semantic_payload_returns_409_without_fetch(): void
    {
        $fetcher = $this->bindArtworkFetcher();
        $payload = $this->payload();
        $this->submit($payload)->assertOk();

        $payload['file_name'] = 'different-production-art.png';
        $this->submit($payload)
            ->assertStatus(409)
            ->assertJsonPath('error.code', 'idempotency_conflict');

        $this->assertSame(1, $fetcher->calls);
        $this->assertDatabaseCount('dtfimages', 1, 'fuelmysql');
    }

    public function test_same_artwork_with_different_dispatches_and_labels_creates_distinct_jobs(): void
    {
        $this->bindArtworkFetcher();
        $first = $this->payload();
        $second = $this->payload();
        $second['idempotency_key'] = 'shopnltees:dispatch:00000000-0000-4000-8000-000000000002';
        $second['job_label']['color'] = 'Navy';

        $one = $this->submit($first)->assertOk();
        $two = $this->submit($second)->assertOk();

        $this->assertNotSame($one->json('dtfimage_id'), $two->json('dtfimage_id'));
        $this->assertSame($one->json('file'), $two->json('file'));
        $this->assertDatabaseCount('incoming_order_jobs', 2, 'fuelmysql');
        $this->assertSame(2, IncomingOrderJob::pluck('job_label_fingerprint')->unique()->count());
    }

    public function test_hash_mismatch_is_atomic_and_frozen_as_a_permanent_failure(): void
    {
        $this->bindArtworkFetcher();
        $payload = $this->payload();
        $payload['design']['sha256'] = str_repeat('0', 64);

        $this->submit($payload)
            ->assertStatus(422)
            ->assertJsonPath('error.reason', 'artwork_hash_mismatch');

        $this->assertDatabaseCount('dtfimages', 0, 'fuelmysql');
        $this->assertDatabaseCount('dtforders', 0, 'fuelmysql');
        $this->assertDatabaseHas('incoming_order_jobs', [
            'state' => 'permanent_failure',
            'last_error_code' => 'artwork_hash_mismatch',
            'dtfimage_id' => null,
        ], 'fuelmysql');
    }

    public function test_aspect_mismatch_never_falls_through_to_legacy_resizing(): void
    {
        $this->bindArtworkFetcher();
        $payload = $this->payload();
        $payload['design']['width'] = '2.0000';

        $this->submit($payload)
            ->assertStatus(422)
            ->assertJsonPath('error.reason', 'artwork_dimension_mismatch');

        $this->assertDatabaseCount('dtfimages', 0, 'fuelmysql');
    }

    public function test_optional_invalid_label_is_explicitly_ignored_but_artwork_job_continues(): void
    {
        $this->bindArtworkFetcher();
        $payload = $this->payload();
        $payload['job_label']['required'] = false;
        $payload['job_label']['mode'] = 'printed_strip';

        $this->submit($payload)
            ->assertOk()
            ->assertJsonPath('job_label.status', 'ignored')
            ->assertJsonPath('job_label.mode', null)
            ->assertJsonPath('job_label.reason', 'unsupported_mode')
            ->assertJsonPath('job_label.job_card.status', 'not_requested');

        $job = IncomingOrderJob::firstOrFail();
        $this->assertNull($job->job_label_metadata);
        $this->assertSame('ignored', $job->job_label_status);
        $this->assertDatabaseCount('dtfimages', 1, 'fuelmysql');
    }

    public function test_required_invalid_label_creates_no_reservation_order_or_job(): void
    {
        $fetcher = $this->bindArtworkFetcher();
        $payload = $this->payload();
        $payload['job_label']['required'] = true;
        $payload['job_label']['mode'] = 'printed_strip';

        $this->submit($payload)
            ->assertStatus(422)
            ->assertJsonPath('error.reason', 'unsupported_mode');

        $this->assertSame(0, $fetcher->calls);
        $this->assertDatabaseCount('incoming_order_jobs', 0, 'fuelmysql');
        $this->assertDatabaseCount('dtfimages', 0, 'fuelmysql');
        $this->assertDatabaseCount('dtforders', 0, 'fuelmysql');
    }

    public function test_duplicate_json_keys_are_rejected_before_signature_or_persistence(): void
    {
        $raw = '{"idempotency_key":"first","idempotency_key":"second"}';

        $this->call(
            'POST',
            '/api/incomingorder',
            [],
            [],
            [],
            ['CONTENT_TYPE' => 'application/json'],
            $raw,
        )->assertStatus(400)->assertJsonPath('error.reason', 'duplicate_json_key');

        $this->assertDatabaseCount('incoming_order_jobs', 0, 'fuelmysql');
    }

    public function test_json_content_type_accepts_parameters_but_rejects_prefix_and_suffix_types(): void
    {
        $this->bindArtworkFetcher();
        $raw = json_encode($this->signedPayload($this->payload()), JSON_THROW_ON_ERROR);

        $this->call('POST', '/api/incomingorder', [], [], [], [
            'CONTENT_TYPE' => 'application/json; charset=UTF-8',
        ], $raw)->assertOk();

        $payload = $this->payload();
        $payload['idempotency_key'] = 'shopnltees:dispatch:00000000-0000-4000-8000-000000000099';
        $badRaw = json_encode($this->signedPayload($payload), JSON_THROW_ON_ERROR);
        foreach (['application/jsonx', 'application/json-patch+json'] as $contentType) {
            $this->call('POST', '/api/incomingorder', [], [], [], [
                'CONTENT_TYPE' => $contentType,
            ], $badRaw)
                ->assertStatus(415)
                ->assertJsonPath('error.code', 'unsupported_media_type')
                ->assertJsonPath('error.reason', 'application_json_required');
        }
    }

    public function test_v1_signature_failures_use_the_structured_error_contract(): void
    {
        $payload = $this->payload();
        $payload['signature'] = str_repeat('0', 64);

        $this->postJson('/api/incomingorder', $payload)
            ->assertStatus(401)
            ->assertExactJson([
                'success' => false,
                'error' => [
                    'code' => 'authentication_failed',
                    'reason' => 'invalid_signature',
                ],
            ]);
    }

    public function test_unknown_v1_envelope_field_is_rejected_without_fetch(): void
    {
        $fetcher = $this->bindArtworkFetcher();
        $payload = $this->payload();
        $payload['unexpected'] = 'nope';

        $this->submit($payload)
            ->assertStatus(422)
            ->assertJsonPath('error.reason', 'unknown_field');

        $this->assertSame(0, $fetcher->calls);
    }

    public function test_customer_pii_is_not_persisted_for_an_optional_label(): void
    {
        $this->bindArtworkFetcher();
        $payload = $this->payload();
        $payload['job_label']['product_name'] = 'customer@example.com';

        $this->submit($payload)
            ->assertOk()
            ->assertJsonPath('job_label.status', 'ignored')
            ->assertJsonPath('job_label.reason', 'contains_pii');

        $job = IncomingOrderJob::firstOrFail();
        $this->assertNull($job->job_label_metadata);
        $this->assertStringNotContainsString('customer@example.com', json_encode($job->toArray()));
    }

    /** @return array<string, mixed> */
    private function payload(): array
    {
        return [
            'source_order_id' => 853,
            'file_name' => 'production-art.png',
            'shop' => 'Urey Local School Gear',
            'sent_at' => '2026-09-27T12:00:00Z',
            'idempotency_key' => 'shopnltees:dispatch:00000000-0000-4000-8000-000000000001',
            'design' => [
                'image_url' => 'https://artifacts.example.test/art.png?token=one',
                'sha256' => $this->artworkHash,
                'width' => '1.0000',
                'height' => '1.0000',
                'quantity' => 1,
            ],
            'job_label' => [
                'version' => 1,
                'required' => false,
                'mode' => 'metadata_only',
                'order_number' => '1725',
                'order_item_id' => 1671,
                'production_print_snapshot_id' => 31,
                'product_name' => 'Urey Cheer Port Authority Jacket',
                'product_sku' => null,
                'color' => 'Black/Light Oxford',
                'size' => 'S',
                'placement' => 'Full Back',
                'quantity' => 1,
                'shop_domain' => 'urey.localschoolgear.com',
            ],
        ];
    }

    private function submit(array $payload): TestResponse
    {
        return $this->postJson('/api/incomingorder', $this->signedPayload($payload));
    }

    /** @return array<string, mixed> */
    private function signedPayload(array $payload): array
    {
        $signingObject = json_decode(json_encode($payload, JSON_THROW_ON_ERROR), false, 64, JSON_THROW_ON_ERROR);
        $payload['signature'] = hash_hmac(
            'sha256',
            app(JsonCanonicalizer::class)->canonicalize($signingObject),
            (string) config('incoming_order.shared_secret'),
        );

        return $payload;
    }

    private function bindArtworkFetcher(): BoundedArtworkFetcher
    {
        $bytes = $this->artworkBytes;
        $fetcher = new class($bytes) extends BoundedArtworkFetcher
        {
            public int $calls = 0;

            public function __construct(private readonly string $bytes) {}

            public function fetch(
                string $initialUrl,
                string $owner,
                ?callable $heartbeat = null,
                ?int $deadlineNs = null,
            ): FetchedArtwork {
                $this->calls++;
                $directory = storage_path('app/private/incoming-orders/tmp/'.$owner);
                if (! is_dir($directory)) {
                    mkdir($directory, 0700, true);
                }
                $path = $directory.DIRECTORY_SEPARATOR.'fixture.png';
                file_put_contents($path, $this->bytes);
                $heartbeat && $heartbeat();

                return new FetchedArtwork(
                    temporaryPath: $path,
                    approvedHost: 'artifacts.example.test',
                    bytes: strlen($this->bytes),
                    declaredContentType: 'image/png',
                );
            }
        };
        $this->app->instance(BoundedArtworkFetcher::class, $fetcher);

        return $fetcher;
    }
}
