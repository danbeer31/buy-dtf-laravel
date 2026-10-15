<?php

namespace Tests\Unit;

use App\Models\PaymentInfo;
use App\Models\DtfOrder;
use App\Models\Setting;
use App\Services\QboService;
use App\Services\Accounting\StripeQboReconciliationService;
use App\Services\StripePaymentCompletionGuard;
use App\Services\StripePaymentCompletionService;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Mockery;
use Stripe\PaymentIntent;
use Tests\TestCase;

class StripePaymentCompletionTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config(['database.fuel_connection' => 'sqlite']);

        Schema::connection('sqlite')->create('paymentinfos', function (Blueprint $table) {
            $table->id();
            $table->unsignedBigInteger('dtforder_id');
            $table->unsignedBigInteger('business_id')->nullable();
            $table->string('processor');
            $table->string('processor_confirm');
            $table->string('stripe_charge_id')->nullable();
            $table->string('qbo_payment_id')->nullable();
            $table->string('qbo_invoice_numbers')->nullable();
            $table->string('qbo_fee_expense_id')->nullable();
            $table->decimal('amount', 10, 2);
            $table->decimal('stripe_fee', 10, 2)->nullable();
            $table->text('notes')->nullable();
            $table->string('status');
            $table->timestamps();
        });
        Schema::connection('sqlite')->create('settings', function (Blueprint $table) {
            $table->id();
            $table->string('key');
            $table->string('value');
            $table->timestamps();
        });
        (require database_path('migrations/2026_10_15_000000_create_stripe_payment_completion_guard.php'))->up();
    }

    public function test_second_claim_is_rejected_while_first_is_still_processing(): void
    {
        $guard = new StripePaymentCompletionGuard();

        $this->assertTrue($guard->claim('pi_test_once', 'qbo_invoices'));
        $this->assertFalse($guard->claim('pi_test_once', 'qbo_invoices'));
        $this->assertSame(1, DB::connection('sqlite')->table('stripe_payment_completions')->count());
    }

    public function test_preexisting_payment_is_claimed_without_reposting(): void
    {
        $payment = PaymentInfo::create([
            'dtforder_id' => 0,
            'processor' => 'Stripe',
            'processor_confirm' => 'pi_historic',
            'amount' => 10,
            'status' => 'complete',
        ]);

        $this->assertFalse((new StripePaymentCompletionGuard())->claim('pi_historic', 'qbo_invoices'));
        $this->assertSame($payment->id, DB::connection('sqlite')->table('stripe_payment_completions')
            ->where('payment_intent_id', 'pi_historic')->value('payment_info_id'));
    }

    public function test_invoice_payment_and_fee_are_posted_once_across_revisits(): void
    {
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldReceive('request')->once()->with('GET', 'invoice/123')->andReturn([
            'Invoice' => ['CustomerRef' => ['value' => 'customer-1']],
        ]);
        $qbo->shouldReceive('getInvoicePayableBalance')->once()->andReturn(25.0);
        $qbo->shouldReceive('recordGenericPayment')->once()->andReturn(['Id' => 'payment-1']);
        $qbo->shouldReceive('recordStripeFee')->once()->andReturnUsing(function ($entry) {
            ($entry->update)(['qbo_expense_id' => 'fee-1']);
            return ['Id' => 'fee-1'];
        });

        $service = new StripePaymentCompletionService($qbo, new StripePaymentCompletionGuard());
        $intent = $this->intent('pi_test_success');

        $this->assertTrue($service->completeQboInvoices($intent));
        $this->assertTrue($service->completeQboInvoices($intent));
        $this->assertSame(1, PaymentInfo::where('processor_confirm', $intent->id)->count());
        $this->assertSame('complete', DB::connection('sqlite')->table('stripe_payment_completions')
            ->where('payment_intent_id', $intent->id)->value('state'));
        $this->assertSame(2, DB::connection('sqlite')->table('stripe_payment_completion_steps')
            ->where('payment_intent_id', $intent->id)->where('state', 'succeeded')->count());
    }

    public function test_uncertain_qbo_result_is_flagged_and_never_replayed(): void
    {
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldReceive('request')->once()->andReturn([
            'Invoice' => ['CustomerRef' => ['value' => 'customer-1']],
        ]);
        $qbo->shouldReceive('getInvoicePayableBalance')->once()->andReturn(25.0);
        $qbo->shouldReceive('recordGenericPayment')->once()->andThrow(new \RuntimeException('Network timeout after request'));
        $qbo->shouldReceive('recordStripeFee')->once()->andReturnUsing(function ($entry) {
            ($entry->update)(['qbo_expense_id' => 'fee-2']);
            return ['Id' => 'fee-2'];
        });

        $service = new StripePaymentCompletionService($qbo, new StripePaymentCompletionGuard());
        $intent = $this->intent('pi_test_uncertain');

        $this->assertFalse($service->completeQboInvoices($intent));
        $this->assertFalse($service->completeQboInvoices($intent));
        $this->assertSame('needs_review', DB::connection('sqlite')->table('stripe_payment_completions')
            ->where('payment_intent_id', $intent->id)->value('state'));
        $this->assertSame('outcome_unknown', DB::connection('sqlite')->table('stripe_payment_completion_steps')
            ->where('payment_intent_id', $intent->id)->where('step_key', 'payment:123')->value('state'));
    }

    public function test_order_completion_does_not_repost_qbo_on_revisit(): void
    {
        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldReceive('recordPayment')->once()->andReturn(['Id' => 'order-payment-1']);
        $qbo->shouldReceive('recordStripeFee')->once()->andReturnUsing(function ($entry) {
            ($entry->update)(['qbo_expense_id' => 'order-fee-1']);
            return ['Id' => 'order-fee-1'];
        });

        $order = Mockery::mock(DtfOrder::class)->makePartial();
        $order->id = 456;
        $order->business_id = 17;
        $order->status = 1;
        $order->qbo_invoice_id = 'invoice-1';
        $order->shouldReceive('finalizeMetrics')->once();
        $order->shouldReceive('update')->once()->with(['status' => 2])->andReturn(true);

        $service = new StripePaymentCompletionService($qbo, new StripePaymentCompletionGuard());
        $intent = $this->intent('pi_order_once');
        $service->completeOrder($intent, $order);
        $service->completeOrder($intent, $order);

        $this->assertSame(1, PaymentInfo::where('processor_confirm', $intent->id)->count());
        $this->assertSame('complete', DB::connection('sqlite')->table('stripe_payment_completions')
            ->where('payment_intent_id', $intent->id)->value('state'));
    }

    public function test_reconciliation_flags_duplicate_rows_even_when_holding_balance_matches(): void
    {
        Setting::create(['key' => 'qbo_stripe_clearing_id', 'value' => 'clearing-1']);
        foreach ([1, 2] as $id) {
            PaymentInfo::create([
                'dtforder_id' => 0,
                'processor' => 'Stripe',
                'processor_confirm' => 'pi_duplicate',
                'amount' => 25,
                'status' => 'complete',
            ]);
        }

        $qbo = Mockery::mock(QboService::class);
        $qbo->shouldReceive('getAccountBalance')->once()->with('clearing-1')->andReturn(0);
        $service = new class($qbo) extends StripeQboReconciliationService {
            protected function buildExpectedComponents(?int $businessId = null, ?\Carbon\Carbon $asOfDate = null): array
            {
                return ['expected_holding_amount_cents' => 0, 'meta' => []];
            }
        };

        $result = $service->run(['persist' => false]);

        $this->assertSame('mismatch', $result['status']);
        $this->assertSame(0, $result['difference_amount_cents']);
        $this->assertSame(1, $result['meta']['duplicate_stripe_payment_rows']);
    }

    private function intent(string $id): PaymentIntent
    {
        return PaymentIntent::constructFrom([
            'id' => $id,
            'object' => 'payment_intent',
            'status' => 'succeeded',
            'amount_received' => 2500,
            'metadata' => [
                'payment_type' => 'qbo_invoice_payment',
                'business_id' => '17',
                'qbo_invoice_ids' => '123',
                'qbo_invoice_amounts' => '123=25.00',
            ],
            'latest_charge' => [
                'id' => 'ch_test',
                'object' => 'charge',
                'balance_transaction' => [
                    'id' => 'txn_test',
                    'object' => 'balance_transaction',
                    'fee' => 100,
                ],
            ],
        ]);
    }
}
