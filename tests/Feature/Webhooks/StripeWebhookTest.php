<?php

namespace Tests\Feature\Webhooks;

use App\Jobs\ProcessStripePayoutWebhook;
use App\Models\StripeSyncLog;
use App\Models\StripeWebhookEvent;
use App\Services\QboService;
use App\Services\StripePayoutService;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Queue;
use Tests\TestCase;

class StripeWebhookTest extends TestCase
{
    private array $originalEnvironment = [];

    protected function setUp(): void
    {
        parent::setUp();

        foreach ([
            'STRIPE_WEBHOOK_SECRET_PROD',
            'STRIPE_WEBHOOK_SECRET_DEV',
            'STRIPE_WEBHOOK_SECRET',
        ] as $name) {
            $this->rememberAndSetEnvironment($name, '');
        }

        config()->set('services.stripe.webhook_secret', 'whsec_primary_step1');
        config()->set('services.stripe.webhook_secrets', []);

        Queue::fake();
        Http::preventStrayRequests();

        // A payout job must remain queued during the HTTP request. Resolving either
        // integration service here would mean the webhook has started outbound work.
        $this->app->bind(StripePayoutService::class, static function () {
            throw new \RuntimeException('Stripe payout work ran inside the webhook request.');
        });
        $this->app->bind(QboService::class, static function () {
            throw new \RuntimeException('QuickBooks work ran inside the webhook request.');
        });
    }

    protected function tearDown(): void
    {
        foreach ($this->originalEnvironment as $name => $original) {
            if ($original === false) {
                putenv($name);
                unset($_ENV[$name], $_SERVER[$name]);

                continue;
            }

            putenv("{$name}={$original}");
            $_ENV[$name] = $original;
            $_SERVER[$name] = $original;
        }

        parent::tearDown();
    }

    public function test_valid_payout_signature_records_event_and_queues_work_without_outbound_http(): void
    {
        $payload = $this->eventPayload('evt_valid_step1');

        $response = $this->postStripeWebhook(
            $payload,
            $this->signatureFor($payload, 'whsec_primary_step1')
        );

        $response
            ->assertOk()
            ->assertExactJson(['message' => 'Webhook handled']);

        $event = StripeWebhookEvent::query()->sole();
        $this->assertSame('evt_valid_step1', $event->stripe_event_id);
        $this->assertSame('payout.paid', $event->type);
        $this->assertNull($event->processed_at);

        $this->assertSame(1, StripeSyncLog::query()->count());
        $this->assertSame('evt_valid_step1', StripeSyncLog::query()->value('stripe_id'));

        Queue::assertPushed(ProcessStripePayoutWebhook::class, 1);
        Http::assertNothingSent();
    }

    public function test_rotation_fallback_secret_is_accepted(): void
    {
        config()->set('services.stripe.webhook_secret', 'whsec_old_step1');
        config()->set('services.stripe.webhook_secrets', ['whsec_rotated_step1']);
        $payload = $this->eventPayload('evt_rotation_step1');

        $this->postStripeWebhook(
            $payload,
            $this->signatureFor($payload, 'whsec_rotated_step1')
        )->assertOk();

        $this->assertSame(1, StripeWebhookEvent::query()->count());
        Queue::assertPushed(ProcessStripePayoutWebhook::class, 1);
        Http::assertNothingSent();
    }

    public function test_invalid_signature_is_rejected_without_recording_or_queueing(): void
    {
        $payload = $this->eventPayload('evt_invalid_step1');

        $this->postStripeWebhook(
            $payload,
            $this->signatureFor($payload, 'whsec_not_configured')
        )
            ->assertStatus(400)
            ->assertExactJson(['error' => 'Invalid signature']);

        $this->assertSame(0, StripeWebhookEvent::query()->count());
        $this->assertSame(0, StripeSyncLog::query()->count());
        Queue::assertNothingPushed();
        Http::assertNothingSent();
    }

    public function test_stale_signature_is_rejected_without_recording_or_queueing(): void
    {
        $payload = $this->eventPayload('evt_stale_step1');
        $staleTimestamp = time() - 301;

        $this->postStripeWebhook(
            $payload,
            $this->signatureFor($payload, 'whsec_primary_step1', $staleTimestamp)
        )
            ->assertStatus(400)
            ->assertExactJson(['error' => 'Invalid signature']);

        $this->assertSame(0, StripeWebhookEvent::query()->count());
        $this->assertSame(0, StripeSyncLog::query()->count());
        Queue::assertNothingPushed();
        Http::assertNothingSent();
    }

    public function test_sequential_duplicate_is_acknowledged_without_a_second_record_or_job(): void
    {
        $payload = $this->eventPayload('evt_duplicate_step1');
        $signature = $this->signatureFor($payload, 'whsec_primary_step1');

        $this->postStripeWebhook($payload, $signature)
            ->assertOk()
            ->assertExactJson(['message' => 'Webhook handled']);

        $this->postStripeWebhook($payload, $signature)
            ->assertOk()
            ->assertExactJson(['message' => 'Event already processed']);

        $this->assertSame(1, StripeWebhookEvent::query()->count());
        $this->assertSame(1, StripeSyncLog::query()->count());
        Queue::assertPushed(ProcessStripePayoutWebhook::class, 1);
        Http::assertNothingSent();
    }

    public function test_balance_available_event_is_marked_processed_without_queueing_work(): void
    {
        $payload = $this->eventPayload(
            'evt_balance_step1',
            'balance.available',
            ['object' => 'balance']
        );

        $this->postStripeWebhook(
            $payload,
            $this->signatureFor($payload, 'whsec_primary_step1')
        )->assertOk();

        $event = StripeWebhookEvent::query()->sole();
        $this->assertNotNull($event->processed_at);
        Queue::assertNothingPushed();
        Http::assertNothingSent();
    }

    private function eventPayload(
        string $eventId,
        string $type = 'payout.paid',
        ?array $dataObject = null
    ): string {
        $dataObject ??= [
            'id' => 'po_step1',
            'object' => 'payout',
            'status' => 'paid',
        ];

        return (string) json_encode([
            'id' => $eventId,
            'object' => 'event',
            'api_version' => '2024-06-20',
            'created' => time(),
            'data' => [
                'object' => $dataObject,
            ],
            'livemode' => false,
            'pending_webhooks' => 1,
            'type' => $type,
        ], JSON_THROW_ON_ERROR);
    }

    private function signatureFor(string $payload, string $secret, ?int $timestamp = null): string
    {
        $timestamp ??= time();
        $signature = hash_hmac('sha256', "{$timestamp}.{$payload}", $secret);

        return "t={$timestamp},v1={$signature}";
    }

    private function postStripeWebhook(string $payload, string $signature)
    {
        return $this->call(
            'POST',
            '/api/stripe/webhook',
            [],
            [],
            [],
            [
                'CONTENT_TYPE' => 'application/json',
                'HTTP_STRIPE_SIGNATURE' => $signature,
            ],
            $payload
        );
    }

    private function rememberAndSetEnvironment(string $name, string $value): void
    {
        $this->originalEnvironment[$name] = getenv($name);
        putenv("{$name}={$value}");
        $_ENV[$name] = $value;
        $_SERVER[$name] = $value;
    }
}
