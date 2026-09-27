<?php

namespace Tests\Unit\IncomingOrders;

use App\Exceptions\DuplicateJsonKeyException;
use App\Support\JsonCanonicalizer;
use App\Support\StrictJson;
use PHPUnit\Framework\TestCase;

class JsonCanonicalizerTest extends TestCase
{
    public function test_it_matches_the_rfc_8785_serialization_sample(): void
    {
        $decoded = StrictJson::decode(<<<'JSON'
{"numbers":[333333333.33333329,1E30,4.50,2e-3,0.000000000000000000000000001],"string":"€$\u000f\nA'B\"\\\\\"/","literals":[null,true,false]}
JSON);

        $canonical = (new JsonCanonicalizer)->canonicalize($decoded);

        $this->assertSame(
            '{"literals":[null,true,false],"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],"string":"€$\u000f\nA\'B\"\\\\\\\\\"/"}',
            $canonical,
        );
    }

    public function test_object_names_are_sorted_as_utf16_code_units(): void
    {
        $value = (object) [
            "\u{FB33}" => 1,
            "\u{1F600}" => 2,
            '1' => 3,
            "\u{20AC}" => 4,
            "\u{00F6}" => 5,
            "\u{0080}" => 6,
            "\r" => 7,
        ];

        $this->assertSame(
            "{\"\\r\":7,\"1\":3,\"\u{0080}\":6,\"\u{00F6}\":5,\"\u{20AC}\":4,\"\u{1F600}\":2,\"\u{FB33}\":1}",
            (new JsonCanonicalizer)->canonicalize($value),
        );
    }

    public function test_negative_zero_and_ecmascript_number_thresholds_are_canonical(): void
    {
        $this->assertSame(
            '[0,0.000001,1e-7,100000000000000000000,1e+21]',
            (new JsonCanonicalizer)->canonicalize([-0.0, 1e-6, 1e-7, 1e20, 1e21]),
        );
    }

    public function test_duplicate_names_are_rejected_at_any_depth(): void
    {
        $this->expectException(DuplicateJsonKeyException::class);

        StrictJson::decode('{"outer":{"same":1,"same":2}}');
    }

    public function test_empty_object_remains_distinct_from_empty_array(): void
    {
        $canonicalizer = new JsonCanonicalizer;

        $this->assertSame('{}', $canonicalizer->canonicalize(StrictJson::decode('{}')));
        $this->assertSame('[]', $canonicalizer->canonicalize(StrictJson::decode('[]')));
    }
}
