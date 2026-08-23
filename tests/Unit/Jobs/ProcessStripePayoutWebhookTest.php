<?php

namespace Tests\Unit\Jobs;

use App\Jobs\ProcessStripePayoutWebhook;
use App\Models\StripePayout;
use App\Models\StripeWebhookEvent;
use App\Services\QboService;
use App\Services\StripePayoutService;
use Mockery;
use RuntimeException;
use Tests\TestCase;

class ProcessStripePayoutWebhookTest extends TestCase
{
    public function test_missing_event_is_a_no_op(): void
    {
        $payoutService = Mockery::mock(StripePayoutService::class);
        $payoutService->shouldNotReceive('syncPayout');
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('recordStripePayoutTransfer');

        (new ProcessStripePayoutWebhook(999999))->handle($payoutService, $qbo);

        $this->addToAssertionCount(1);
    }

    public function test_already_processed_event_is_a_no_op(): void
    {
        $event = $this->createPayoutEvent([
            'processed_at' => now(),
        ]);
        $payoutService = Mockery::mock(StripePayoutService::class);
        $payoutService->shouldNotReceive('syncPayout');
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('recordStripePayoutTransfer');

        (new ProcessStripePayoutWebhook($event->id))->handle($payoutService, $qbo);

        $this->assertNotNull($event->fresh()->processed_at);
    }

    public function test_paid_payout_syncs_transfer_and_marks_event_processed(): void
    {
        $event = $this->createPayoutEvent();
        $payout = new StripePayout([
            'stripe_payout_id' => 'po_step1',
            'status' => 'paid',
            'qbo_transfer_id' => null,
        ]);
        $payoutService = Mockery::mock(StripePayoutService::class);
        $payoutService
            ->shouldReceive('syncPayout')
            ->once()
            ->with('po_step1')
            ->andReturn($payout);
        $qbo = Mockery::mock(QboService::class);
        $qbo
            ->shouldReceive('recordStripePayoutTransfer')
            ->once()
            ->with($payout);

        (new ProcessStripePayoutWebhook($event->id))->handle($payoutService, $qbo);

        $this->assertNotNull($event->fresh()->processed_at);
    }

    public function test_failed_payout_does_not_create_qbo_transfer_and_marks_event_processed(): void
    {
        $event = $this->createPayoutEvent([
            'type' => 'payout.failed',
            'payload' => $this->payoutPayload('failed'),
        ]);
        $payout = new StripePayout([
            'stripe_payout_id' => 'po_step1',
            'status' => 'failed',
            'qbo_transfer_id' => null,
        ]);
        $payoutService = Mockery::mock(StripePayoutService::class);
        $payoutService
            ->shouldReceive('syncPayout')
            ->once()
            ->with('po_step1')
            ->andReturn($payout);
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('recordStripePayoutTransfer');

        (new ProcessStripePayoutWebhook($event->id))->handle($payoutService, $qbo);

        $this->assertNotNull($event->fresh()->processed_at);
    }

    public function test_stripe_sync_exception_propagates_and_leaves_event_unprocessed(): void
    {
        $event = $this->createPayoutEvent();
        $payoutService = Mockery::mock(StripePayoutService::class);
        $payoutService
            ->shouldReceive('syncPayout')
            ->once()
            ->with('po_step1')
            ->andThrow(new RuntimeException('Stripe unavailable'));
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('recordStripePayoutTransfer');

        try {
            (new ProcessStripePayoutWebhook($event->id))->handle($payoutService, $qbo);
            $this->fail('The Stripe exception should be rethrown for the queue to retry.');
        } catch (RuntimeException $exception) {
            $this->assertSame('Stripe unavailable', $exception->getMessage());
        }

        $this->assertNull($event->fresh()->processed_at);
    }

    public function test_qbo_exception_propagates_and_leaves_event_unprocessed(): void
    {
        $event = $this->createPayoutEvent();
        $payout = new StripePayout([
            'stripe_payout_id' => 'po_step1',
            'status' => 'paid',
            'qbo_transfer_id' => null,
        ]);
        $payoutService = Mockery::mock(StripePayoutService::class);
        $payoutService
            ->shouldReceive('syncPayout')
            ->once()
            ->with('po_step1')
            ->andReturn($payout);
        $qbo = Mockery::mock(QboService::class);
        $qbo
            ->shouldReceive('recordStripePayoutTransfer')
            ->once()
            ->with($payout)
            ->andThrow(new RuntimeException('QuickBooks unavailable'));

        try {
            (new ProcessStripePayoutWebhook($event->id))->handle($payoutService, $qbo);
            $this->fail('The QuickBooks exception should be rethrown for the queue to retry.');
        } catch (RuntimeException $exception) {
            $this->assertSame('QuickBooks unavailable', $exception->getMessage());
        }

        $this->assertNull($event->fresh()->processed_at);
    }

    public function test_malformed_payout_payload_is_a_no_op_and_remains_unprocessed(): void
    {
        $event = $this->createPayoutEvent([
            'payload' => ['data' => ['object' => ['object' => 'charge']]],
        ]);
        $payoutService = Mockery::mock(StripePayoutService::class);
        $payoutService->shouldNotReceive('syncPayout');
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('recordStripePayoutTransfer');

        (new ProcessStripePayoutWebhook($event->id))->handle($payoutService, $qbo);

        $this->assertNull($event->fresh()->processed_at);
    }

    private function createPayoutEvent(array $overrides = []): StripeWebhookEvent
    {
        return StripeWebhookEvent::query()->create(array_merge([
            'stripe_event_id' => 'evt_'.str_replace('.', '_', uniqid('', true)),
            'type' => 'payout.paid',
            'payload' => $this->payoutPayload('paid'),
            'processed_at' => null,
        ], $overrides));
    }

    private function payoutPayload(string $status): array
    {
        return [
            'data' => [
                'object' => [
                    'id' => 'po_step1',
                    'object' => 'payout',
                    'status' => $status,
                ],
            ],
        ];
    }
}
