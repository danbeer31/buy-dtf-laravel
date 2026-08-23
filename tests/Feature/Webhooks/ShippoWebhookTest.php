<?php

namespace Tests\Feature\Webhooks;

use App\Mail\OrderDelivered;
use App\Mail\OrderOutForDelivery;
use App\Mail\OrderShipped;
use App\Models\Business;
use App\Models\DtfOrder;
use App\Models\User;
use Illuminate\Support\Facades\Mail;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class ShippoWebhookTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        Mail::fake();
    }

    public static function trackingStatuses(): array
    {
        return [
            'in transit' => ['TRANSIT', 11, OrderShipped::class],
            'out for delivery' => ['OUT_FOR_DELIVERY', 12, OrderOutForDelivery::class],
            'delivered' => ['DELIVERED', 13, OrderDelivered::class],
        ];
    }

    #[DataProvider('trackingStatuses')]
    public function test_tracking_update_changes_status_and_sends_expected_email(
        string $shippoStatus,
        int $orderStatus,
        string $mailableClass
    ): void {
        $order = $this->createOrder(status: 4);

        $this->postJson('/webhooks/shippo', $this->trackUpdatedPayload(
            $order->tracking_number,
            $shippoStatus
        ))
            ->assertOk()
            ->assertExactJson(['status' => 'success']);

        $this->assertSame($orderStatus, (int) $order->fresh()->status);
        Mail::assertSent($mailableClass, function ($mail) use ($order): bool {
            return $mail->hasTo('shippo-step1@example.test')
                && $mail->order->is($order);
        });
        Mail::assertSentCount(1);
    }

    public function test_repeated_same_status_does_not_send_duplicate_email(): void
    {
        $order = $this->createOrder(status: 13);

        $this->postJson('/webhooks/shippo', $this->trackUpdatedPayload(
            $order->tracking_number,
            'DELIVERED'
        ))->assertOk();

        $this->assertSame(13, (int) $order->fresh()->status);
        Mail::assertNothingSent();
    }

    public function test_out_of_order_transit_event_currently_regresses_delivered_order(): void
    {
        $order = $this->createOrder(status: 13);

        $this->postJson('/webhooks/shippo', $this->trackUpdatedPayload(
            $order->tracking_number,
            'TRANSIT'
        ))->assertOk();

        // Characterizes the current behavior for later webhook hardening.
        $this->assertSame(11, (int) $order->fresh()->status);
        Mail::assertSent(OrderShipped::class, 1);
    }

    public function test_missing_tracking_number_is_rejected_without_email(): void
    {
        $this->postJson('/webhooks/shippo', [
            'event' => 'track_updated',
            'data' => ['tracking_status' => ['status' => 'DELIVERED']],
        ])
            ->assertStatus(400)
            ->assertExactJson(['error' => 'No tracking number']);

        Mail::assertNothingSent();
    }

    public function test_unknown_tracking_number_returns_not_found_without_email(): void
    {
        $this->postJson('/webhooks/shippo', $this->trackUpdatedPayload(
            'unknown-step1',
            'DELIVERED'
        ))
            ->assertStatus(404)
            ->assertExactJson(['error' => 'Order not found']);

        Mail::assertNothingSent();
    }

    public function test_unhandled_event_is_ignored_without_changing_order_or_sending_email(): void
    {
        $order = $this->createOrder(status: 4);

        $this->postJson('/webhooks/shippo', [
            'event' => 'transaction_created',
            'data' => ['tracking_number' => $order->tracking_number],
        ])
            ->assertOk()
            ->assertExactJson(['status' => 'ignored']);

        $this->assertSame(4, (int) $order->fresh()->status);
        Mail::assertNothingSent();
    }

    private function createOrder(int $status): DtfOrder
    {
        $user = User::factory()->create();
        $business = Business::query()->create([
            'user_id' => $user->id,
            'business_name' => 'Shippo Step 1',
            'contact_name' => 'Test Recipient',
            'email' => 'shippo-step1@example.test',
            'phone' => '5555550100',
            'address' => '1 Test Way',
            'city' => 'La Porte',
            'state' => 'IN',
            'zip' => '46350',
            'status' => 'confirmed',
        ]);

        return DtfOrder::query()->create([
            'business_id' => $business->id,
            'order_date' => now(),
            'status' => $status,
            'tracking_number' => 'track-step1-'.uniqid(),
        ]);
    }

    private function trackUpdatedPayload(string $trackingNumber, string $status): array
    {
        return [
            'event' => 'track_updated',
            'data' => [
                'tracking_number' => $trackingNumber,
                'tracking_status' => ['status' => $status],
            ],
        ];
    }
}
