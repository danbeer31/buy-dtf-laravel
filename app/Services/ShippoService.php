<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use App\Models\Setting;

class ShippoService
{
    private string $baseUrl = 'https://api.goshippo.com';
    private string $apiToken;
    private array $fromAddress;
    private array $defaultParcel;

    public function __construct()
    {
        $this->apiToken = config('services.shippo.token');
        $this->fromAddress = config('services.shippo.from_address', []);
        $this->defaultParcel = config('services.shippo.default_parcel', [
            'length' => '12',
            'width' => '10',
            'height' => '4',
            'distance_unit' => 'in',
        ]);
    }

    public function buildAddress(array $a): array
    {
        return [
            'name'           => (string)($a['name'] ?? ''),
            'company'        => (string)($a['company'] ?? ''),
            'street1'        => (string)($a['street1'] ?? ($a['address1'] ?? '')),
            'street2'        => (string)($a['street2'] ?? ($a['address2'] ?? '')),
            'city'           => (string)($a['city'] ?? ''),
            'state'          => (string)($a['state'] ?? ''),
            'zip'            => (string)($a['zip'] ?? ''),
            'country'        => (string)($a['country'] ?? 'US'),
            'phone'          => (string)($a['phone'] ?? ''),
            'email'          => (string)($a['email'] ?? ''),
            'is_residential' => (bool)($a['is_residential'] ?? true),
        ];
    }

    public function buildParcel(array $p): array
    {
        return [
            'length'        => (string)($p['length'] ?? $this->defaultParcel['length']),
            'width'         => (string)($p['width'] ?? $this->defaultParcel['width']),
            'height'        => (string)($p['height'] ?? $this->defaultParcel['height']),
            'distance_unit' => (string)($p['distance_unit'] ?? ($this->defaultParcel['distance_unit'] ?? 'in')),
            'weight'        => (string)($p['weight'] ?? '16'),
            'mass_unit'     => (string)($p['mass_unit'] ?? 'oz'),
        ];
    }

    public function createShipment(array $addressTo, array $parcels, array $opts = []): array
    {
        $parcels = array_map(function($p) {
            $parcel = $this->buildParcel($p);
            // Shippo API limitation: weight must not have more than 10 digits in total
            if (isset($parcel['weight'])) {
                $parcel['weight'] = (string)round((float)$parcel['weight'], 4);
            }
            return $parcel;
        }, $parcels);

        $payload = [
            'address_from' => $this->buildAddress($this->fromAddress),
            'address_to'   => $this->buildAddress($addressTo),
            'parcels'      => $parcels,
            'async'        => false,
        ];

        if (!empty($opts['carrier_accounts'])) {
            $payload['carrier_accounts'] = $opts['carrier_accounts'];
        }

        return $this->request('POST', '/shipments/', $payload);
    }

    public function createTransaction(string $rateId, array $opts = []): array
    {
        $labelType = (string)($opts['label_file_type'] ?? 'PDF_4x6');

        $payload = [
            'rate'            => $rateId,
            'label_file_type' => $labelType,
            'async'           => false,
        ];

        return $this->request('POST', '/transactions/', $payload);
    }

    public function validateAddress(array $address): array
    {
        $payload = $this->buildAddress($address);
        $payload['validate'] = true;
        return $this->request('POST', '/addresses/', $payload);
    }

    private function request(string $method, string $path, array $payload = null): array
    {
        $url = rtrim($this->baseUrl, '/') . $path;

        $response = Http::withHeaders([
            'Authorization' => 'ShippoToken ' . $this->apiToken,
            'Content-Type' => 'application/json',
        ])->timeout(30);

        if ($method === 'POST') {
            $response = $response->post($url, $payload ?? []);
        } else {
            $response = $response->get($url, $payload ?? []);
        }

        if ($response->failed()) {
            Log::error('Shippo request failed', [
                'method' => $method,
                'path' => $path,
                'status' => $response->status(),
            ]);

            throw new \RuntimeException(
                sprintf('Shippo HTTP %d request failed for %s.', $response->status(), $path)
            );
        }

        return $response->json();
    }

    public function quoteUpsRates(array $toAddr, float $weightOz, array $parcelIn = []): array
    {
        $parcel = array_merge($this->defaultParcel, $parcelIn, ['weight' => $weightOz, 'mass_unit' => 'oz']);

        Log::debug('Requesting Shippo rates', [
            'weight_oz' => $weightOz,
        ]);
        try {
            $shipment = $this->createShipment($toAddr, [$parcel]);
            Log::debug('Shippo shipment rates received', [
                'rate_count' => isset($shipment['rates']) && is_countable($shipment['rates'])
                    ? count($shipment['rates'])
                    : 0,
            ]);
            if (isset($shipment['messages']) && !empty($shipment['messages'])) {
                Log::debug('Shippo shipment returned carrier messages', [
                    'message_count' => is_countable($shipment['messages'])
                        ? count($shipment['messages'])
                        : 1,
                ]);
            }
        } catch (\Exception $e) {
            Log::error('Shippo shipment request raised an exception', [
                'exception_type' => $e::class,
                'exception_code' => $e->getCode(),
            ]);
            throw $e;
        }

        $rates = [];
        foreach (($shipment['rates'] ?? []) as $rate) {
            Log::debug('Evaluating Shippo rate', [
                'provider' => (string) ($rate['provider'] ?? ''),
                'service_name' => (string) ($rate['servicelevel']['name'] ?? $rate['service_name'] ?? ''),
                'service_token' => (string) ($rate['servicelevel']['token'] ?? $rate['service_token'] ?? ''),
                'amount' => (string) ($rate['amount'] ?? ''),
                'currency' => (string) ($rate['currency'] ?? ''),
            ]);
            if (!$this->isAllowedUpsRate($rate)) continue;
            $rates[] = $rate;
        }

        usort($rates, fn($a, $b) => ((float)$a['amount']) <=> ((float)$b['amount']));

        return [
            'shippo_shipment_id' => $shipment['object_id'] ?? ($shipment['shippo_shipment_id'] ?? null),
            'rates' => $rates,
        ];
    }

    private function isAllowedUpsRate(array $rate): bool
    {
        $provider = strtoupper((string)($rate['provider'] ?? ''));
        if ($provider !== 'UPS') {
            Log::debug('Filtered non-UPS Shippo rate', [
                'provider' => $provider,
            ]);
            return false;
        }

        $name  = strtolower((string)($rate['servicelevel']['name'] ?? $rate['service_name'] ?? ''));
        $token = strtolower((string)($rate['servicelevel']['token'] ?? $rate['service_token'] ?? ''));

        if (strpos($name, 'surepost') !== false) {
            Log::debug('Filtered UPS SurePost rate', [
                'service_name' => $name,
            ]);
            return false;
        }

        $allowedTokens = json_decode(Setting::get('ups_allowed_services', '[]'), true);

        if (empty($allowedTokens)) {
            $allowedTokens = [
                'ups_ground',
                'ups_ground_saver',
                'ups_2_day',
                'ups_2nd_day_air',
                'ups_second_day_air',
                'ups_next_day_air',
                'ups_next_day_air_saver',
            ];
        }

        if (in_array($token, $allowedTokens, true)) {
            return true;
        }

        // Only use fallback name matching if no explicit allowed services are set or if it matches ground/express
        if (empty(json_decode(Setting::get('ups_allowed_services', '[]'), true))) {
            if (strpos($name, 'ground') !== false) {
                Log::debug('Allowed UPS rate by service-name fallback', [
                    'service_name' => $name,
                ]);
                return true;
            }
            if (strpos($name, '2nd day') !== false || strpos($name, '2 day') !== false) {
                Log::debug('Allowed UPS rate by service-name fallback', [
                    'service_name' => $name,
                ]);
                return true;
            }
            if (strpos($name, 'next day') !== false) {
                Log::debug('Allowed UPS rate by service-name fallback', [
                    'service_name' => $name,
                ]);
                return true;
            }
        }

        Log::debug('Filtered disallowed UPS rate', [
            'service_name' => $name,
            'service_token' => $token,
        ]);

        return false;
    }
}
