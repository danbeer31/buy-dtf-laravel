<?php

namespace Tests\Feature\Checkout;

use App\Mail\AdminNewOrderPlaced;
use App\Mail\OrderPlaced;
use App\Models\Business;
use App\Models\DtfOrder;
use App\Models\Setting;
use App\Models\User;
use App\Services\QboService;
use Illuminate\Support\Facades\Mail;
use Mockery;
use Tests\TestCase;

class InvoiceCheckoutTest extends TestCase
{
    public function test_invoice_checkout_completes_locally_when_qbo_creation_fails(): void
    {
        Mail::fake();

        [$user, $business] = $this->customerWithBusiness('owner@example.test');
        $order = DtfOrder::create([
            'business_id' => $business->id,
            'order_date' => now(),
            'status' => 1,
            'total_price' => 125.50,
        ]);

        Setting::create([
            'key' => 'qbo_auto_invoice_on_checkout',
            'value' => '1',
        ]);

        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldReceive('createInvoice')
            ->once()
            ->withArgs(fn (Business $actualBusiness, DtfOrder $actualOrder) => $actualBusiness->is($business) && $actualOrder->is($order)
            )
            ->andThrow(new \RuntimeException('QBO unavailable during test'));
        $this->app->instance(QboService::class, $qbo);

        $response = $this->actingAs($user)->post(
            route('checkout.invoice.complete', ['order' => $order])
        );

        $response->assertRedirect(
            route('checkout.complete', ['pi' => 'invoice_'.$order->id])
        );
        $this->assertSame(2, (int) $order->fresh()->status);
        Mail::assertSent(OrderPlaced::class);
        Mail::assertSent(AdminNewOrderPlaced::class);
    }

    public function test_customer_cannot_complete_another_business_invoice(): void
    {
        [$user] = $this->customerWithBusiness('first@example.test');
        [, $otherBusiness] = $this->customerWithBusiness('second@example.test');

        $order = DtfOrder::create([
            'business_id' => $otherBusiness->id,
            'order_date' => now(),
            'status' => 1,
            'total_price' => 25,
        ]);

        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('createInvoice');
        $this->app->instance(QboService::class, $qbo);

        $this->actingAs($user)
            ->post(route('checkout.invoice.complete', ['order' => $order]))
            ->assertForbidden();

        $this->assertSame(1, (int) $order->fresh()->status);
    }

    /** @return array{User, Business} */
    private function customerWithBusiness(string $email): array
    {
        $business = Business::create([
            'business_name' => 'Business '.$email,
            'contact_name' => 'Checkout Owner',
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
}
