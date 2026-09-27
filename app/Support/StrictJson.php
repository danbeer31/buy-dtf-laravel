<?php

namespace App\Support;

use App\Exceptions\DuplicateJsonKeyException;
use JsonException;
use stdClass;

class StrictJson
{
    private int $offset = 0;

    private int $length;

    private function __construct(private readonly string $json)
    {
        $this->length = strlen($json);
    }

    /**
     * Decode JSON while rejecting duplicate object names at every depth.
     * Objects intentionally remain stdClass so an empty object is distinct
     * from an empty JSON array during RFC 8785 canonicalization.
     *
     * @throws DuplicateJsonKeyException|JsonException
     */
    public static function decode(string $json): mixed
    {
        $scanner = new self($json);
        $scanner->skipWhitespace();
        $scanner->scanValue(0);
        $scanner->skipWhitespace();

        if ($scanner->offset !== $scanner->length) {
            throw new JsonException('Unexpected trailing JSON content.');
        }

        return json_decode(
            $json,
            false,
            64,
            JSON_THROW_ON_ERROR | JSON_BIGINT_AS_STRING,
        );
    }

    public static function toAssociative(mixed $value): mixed
    {
        if ($value instanceof stdClass) {
            $result = [];
            foreach (get_object_vars($value) as $key => $item) {
                $result[$key] = self::toAssociative($item);
            }

            return $result;
        }

        if (is_array($value)) {
            return array_map([self::class, 'toAssociative'], $value);
        }

        return $value;
    }

    private function scanValue(int $depth): void
    {
        if ($depth > 64) {
            throw new JsonException('Maximum JSON depth exceeded.');
        }

        $this->skipWhitespace();
        $char = $this->json[$this->offset] ?? null;

        match ($char) {
            '{' => $this->scanObject($depth + 1),
            '[' => $this->scanArray($depth + 1),
            '"' => $this->scanStringToken(),
            't' => $this->scanLiteral('true'),
            'f' => $this->scanLiteral('false'),
            'n' => $this->scanLiteral('null'),
            default => $this->scanNumber(),
        };
    }

    private function scanObject(int $depth): void
    {
        $this->offset++;
        $this->skipWhitespace();
        if (($this->json[$this->offset] ?? null) === '}') {
            $this->offset++;

            return;
        }

        $seen = [];
        while (true) {
            $this->skipWhitespace();
            if (($this->json[$this->offset] ?? null) !== '"') {
                throw new JsonException('Expected a JSON object name.');
            }

            $token = $this->scanStringToken();
            $key = json_decode($token, false, 2, JSON_THROW_ON_ERROR);
            if (! is_string($key)) {
                throw new JsonException('Invalid JSON object name.');
            }
            if (array_key_exists($key, $seen)) {
                throw new DuplicateJsonKeyException('Duplicate JSON object name.');
            }
            $seen[$key] = true;

            $this->skipWhitespace();
            if (($this->json[$this->offset] ?? null) !== ':') {
                throw new JsonException('Expected a colon after a JSON object name.');
            }
            $this->offset++;
            $this->scanValue($depth);
            $this->skipWhitespace();

            $separator = $this->json[$this->offset] ?? null;
            if ($separator === '}') {
                $this->offset++;

                return;
            }
            if ($separator !== ',') {
                throw new JsonException('Expected a comma or object terminator.');
            }
            $this->offset++;
        }
    }

    private function scanArray(int $depth): void
    {
        $this->offset++;
        $this->skipWhitespace();
        if (($this->json[$this->offset] ?? null) === ']') {
            $this->offset++;

            return;
        }

        while (true) {
            $this->scanValue($depth);
            $this->skipWhitespace();
            $separator = $this->json[$this->offset] ?? null;
            if ($separator === ']') {
                $this->offset++;

                return;
            }
            if ($separator !== ',') {
                throw new JsonException('Expected a comma or array terminator.');
            }
            $this->offset++;
        }
    }

    private function scanStringToken(): string
    {
        $start = $this->offset;
        $this->offset++;

        while ($this->offset < $this->length) {
            $byte = ord($this->json[$this->offset]);
            if ($byte < 0x20) {
                throw new JsonException('Unescaped control character in JSON string.');
            }

            $char = $this->json[$this->offset++];
            if ($char === '"') {
                return substr($this->json, $start, $this->offset - $start);
            }
            if ($char !== '\\') {
                continue;
            }

            $escape = $this->json[$this->offset++] ?? null;
            if ($escape === null || ! str_contains('"\\/bfnrtu', $escape)) {
                throw new JsonException('Invalid JSON string escape.');
            }
            if ($escape === 'u') {
                $hex = substr($this->json, $this->offset, 4);
                if (strlen($hex) !== 4 || ! ctype_xdigit($hex)) {
                    throw new JsonException('Invalid JSON Unicode escape.');
                }
                $this->offset += 4;
            }
        }

        throw new JsonException('Unterminated JSON string.');
    }

    private function scanLiteral(string $literal): void
    {
        if (substr($this->json, $this->offset, strlen($literal)) !== $literal) {
            throw new JsonException('Invalid JSON literal.');
        }
        $this->offset += strlen($literal);
    }

    private function scanNumber(): void
    {
        $remaining = substr($this->json, $this->offset);
        if (! preg_match('/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/', $remaining, $match)) {
            throw new JsonException('Invalid JSON value.');
        }

        $this->offset += strlen($match[0]);
    }

    private function skipWhitespace(): void
    {
        while ($this->offset < $this->length && str_contains(" \t\r\n", $this->json[$this->offset])) {
            $this->offset++;
        }
    }
}
