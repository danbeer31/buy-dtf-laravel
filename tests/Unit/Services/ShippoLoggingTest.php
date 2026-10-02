<?php

namespace Tests\Unit\Services;

use App\Services\ShippoService;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Tests\TestCase;

class ShippoLoggingTest extends TestCase
{
    public function test_rate_diagnostics_are_debug_level_and_exclude_addresses_and_carrier_payloads(): void
    {
        config()->set('services.shippo.from_address', [
            'name' => 'Private Sender',
            'street1' => '100 Sender Secret Way',
            'city' => 'La Porte',
            'state' => 'IN',
            'zip' => '46350',
            'country' => 'US',
        ]);

        Http::fake([
            'https://api.goshippo.com/shipments/' => Http::response([
                'object_id' => 'shipment-log-test',
                'messages' => [[
                    'source' => 'UPS',
                    'text' => 'carrier-message-secret for 200 Buyer Street',
                ]],
                'rates' => [[
                    'provider' => 'UPS',
                    'servicelevel' => [
                        'name' => 'Ground',
                        'token' => 'ups_ground',
                        'terms' => 'carrier-extra-secret',
                    ],
                    'amount' => '9.99',
                    'currency' => 'USD',
                    'carrier_account' => 'carrier-account-secret',
                ]],
            ]),
        ]);
        Log::spy();

        $quote = (new ShippoService)->quoteUpsRates([
            'name' => 'Recipient Private',
            'street1' => '200 Buyer Street',
            'city' => 'Chicago',
            'state' => 'IL',
            'zip' => '60601',
        ], 12.5);

        $this->assertCount(1, $quote['rates']);
        Log::shouldHaveReceived('debug', [
            'Requesting Shippo rates',
            ['weight_oz' => 12.5],
        ])->once();
        Log::shouldHaveReceived('debug', [
            'Shippo shipment returned carrier messages',
            ['message_count' => 1],
        ])->once();
        Log::shouldNotHaveReceived('error');

        foreach ([
            'Recipient Private',
            '200 Buyer Street',
            '60601',
            'carrier-message-secret',
            'carrier-extra-secret',
            'carrier-account-secret',
        ] as $privateValue) {
            $this->assertValueWasNotLogged($privateValue);
        }
    }

    public function test_failed_shippo_response_logs_status_without_response_body(): void
    {
        Http::fake([
            'https://api.goshippo.com/shipments/' => Http::response([
                'detail' => 'carrier-response-secret for 200 Buyer Street',
                'address' => ['zip' => '60601'],
            ], 422),
        ]);
        Log::spy();

        try {
            (new ShippoService)->createShipment([
                'name' => 'Recipient Private',
                'street1' => '200 Buyer Street',
                'city' => 'Chicago',
                'state' => 'IL',
                'zip' => '60601',
            ], [['weight' => 12.5, 'mass_unit' => 'oz']]);
            $this->fail('The failed Shippo response should raise an exception.');
        } catch (\RuntimeException $exception) {
            $this->assertSame(
                'Shippo HTTP 422 request failed for /shipments/.',
                $exception->getMessage()
            );
        }

        Log::shouldHaveReceived('error', [
            'Shippo request failed',
            [
                'method' => 'POST',
                'path' => '/shipments/',
                'status' => 422,
            ],
        ])->once();

        foreach ([
            'Recipient Private',
            '200 Buyer Street',
            '60601',
            'carrier-response-secret',
        ] as $privateValue) {
            $this->assertValueWasNotLogged($privateValue);
        }
    }

    private function assertValueWasNotLogged(string $privateValue): void
    {
        foreach (['debug', 'info', 'notice', 'warning', 'error', 'critical', 'alert', 'emergency'] as $level) {
            Log::shouldNotHaveReceived(
                $level,
                static fn (...$arguments): bool => str_contains(
                    json_encode($arguments, JSON_THROW_ON_ERROR),
                    $privateValue
                )
            );
        }
    }
}
