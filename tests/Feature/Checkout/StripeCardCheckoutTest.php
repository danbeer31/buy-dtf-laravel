<?php

namespace Tests\Feature\Checkout;

use App\Models\Business;
use App\Models\BusinessSetting;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\PaymentInfo;
use App\Models\User;
use App\Services\QboService;
use Illuminate\Support\Facades\Mail;
use Mockery;
use Stripe\ApiRequestor;
use Stripe\HttpClient\ClientInterface;
use Stripe\Stripe;
use Tests\TestCase;

class StripeCardCheckoutTest extends TestCase
{
    private ?object $recordedFeeEntry = null;

    protected function tearDown(): void
    {
        ApiRequestor::setHttpClient(null);
        ApiRequestor::resetTelemetry();
        Stripe::setApiKey('');

        parent::tearDown();
    }

    public function test_starting_card_payment_creates_the_expected_intent_and_persists_totals(): void
    {
        [$user, $business, $order] = $this->customerWithOpenOrder();

        $stripe = $this->fakeStripe([
            $this->paymentIntentPayload(
                id: 'pi_step1_start',
                order: $order,
                status: 'requires_payment_method',
                amount: 1325,
                clientSecret: 'pi_step1_start_secret_test'
            ),
        ]);

        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('createInvoice');
        $qbo->shouldNotReceive('recordPayment');
        $qbo->shouldNotReceive('recordStripeFee');
        $this->app->instance(QboService::class, $qbo);

        $this->actingAs($user)
            ->postJson(route('checkout.payment'), [
                'shipping_rate_id' => 'shippo_rate_step1',
                'shipping_cost' => 3.25,
                'shipping_service_name' => 'UPS Ground',
                'payment_method_id' => 2,
            ])
            ->assertOk()
            ->assertExactJson([
                'client_secret' => 'pi_step1_start_secret_test',
                'stripe_publishable_key' => config('services.stripe.key'),
            ]);

        $order->refresh();

        $this->assertSame(10.0, $order->price);
        $this->assertSame(3.25, $order->shipping_cost);
        $this->assertSame(13.25, $order->total_price);
        $this->assertSame(0.0, $order->sales_tax);
        $this->assertSame(2, (int) $order->payment_method_id);
        $this->assertSame('UPS Ground', $order->shipping_method);
        $this->assertSame('UPS Ground', $order->shippo_service_name);

        $this->assertCount(1, $stripe->requests);
        $this->assertSame('post', $stripe->requests[0]['method']);
        $this->assertStringEndsWith('/v1/payment_intents', $stripe->requests[0]['url']);
        $this->assertSame(1325, $stripe->requests[0]['params']['amount']);
        $this->assertSame('usd', $stripe->requests[0]['params']['currency']);
        $this->assertSame($order->id, $stripe->requests[0]['params']['metadata']['order_id']);
        $this->assertSame($business->id, $stripe->requests[0]['params']['metadata']['business_id']);
        $this->assertDatabaseCount('paymentinfos', 0);
    }

    public function test_non_succeeded_card_payment_does_not_mark_the_order_paid(): void
    {
        [$user, , $order] = $this->customerWithOpenOrder();

        $stripe = $this->fakeStripe([
            $this->paymentIntentPayload(
                id: 'pi_step1_processing',
                order: $order,
                status: 'processing',
                amount: 1325
            ),
        ]);

        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldNotReceive('createInvoice');
        $qbo->shouldNotReceive('recordPayment');
        $qbo->shouldNotReceive('recordStripeFee');
        $this->app->instance(QboService::class, $qbo);

        $this->actingAs($user)
            ->get(route('checkout.complete', ['pi' => 'pi_step1_processing']))
            ->assertRedirect(route('cart.index'))
            ->assertSessionHas('error', 'Payment has not succeeded.');

        $this->assertSame(1, (int) $order->fresh()->status);
        $this->assertDatabaseCount('paymentinfos', 0);
        $this->assertCount(1, $stripe->requests);
    }

    public function test_succeeded_card_payment_records_payment_order_metrics_and_qbo_results(): void
    {
        Mail::fake();

        [$user, $business, $order] = $this->customerWithOpenOrder();
        $order->update([
            'shipping_cost' => 3.25,
            'price' => 10,
            'total_price' => 13.25,
        ]);

        $stripe = $this->fakeStripe($this->successfulStripeResponses($order));
        $this->mockSuccessfulQboSync($business, $order);

        $this->actingAs($user)
            ->get(route('checkout.complete', ['pi' => 'pi_step1_success']))
            ->assertOk()
            ->assertViewIs('checkout.complete')
            ->assertViewHas('order', fn (DtfOrder $viewOrder): bool => $viewOrder->is($order));

        $order->refresh();
        $payment = PaymentInfo::query()->where('dtforder_id', $order->id)->sole();

        $this->assertSame(2, (int) $order->status);
        $this->assertSame(200.0, $order->square_inches);
        $this->assertEqualsWithDelta(11.090909, $order->linear_inches, 0.0001);
        $this->assertEqualsWithDelta(1.86, $order->weight, 0.0001);
        $this->assertSame('qbo_invoice_step1', $order->qbo_invoice_id);
        $this->assertSame('Stripe', $payment->processor);
        $this->assertSame('pi_step1_success', $payment->processor_confirm);
        $this->assertSame('ch_step1_success', $payment->stripe_charge_id);
        $this->assertSame(13.25, $payment->amount);
        $this->assertSame('complete', $payment->status);
        $this->assertEqualsWithDelta(1.25, (float) $payment->stripe_fee, 0.0001);
        $this->assertSame('qbo_payment_step1', $payment->qbo_payment_id);
        $this->assertSame('qbo_fee_step1', $payment->qbo_fee_expense_id);
        $this->assertNotNull($this->recordedFeeEntry);
        $this->assertEqualsWithDelta(1.25, (float) $this->recordedFeeEntry->fee, 0.0001);
        $this->assertSame('ch_step1_success', $this->recordedFeeEntry->stripe_transaction_id);
        $this->assertCount(2, $stripe->requests);
        $this->assertStringEndsWith('/v1/payment_intents/pi_step1_success', $stripe->requests[0]['url']);
        $this->assertStringEndsWith('/v1/balance_transactions/txn_step1_success', $stripe->requests[1]['url']);
    }

    public function test_replaying_a_succeeded_completion_does_not_duplicate_local_or_qbo_records(): void
    {
        Mail::fake();

        [$user, $business, $order] = $this->customerWithOpenOrder();
        $order->update([
            'shipping_cost' => 3.25,
            'price' => 10,
            'total_price' => 13.25,
        ]);

        $responses = $this->successfulStripeResponses($order);
        $responses[] = $this->paymentIntentPayload(
            id: 'pi_step1_success',
            order: $order,
            status: 'succeeded',
            amount: 1325,
            chargeId: 'ch_step1_success',
            balanceTransactionId: 'txn_step1_success'
        );

        $stripe = $this->fakeStripe($responses);
        $this->mockSuccessfulQboSync($business, $order);

        $url = route('checkout.complete', ['pi' => 'pi_step1_success']);

        $this->actingAs($user)->get($url)->assertOk();
        $this->actingAs($user)->get($url)->assertOk();

        $this->assertSame(2, (int) $order->fresh()->status);
        $this->assertSame(1, PaymentInfo::query()->where('dtforder_id', $order->id)->count());
        $this->assertCount(3, $stripe->requests);
    }

    /** @return array{User, Business, DtfOrder} */
    private function customerWithOpenOrder(): array
    {
        $business = Business::query()->create([
            'business_name' => 'Step 1 Card Checkout',
            'contact_name' => 'Checkout Owner',
            'email' => 'card-checkout@example.test',
            'status' => 1,
            'tax_exempt' => true,
        ]);

        BusinessSetting::query()->create([
            'business_id' => $business->id,
            'rate' => 0.05,
        ]);

        $user = User::factory()->create([
            'email' => $business->email,
            'role' => 'customer',
            'fuel_business_id' => $business->id,
        ]);

        $order = DtfOrder::query()->create([
            'business_id' => $business->id,
            'order_date' => now(),
            'payment_method_id' => 2,
            'status' => 1,
        ]);

        DtfImage::query()->create([
            'dtforder_id' => $order->id,
            'image' => 'step1-card-checkout.png',
            'width' => 10,
            'height' => 10,
            'quantity' => 2,
            'production' => 0,
        ]);

        return [$user, $business, $order];
    }

    /** @return list<array<string, mixed>> */
    private function successfulStripeResponses(DtfOrder $order): array
    {
        return [
            $this->paymentIntentPayload(
                id: 'pi_step1_success',
                order: $order,
                status: 'succeeded',
                amount: 1325,
                chargeId: 'ch_step1_success',
                balanceTransactionId: 'txn_step1_success'
            ),
            [
                'id' => 'txn_step1_success',
                'object' => 'balance_transaction',
                'amount' => 1325,
                'currency' => 'usd',
                'fee' => 125,
                'net' => 1200,
                'status' => 'available',
                'type' => 'charge',
            ],
        ];
    }

    /** @return array<string, mixed> */
    private function paymentIntentPayload(
        string $id,
        DtfOrder $order,
        string $status,
        int $amount,
        ?string $clientSecret = null,
        ?string $chargeId = null,
        ?string $balanceTransactionId = null
    ): array {
        return [
            'id' => $id,
            'object' => 'payment_intent',
            'amount' => $amount,
            'amount_received' => $status === 'succeeded' ? $amount : 0,
            'client_secret' => $clientSecret,
            'currency' => 'usd',
            'metadata' => [
                'order_id' => (string) $order->id,
                'business_id' => (string) $order->business_id,
            ],
            'latest_charge' => $chargeId === null ? null : [
                'id' => $chargeId,
                'object' => 'charge',
                'balance_transaction' => [
                    'id' => $balanceTransactionId,
                    'object' => 'balance_transaction',
                ],
            ],
            'status' => $status,
        ];
    }

    private function fakeStripe(array $responses): FakeStripeClient
    {
        config()->set('services.stripe.secret', 'stripe-secret-test-only');
        config()->set('services.stripe.key', 'stripe-publishable-test-only');

        $client = new FakeStripeClient($responses);
        ApiRequestor::setHttpClient($client);
        ApiRequestor::resetTelemetry();

        return $client;
    }

    private function mockSuccessfulQboSync(Business $business, DtfOrder $order): void
    {
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldReceive('createInvoice')
            ->once()
            ->withArgs(fn (Business $actualBusiness, DtfOrder $actualOrder): bool => $actualBusiness->is($business) && $actualOrder->is($order))
            ->andReturnUsing(function (Business $actualBusiness, DtfOrder $actualOrder): array {
                $actualOrder->update([
                    'qbo_invoice_id' => 'qbo_invoice_step1',
                    'qbo_invoice_number' => 'INV-STEP1',
                ]);

                return ['Id' => 'qbo_invoice_step1', 'DocNumber' => 'INV-STEP1'];
            });
        $qbo->shouldReceive('recordPayment')
            ->once()
            ->withArgs(fn (DtfOrder $actualOrder, float $amount, string $reference, float $fee): bool => $actualOrder->is($order)
                && abs($amount - 13.25) < 0.0001
                && $reference === 'pi_step1_success'
                && abs($fee - 1.25) < 0.0001)
            ->andReturnUsing(function (DtfOrder $actualOrder): array {
                PaymentInfo::query()
                    ->where('dtforder_id', $actualOrder->id)
                    ->latest('id')
                    ->firstOrFail()
                    ->update(['qbo_payment_id' => 'qbo_payment_step1']);

                return ['Id' => 'qbo_payment_step1'];
            });
        $qbo->shouldReceive('recordStripeFee')
            ->once()
            ->andReturnUsing(function (object $entry) use ($order): array {
                $this->recordedFeeEntry = $entry;
                $updated = ($entry->update)(['qbo_expense_id' => 'qbo_fee_step1']);

                $this->assertTrue($updated);
                $this->assertSame(
                    'qbo_fee_step1',
                    PaymentInfo::query()->where('dtforder_id', $order->id)->latest('id')->value('qbo_fee_expense_id')
                );

                return ['Id' => 'qbo_fee_step1'];
            });

        $this->app->instance(QboService::class, $qbo);
    }
}

final class FakeStripeClient implements ClientInterface
{
    /** @var list<array{method: string, url: string, headers: array, params: array, has_file: bool, api_mode: string}> */
    public array $requests = [];

    /** @param list<array<string, mixed>> $responses */
    public function __construct(private array $responses) {}

    public function request($method, $absUrl, $headers, $params, $hasFile, $apiMode = 'v1'): array
    {
        $this->requests[] = [
            'method' => $method,
            'url' => $absUrl,
            'headers' => $headers,
            'params' => $params,
            'has_file' => $hasFile,
            'api_mode' => $apiMode,
        ];

        if ($this->responses === []) {
            throw new \RuntimeException("Unexpected Stripe request: {$method} {$absUrl}");
        }

        return [json_encode(array_shift($this->responses), JSON_THROW_ON_ERROR), 200, []];
    }
}
