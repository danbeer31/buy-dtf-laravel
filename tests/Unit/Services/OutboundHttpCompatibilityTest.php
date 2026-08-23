<?php

namespace Tests\Unit\Services;

use App\Models\DropboxToken;
use App\Models\QboToken;
use App\Services\DropboxService;
use App\Services\NameNumberService;
use App\Services\QboService;
use App\Services\ShippoService;
use GuzzleHttp\Client as GuzzleClient;
use GuzzleHttp\HandlerStack;
use GuzzleHttp\Promise\Create;
use GuzzleHttp\Psr7\Response as Psr7Response;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Schema;
use Psr\Http\Message\RequestInterface;
use Spatie\Dropbox\Client as SpatieDropboxClient;
use Tests\TestCase;

class OutboundHttpCompatibilityTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        Schema::create('qbo_tokens', function (Blueprint $table): void {
            $table->id();
            $table->text('access_token');
            $table->text('refresh_token');
            $table->string('realm_id');
            $table->unsignedBigInteger('expires_in');
            $table->unsignedBigInteger('x_refresh_token_expires_in');
            $table->timestamp('updated_at')->nullable();
        });

        Schema::create('dropbox_tokens', function (Blueprint $table): void {
            $table->id();
            $table->text('access_token');
            $table->string('token_type')->nullable();
            $table->string('uid')->nullable();
            $table->string('account_id')->nullable();
            $table->text('scope')->nullable();
            $table->unsignedBigInteger('expires_in')->default(0);
            $table->text('refresh_token')->nullable();
            $table->timestamp('updated_at')->nullable();
        });
    }

    public function test_qbo_refresh_and_api_requests_keep_their_expected_guzzle_shape(): void
    {
        config()->set([
            'services.qbo.client_id' => 'qbo-client-step2',
            'services.qbo.client_secret' => 'qbo-secret-step2',
            'services.qbo.environment' => 'Development',
        ]);

        QboToken::create([
            'access_token' => 'expired-access-step2',
            'refresh_token' => 'refresh-step2',
            'realm_id' => 'realm-step2',
            'expires_in' => time() - 60,
            'x_refresh_token_expires_in' => time() + 3600,
        ]);

        Http::fake([
            'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer' => Http::response([
                'access_token' => 'fresh-access-step2',
                'refresh_token' => 'rotated-refresh-step2',
                'expires_in' => 3600,
                'x_refresh_token_expires_in' => 7200,
            ]),
            'https://sandbox-quickbooks.api.intuit.com/v3/company/realm-step2/account/account-step2' => Http::response([
                'Account' => ['CurrentBalance' => 12.34],
            ]),
        ]);

        $balance = (new QboService)->getAccountBalance('account-step2');

        $this->assertSame(12.34, $balance);
        $this->assertDatabaseHas('qbo_tokens', [
            'access_token' => 'fresh-access-step2',
            'refresh_token' => 'rotated-refresh-step2',
        ]);

        Http::assertSentInOrder([
            static fn (Request $request): bool => $request->method() === 'POST'
                && $request->url() === 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
                && $request->hasHeader('Authorization', 'Basic '.base64_encode('qbo-client-step2:qbo-secret-step2'))
                && $request->hasHeader('Accept', 'application/json')
                && $request->hasHeader('Content-Type', 'application/x-www-form-urlencoded')
                && $request->data() === [
                    'grant_type' => 'refresh_token',
                    'refresh_token' => 'refresh-step2',
                ],
            static fn (Request $request): bool => $request->method() === 'GET'
                && $request->url() === 'https://sandbox-quickbooks.api.intuit.com/v3/company/realm-step2/account/account-step2'
                && $request->hasHeader('Authorization', 'Bearer fresh-access-step2')
                && $request->hasHeader('Accept', 'application/json')
                && $request->hasHeader('Content-Type', 'application/json'),
        ]);
        Http::assertSentCount(2);
    }

    public function test_shippo_shipment_request_keeps_authentication_and_json_payload_shape(): void
    {
        config()->set([
            'services.shippo.token' => 'shippo-token-step2',
            'services.shippo.from_address' => [
                'name' => 'Buy DTF',
                'street1' => '100 Sender Way',
                'city' => 'La Porte',
                'state' => 'IN',
                'zip' => '46350',
                'country' => 'US',
            ],
            'services.shippo.default_parcel' => [
                'length' => '12',
                'width' => '10',
                'height' => '4',
                'distance_unit' => 'in',
            ],
        ]);

        Http::fake([
            'https://api.goshippo.com/shipments/' => Http::response(['object_id' => 'shipment-step2']),
        ]);

        $result = (new ShippoService)->createShipment(
            [
                'name' => 'Recipient',
                'address1' => '200 Buyer Street',
                'city' => 'Chicago',
                'state' => 'IL',
                'zip' => '60601',
            ],
            [['weight' => 12.34567, 'mass_unit' => 'oz']],
            ['carrier_accounts' => ['carrier-step2']]
        );

        $this->assertSame('shipment-step2', $result['object_id']);
        Http::assertSent(static function (Request $request): bool {
            $data = $request->data();

            return $request->method() === 'POST'
                && $request->url() === 'https://api.goshippo.com/shipments/'
                && $request->hasHeader('Authorization', 'ShippoToken shippo-token-step2')
                && $request->hasHeader('Content-Type', 'application/json')
                && $data['address_from']['street1'] === '100 Sender Way'
                && $data['address_to']['street1'] === '200 Buyer Street'
                && $data['address_to']['country'] === 'US'
                && $data['parcels'][0]['weight'] === '12.3457'
                && $data['parcels'][0]['mass_unit'] === 'oz'
                && $data['carrier_accounts'] === ['carrier-step2']
                && $data['async'] === false;
        });
        Http::assertSentCount(1);
    }

    public function test_dropbox_oauth_exchange_and_refresh_remain_form_encoded_and_persist_rotation(): void
    {
        config()->set([
            'services.dropbox.client_id' => 'dropbox-client-step2',
            'services.dropbox.client_secret' => 'dropbox-secret-step2',
            'services.dropbox.redirect_uri' => 'https://buy-dtf.test/admin/dropbox/callback',
            'services.dropbox.token_url' => 'https://api.dropboxapi.com/oauth2/token',
            'services.dropbox.authorize_url' => 'https://www.dropbox.com/oauth2/authorize',
        ]);

        Http::fakeSequence('https://api.dropboxapi.com/oauth2/token')
            ->push([
                'access_token' => 'dropbox-access-step2',
                'refresh_token' => 'dropbox-refresh-step2',
                'token_type' => 'bearer',
                'expires_in' => 14400,
            ])
            ->push([
                'access_token' => 'dropbox-access-rotated-step2',
                'refresh_token' => 'dropbox-refresh-rotated-step2',
                'token_type' => 'bearer',
                'expires_in' => 14400,
            ]);

        $service = new DropboxService;
        $service->exchangeCodeForToken('oauth-code-step2');
        $service->refreshTokens(DropboxToken::firstOrFail());

        $this->assertDatabaseHas('dropbox_tokens', [
            'access_token' => 'dropbox-access-rotated-step2',
            'refresh_token' => 'dropbox-refresh-rotated-step2',
        ]);

        Http::assertSentInOrder([
            static fn (Request $request): bool => $request->method() === 'POST'
                && $request->url() === 'https://api.dropboxapi.com/oauth2/token'
                && $request->hasHeader('Content-Type', 'application/x-www-form-urlencoded')
                && $request->data() === [
                    'code' => 'oauth-code-step2',
                    'grant_type' => 'authorization_code',
                    'client_id' => 'dropbox-client-step2',
                    'client_secret' => 'dropbox-secret-step2',
                    'redirect_uri' => 'https://buy-dtf.test/admin/dropbox/callback',
                ],
            static fn (Request $request): bool => $request->method() === 'POST'
                && $request->url() === 'https://api.dropboxapi.com/oauth2/token'
                && $request->hasHeader('Authorization', 'Basic '.base64_encode('dropbox-client-step2:dropbox-secret-step2'))
                && $request->hasHeader('Content-Type', 'application/x-www-form-urlencoded')
                && $request->data() === [
                    'grant_type' => 'refresh_token',
                    'refresh_token' => 'dropbox-refresh-step2',
                ],
        ]);
        Http::assertSentCount(2);
    }

    public function test_dropbox_service_upload_stream_keeps_the_actual_spatie_guzzle_contract_without_network(): void
    {
        $capturedRequest = null;
        $capturedBody = null;
        $handler = static function (RequestInterface $request, array $options) use (&$capturedRequest, &$capturedBody) {
            $capturedRequest = $request;
            $body = $request->getBody();
            $position = $body->isSeekable() ? $body->tell() : null;
            $capturedBody = (string) $body;

            if ($position !== null) {
                $body->seek($position);
            }

            return Create::promiseFor(new Psr7Response(
                200,
                ['Content-Type' => 'application/json'],
                json_encode([
                    'name' => 'artwork.png',
                    'path_display' => '/Production/Order 4242/artwork.png',
                ], JSON_THROW_ON_ERROR),
            ));
        };

        $spatieClient = new SpatieDropboxClient(
            'dropbox-access-step2',
            new GuzzleClient(['handler' => HandlerStack::create($handler)]),
        );
        $service = new class($spatieClient) extends DropboxService
        {
            public function __construct(private readonly SpatieDropboxClient $spatieClient)
            {
                parent::__construct();
            }

            public function getClient($token = null)
            {
                return $this->spatieClient;
            }

            public function uploadWithInjectedClient(string $localPath, string $dropboxPath): string
            {
                return $this->performUpload($localPath, $dropboxPath, 'dropbox-access-step2');
            }
        };

        $fileContents = "step2-dropbox-binary\x00payload";
        $tempFile = tempnam(sys_get_temp_dir(), 'buy-dtf-dropbox-');
        if ($tempFile === false) {
            $this->fail('Unable to create the temporary Dropbox upload fixture.');
        }

        file_put_contents($tempFile, $fileContents);

        try {
            $result = $service->uploadWithInjectedClient(
                $tempFile,
                'Production/Order 4242/artwork.png',
            );
        } finally {
            if (is_file($tempFile)) {
                unlink($tempFile);
            }
        }

        $this->assertSame('Production/Order 4242/artwork.png', $result);
        $this->assertFileDoesNotExist($tempFile);
        $this->assertInstanceOf(RequestInterface::class, $capturedRequest);
        $this->assertSame('POST', $capturedRequest->getMethod());
        $this->assertSame('https://content.dropboxapi.com/2/files/upload', (string) $capturedRequest->getUri());
        $this->assertSame('Bearer dropbox-access-step2', $capturedRequest->getHeaderLine('Authorization'));
        $this->assertSame('application/octet-stream', $capturedRequest->getHeaderLine('Content-Type'));
        $this->assertSame([
            'path' => '/Production/Order 4242/artwork.png',
            'mode' => 'overwrite',
            'autorename' => false,
        ], json_decode(
            $capturedRequest->getHeaderLine('Dropbox-API-Arg'),
            true,
            512,
            JSON_THROW_ON_ERROR,
        ));
        $this->assertSame($fileContents, $capturedBody);
    }

    public function test_name_number_renderer_keeps_token_header_and_normalized_json_payload(): void
    {
        config()->set([
            'services.namenumber.url' => 'https://renderer.example.test/api',
            'services.namenumber.token' => 'renderer-token-step2',
        ]);

        Http::fake([
            'https://renderer.example.test/api/render-name-number' => Http::response([
                'success' => true,
                'job_id' => 'render-step2',
            ]),
        ]);

        $result = (new NameNumberService)->renderTemplateRemote(
            'varsity',
            "Jane O'Neil!",
            '#42',
            ['fontFamily' => 'Impact', 'fill' => '#112233'],
            ['fontFamily' => 'Impact'],
            ['dpi' => 600, 'format' => 'json', 'preserveCase' => true]
        );

        $this->assertSame(['success' => true, 'job_id' => 'render-step2'], $result);
        Http::assertSent(static function (Request $request): bool {
            $data = $request->data();

            return $request->method() === 'POST'
                && $request->url() === 'https://renderer.example.test/api/render-name-number'
                && $request->hasHeader('X-Api-Token', 'renderer-token-step2')
                && $request->hasHeader('Content-Type', 'application/json')
                && $data['template'] === 'varsity'
                && $data['name'] === 'Jane ONeil'
                && $data['number'] === '42'
                && $data['dpi'] === 600
                && $data['preserveCase'] === true
                && $data['format'] === 'json'
                && $data['nameStyle']['fill'] === '#112233';
        });
        Http::assertSentCount(1);
    }

    public function test_name_number_font_upload_keeps_multipart_contract_and_cleans_up_temp_file(): void
    {
        config()->set([
            'services.namenumber.url' => 'https://renderer.example.test/api',
            'services.namenumber.token' => 'renderer-token-step2',
        ]);

        Http::fake([
            'https://renderer.example.test/api/fonts/upload' => Http::response([
                'success' => true,
                'font' => 'compatibility-font',
            ]),
        ]);

        $fontContents = "step2-font-binary\x00payload";
        $tempFile = tempnam(sys_get_temp_dir(), 'buy-dtf-font-');
        if ($tempFile === false) {
            $this->fail('Unable to create the temporary font fixture.');
        }

        file_put_contents($tempFile, $fontContents);

        try {
            $result = (new NameNumberService)->uploadFont($tempFile);

            $this->assertSame([
                'success' => true,
                'font' => 'compatibility-font',
            ], $result);
            Http::assertSent(static function (Request $request) use ($fontContents, $tempFile): bool {
                $contentType = $request->header('Content-Type')[0] ?? '';

                return $request->method() === 'POST'
                    && $request->url() === 'https://renderer.example.test/api/fonts/upload'
                    && $request->hasHeader('X-Api-Token', 'renderer-token-step2')
                    && str_starts_with($contentType, 'multipart/form-data; boundary=')
                    && $request->hasFile('font', $fontContents, basename($tempFile));
            });
            Http::assertSentCount(1);
        } finally {
            if (is_file($tempFile)) {
                unlink($tempFile);
            }
        }

        $this->assertFileDoesNotExist($tempFile);
    }
}
