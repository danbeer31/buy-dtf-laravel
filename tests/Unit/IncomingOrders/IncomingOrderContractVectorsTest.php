<?php

namespace Tests\Unit\IncomingOrders;

use App\Exceptions\DuplicateJsonKeyException;
use App\Exceptions\IncomingOrderValidationException;
use App\Services\IncomingOrders\IncomingOrderV1Validator;
use App\Support\JsonCanonicalizer;
use App\Support\StrictJson;
use Tests\TestCase;

class IncomingOrderContractVectorsTest extends TestCase
{
    private const PINNED_FIXTURE_SHA256 = '5cae7f7af7636f891c39aea7d958aa73caf8f3f289175d156ba02088ffc7fd8b';

    public function test_shared_fixture_hash_and_every_pinned_vector(): void
    {
        $path = base_path('contracts/incoming_order_v1_vectors.json');
        $rawFixture = file_get_contents($path);
        $this->assertIsString($rawFixture);
        $this->assertSame(self::PINNED_FIXTURE_SHA256, hash('sha256', $rawFixture));
        $this->assertStringStartsWith(self::PINNED_FIXTURE_SHA256, trim((string) file_get_contents(
            base_path('contracts/incoming_order_v1_vectors.sha256'),
        )));

        $fixture = json_decode($rawFixture, true, 512, JSON_THROW_ON_ERROR);
        config()->set('incoming_order.allowed_hosts', ['artifacts.example.test']);
        config()->set('incoming_order.job_label_enabled', true);
        $canonicalizer = app(JsonCanonicalizer::class);
        $validator = app(IncomingOrderV1Validator::class);
        $results = [];

        foreach ($fixture['vectors'] as $vector) {
            if ($vector['duplicate_keys']) {
                try {
                    StrictJson::decode($vector['raw_json']);
                    $this->fail('Duplicate vector should fail: '.$vector['name']);
                } catch (DuplicateJsonKeyException) {
                    $this->addToAssertionCount(1);
                }
                $results[$vector['name']] = $vector;

                continue;
            }

            $decoded = StrictJson::decode($vector['raw_json']);
            $signing = $canonicalizer->canonicalize($decoded);
            $this->assertSame($vector['expected_signing_canonical'], $signing, $vector['name']);
            $this->assertSame(
                $vector['expected_hmac_sha256'],
                hash_hmac('sha256', $signing, $fixture['synthetic_secret']),
                $vector['name'],
            );

            try {
                $validated = $validator->validate(StrictJson::toAssociative($decoded));
                $this->assertSame('accepted', $vector['expected_validation'], $vector['name']);
                $this->assertSame(
                    $vector['expected_semantic_canonical'],
                    $canonicalizer->canonicalize($validated['semantic']),
                    $vector['name'],
                );
                $this->assertSame(
                    $vector['expected_semantic_sha256'],
                    $validated['request_fingerprint'],
                    $vector['name'],
                );
            } catch (IncomingOrderValidationException $exception) {
                $this->assertSame($vector['expected_validation'], $exception->reason, $vector['name']);
                $this->assertNull($vector['expected_semantic_canonical'], $vector['name']);
                $this->assertNull($vector['expected_semantic_sha256'], $vector['name']);
            }

            $results[$vector['name']] = $vector;
        }

        $this->assertSame(
            $results['base']['expected_hmac_sha256'],
            $results['reordered_keys']['expected_hmac_sha256'],
        );
        $this->assertNotSame(
            $results['base']['expected_hmac_sha256'],
            $results['refreshed_transport']['expected_hmac_sha256'],
        );
        $this->assertSame(
            $results['base']['expected_semantic_sha256'],
            $results['refreshed_transport']['expected_semantic_sha256'],
        );
        $this->assertSame(
            $results['base']['expected_semantic_sha256'],
            $results['omitted_optional_required']['expected_semantic_sha256'],
        );
        $this->assertNotSame(
            $results['base']['expected_hmac_sha256'],
            $results['omitted_optional_required']['expected_hmac_sha256'],
        );
        $this->assertNotSame(
            $results['base']['expected_semantic_sha256'],
            $results['changed_artwork_hash']['expected_semantic_sha256'],
        );
    }
}
