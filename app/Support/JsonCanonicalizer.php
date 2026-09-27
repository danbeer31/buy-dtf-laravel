<?php

namespace App\Support;

use InvalidArgumentException;
use JsonException;
use stdClass;

class JsonCanonicalizer
{
    /**
     * RFC 8785 JSON Canonicalization Scheme serialization.
     */
    public function canonicalize(mixed $value): string
    {
        return $this->encode($value);
    }

    private function encode(mixed $value): string
    {
        if ($value === null) {
            return 'null';
        }
        if ($value === true) {
            return 'true';
        }
        if ($value === false) {
            return 'false';
        }
        if (is_string($value)) {
            return $this->encodeString($value);
        }
        if (is_int($value)) {
            return (string) $value;
        }
        if (is_float($value)) {
            return $this->encodeNumber($value);
        }
        if ($value instanceof stdClass) {
            return $this->encodeObject(get_object_vars($value));
        }
        if (is_array($value)) {
            if (array_is_list($value)) {
                return '['.implode(',', array_map(fn (mixed $item): string => $this->encode($item), $value)).']';
            }

            return $this->encodeObject($value);
        }

        throw new InvalidArgumentException('Unsupported value in canonical JSON.');
    }

    private function encodeObject(array $members): string
    {
        $keys = array_keys($members);
        usort($keys, function (string|int $left, string|int $right): int {
            $left = (string) $left;
            $right = (string) $right;
            $leftUtf16 = mb_convert_encoding($left, 'UTF-16BE', 'UTF-8');
            $rightUtf16 = mb_convert_encoding($right, 'UTF-16BE', 'UTF-8');

            return strcmp($leftUtf16, $rightUtf16);
        });

        $encoded = [];
        foreach ($keys as $key) {
            $encoded[] = $this->encodeString((string) $key).':'.$this->encode($members[$key]);
        }

        return '{'.implode(',', $encoded).'}';
    }

    private function encodeString(string $value): string
    {
        if (! mb_check_encoding($value, 'UTF-8')) {
            throw new InvalidArgumentException('Canonical JSON strings must be valid UTF-8.');
        }

        $flags = JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR;
        if (defined('JSON_UNESCAPED_LINE_TERMINATORS')) {
            $flags |= JSON_UNESCAPED_LINE_TERMINATORS;
        }

        try {
            return json_encode($value, $flags);
        } catch (JsonException $exception) {
            throw new InvalidArgumentException('Unable to encode canonical JSON string.', 0, $exception);
        }
    }

    private function encodeNumber(float $value): string
    {
        if (! is_finite($value)) {
            throw new InvalidArgumentException('Canonical JSON cannot contain NaN or infinity.');
        }
        if ($value == 0.0) {
            return '0';
        }

        $encoded = strtolower(json_encode($value, JSON_THROW_ON_ERROR));
        if (! str_contains($encoded, 'e')) {
            return $encoded;
        }

        if (! preg_match('/^(-?)(\d)(?:\.(\d+))?e([+-]?\d+)$/', $encoded, $parts)) {
            throw new InvalidArgumentException('Unable to canonicalize JSON number.');
        }

        $sign = $parts[1];
        $fraction = rtrim($parts[3] ?? '', '0');
        $digits = $parts[2].$fraction;
        $exponent = (int) $parts[4];

        // ECMAScript JSON.stringify uses fixed notation for exponents -6..20.
        if ($exponent >= -6 && $exponent < 21) {
            $decimalPosition = 1 + $exponent;
            if ($decimalPosition <= 0) {
                return $sign.'0.'.str_repeat('0', -$decimalPosition).$digits;
            }
            if ($decimalPosition >= strlen($digits)) {
                return $sign.$digits.str_repeat('0', $decimalPosition - strlen($digits));
            }

            return $sign.substr($digits, 0, $decimalPosition).'.'.substr($digits, $decimalPosition);
        }

        $mantissa = $parts[2].($fraction !== '' ? '.'.$fraction : '');
        $exponentText = ($exponent >= 0 ? '+' : '').(string) $exponent;

        return $sign.$mantissa.'e'.$exponentText;
    }
}
