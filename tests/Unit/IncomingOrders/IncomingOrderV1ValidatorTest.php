<?php

namespace Tests\Unit\IncomingOrders;

use App\Exceptions\IncomingOrderValidationException;
use App\Services\IncomingOrders\IncomingOrderV1Validator;
use Tests\TestCase;

class IncomingOrderV1ValidatorTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config()->set('incoming_order.allowed_hosts', ['artifacts.example.test']);
        config()->set('incoming_order.job_label_enabled', true);
    }

    public function test_text_is_nfc_normalized_and_numeric_sku_is_not_misclassified_as_customer_pii(): void
    {
        $payload = $this->payload();
        $payload['job_label']['product_name'] = "Cafe\u{0301} Team Jacket";
        $payload['job_label']['product_sku'] = '123456789';

        $validated = app(IncomingOrderV1Validator::class)->validate($payload);

        $this->assertSame('Café Team Jacket', $validated['job_label']['metadata']['product_name']);
        $this->assertSame('123456789', $validated['job_label']['metadata']['product_sku']);
        $this->assertSame('10.7500', $validated['design']['width_in']);
        $this->assertSame('11.1220', $validated['design']['height_in']);
    }

    public function test_template_shell_and_html_characters_remain_plain_frozen_text(): void
    {
        $payload = $this->payload();
        $payload['job_label']['product_name'] = '<script>alert(1)</script> ${HOME} $(whoami) {{ seven }}';

        $validated = app(IncomingOrderV1Validator::class)->validate($payload);

        $this->assertSame(
            '<script>alert(1)</script> ${HOME} $(whoami) {{ seven }}',
            $validated['job_label']['metadata']['product_name'],
        );
    }

    public function test_optional_unsafe_control_text_is_ignored_without_retaining_metadata(): void
    {
        $payload = $this->payload();
        $payload['job_label']['placement'] = "Full\nBack";

        $validated = app(IncomingOrderV1Validator::class)->validate($payload);

        $this->assertSame('ignored', $validated['job_label']['status']);
        $this->assertSame('unsafe_characters', $validated['job_label']['reason']);
        $this->assertNull($validated['job_label']['metadata']);
    }

    public function test_required_bidi_control_text_is_rejected(): void
    {
        $payload = $this->payload();
        $payload['job_label']['required'] = true;
        $payload['job_label']['product_name'] = "Safe\u{202E}unsafe";

        try {
            app(IncomingOrderV1Validator::class)->validate($payload);
            $this->fail('Required unsafe metadata must fail.');
        } catch (IncomingOrderValidationException $exception) {
            $this->assertSame('unsafe_characters', $exception->reason);
        }
    }

    public function test_label_length_limit_is_enforced_as_an_enumerated_optional_failure(): void
    {
        $payload = $this->payload();
        $payload['job_label']['size'] = str_repeat('x', 41);

        $validated = app(IncomingOrderV1Validator::class)->validate($payload);

        $this->assertSame('ignored', $validated['job_label']['status']);
        $this->assertSame('too_long', $validated['job_label']['reason']);
    }

    public function test_filename_paths_and_unknown_design_fields_are_core_failures(): void
    {
        $payload = $this->payload();
        $payload['file_name'] = '../unsafe.png';

        $this->expectException(IncomingOrderValidationException::class);
        app(IncomingOrderV1Validator::class)->validate($payload);
    }

    /** @return array<string, mixed> */
    private function payload(): array
    {
        return [
            'source_order_id' => 853,
            'file_name' => 'production-art.png',
            'shop' => 'Urey Local School Gear',
            'sent_at' => '2026-09-27T12:00:00Z',
            'idempotency_key' => 'shopnltees:dispatch:validator-test',
            'design' => [
                'image_url' => 'https://artifacts.example.test/art.png?token=test',
                'sha256' => str_repeat('a', 64),
                'width' => '10.75004',
                'height' => '11.1220',
                'quantity' => 1,
            ],
            'job_label' => [
                'version' => 1,
                'required' => false,
                'mode' => 'metadata_only',
                'order_number' => '1725',
                'order_item_id' => 1671,
                'production_print_snapshot_id' => 31,
                'product_name' => 'Urey Cheer Jacket',
                'product_sku' => 'PC78H',
                'color' => 'Black',
                'size' => 'S',
                'placement' => 'Full Back',
                'quantity' => 1,
                'shop_domain' => 'urey.localschoolgear.com',
            ],
            'signature' => str_repeat('0', 64),
        ];
    }
}
