<?php

namespace Tests\Unit;

use App\Services\QboService;
use Illuminate\Support\Facades\Http;
use RuntimeException;
use Tests\TestCase;

class QboServiceAdminReadTest extends TestCase
{
    public function test_customer_balances_use_the_short_admin_timeout(): void
    {
        config(['services.qbo.admin_read_timeout' => 8]);
        $service = $this->serviceWithResponses([
            [
                'QueryResponse' => [
                    'Customer' => [
                        ['Id' => '12', 'Balance' => 44.25],
                        ['Id' => '19', 'Balance' => 0],
                    ],
                ],
            ],
        ]);

        $this->assertSame(['12' => 44.25, '19' => 0.0], $service->getAdminCustomerBalances());
        $this->assertSame(8, $service->calls[0]['timeout']);
    }

    public function test_invoice_history_is_normalized_for_cached_payment_checks(): void
    {
        $service = $this->serviceWithResponses([
            [
                'QueryResponse' => [
                    'Invoice' => [[
                        'Id' => 'invoice-1',
                        'Balance' => 100,
                        'TotalAmt' => 107,
                        'TxnTaxDetail' => ['TotalTax' => 7],
                    ]],
                ],
            ],
        ]);

        $invoices = $service->getAdminRecentInvoices();

        $this->assertSame(107.0, $invoices[0]['PayableBalance']);
        $this->assertStringContainsString('MAXRESULTS 500', $service->calls[0]['data']['query']);
    }

    public function test_http_errors_fail_the_refresh_instead_of_replacing_stale_data(): void
    {
        $service = $this->serviceWithResponses([
            ['error' => true, 'status' => 503],
        ]);

        $this->expectException(RuntimeException::class);
        $this->expectExceptionMessage('HTTP 503');

        $service->getAdminCustomerBalances();
    }

    public function test_qbo_writes_are_blocked_before_token_or_http_work(): void
    {
        config(['services.qbo.pause_writes' => true]);
        Http::fake();

        $caught = null;
        try {
            (new QboService)->request('POST', 'invoice', ['DocNumber' => 'test']);
        } catch (RuntimeException $exception) {
            $caught = $exception;
        }

        $this->assertInstanceOf(RuntimeException::class, $caught);
        $this->assertSame(
            'QuickBooks writes are temporarily paused while QBO is unavailable.',
            $caught->getMessage()
        );
        Http::assertNothingSent();
    }

    private function serviceWithResponses(array $responses): QboService
    {
        return new class($responses) extends QboService
        {
            public array $calls = [];

            public function __construct(private array $responses) {}

            public function request($method, $endpoint, $data = [], ?int $timeoutSeconds = null)
            {
                $this->calls[] = [
                    'method' => $method,
                    'endpoint' => $endpoint,
                    'data' => $data,
                    'timeout' => $timeoutSeconds,
                ];

                return array_shift($this->responses);
            }
        };
    }
}
