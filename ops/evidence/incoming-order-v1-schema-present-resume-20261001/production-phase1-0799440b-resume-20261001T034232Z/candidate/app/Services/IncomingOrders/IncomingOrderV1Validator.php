<?php

namespace App\Services\IncomingOrders;

use App\Exceptions\IncomingOrderValidationException;
use App\Exceptions\JobLabelValidationException;
use App\Support\JsonCanonicalizer;
use DateTimeImmutable;
use Normalizer;

class IncomingOrderV1Validator
{
    private const ENVELOPE_KEYS = [
        'source_order_id',
        'file_name',
        'shop',
        'sent_at',
        'idempotency_key',
        'design',
        'job_label',
        'signature',
    ];

    private const DESIGN_KEYS = ['image_url', 'sha256', 'width', 'height', 'quantity'];

    private const LABEL_KEYS = [
        'version',
        'required',
        'mode',
        'order_number',
        'order_item_id',
        'production_print_snapshot_id',
        'product_name',
        'product_sku',
        'color',
        'size',
        'placement',
        'quantity',
        'shop_domain',
    ];

    public function __construct(private readonly JsonCanonicalizer $canonicalizer) {}

    /**
     * @return array<string, mixed>
     */
    public function validate(array $data): array
    {
        $this->assertOnlyKeys($data, self::ENVELOPE_KEYS, 'unknown_field');

        $sourceOrderId = $this->positiveInteger($data['source_order_id'] ?? null, 'source_order_id');
        $fileName = $this->safeText($data['file_name'] ?? null, 255, 'file_name');
        if (basename(str_replace('\\', '/', $fileName)) !== $fileName) {
            throw $this->invalid('invalid_value');
        }

        $shop = null;
        if (array_key_exists('shop', $data) && $data['shop'] !== null) {
            $shop = $this->safeText($data['shop'], 160, 'shop');
        }

        $sentAt = null;
        if (array_key_exists('sent_at', $data) && $data['sent_at'] !== null) {
            $sentAt = $this->safeText($data['sent_at'], 64, 'sent_at');
            if (! $this->isRfc3339($sentAt)) {
                throw $this->invalid('invalid_value');
            }
        }

        $key = $data['idempotency_key'] ?? null;
        if (! is_string($key)
            || strlen($key) < 1
            || strlen($key) > 128
            || ! preg_match('/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/D', $key)) {
            throw $this->invalid('invalid_idempotency_key');
        }

        $design = $data['design'] ?? null;
        if (! is_array($design)) {
            throw $this->invalid('invalid_type');
        }
        $this->assertOnlyKeys($design, self::DESIGN_KEYS, 'unknown_field');
        foreach (self::DESIGN_KEYS as $required) {
            if (! array_key_exists($required, $design)) {
                throw $this->invalid('missing_field');
            }
        }

        $imageUrl = $design['image_url'];
        if (! is_string($imageUrl) || strlen($imageUrl) < 1 || strlen($imageUrl) > 2048) {
            throw $this->invalid('invalid_image_url');
        }
        $urlParts = parse_url($imageUrl);
        $host = is_array($urlParts) ? strtolower((string) ($urlParts['host'] ?? '')) : '';
        if (($urlParts['scheme'] ?? null) !== 'https'
            || $host === ''
            || isset($urlParts['user'])
            || isset($urlParts['pass'])
            || isset($urlParts['fragment'])) {
            throw $this->invalid('invalid_image_url');
        }
        $allowedHosts = (array) config('incoming_order.allowed_hosts', []);
        if (! in_array($host, $allowedHosts, true)) {
            throw $this->invalid('artwork_host_not_allowed');
        }

        $expectedHash = $design['sha256'];
        if (! is_string($expectedHash) || ! preg_match('/^[a-f0-9]{64}$/D', $expectedHash)) {
            throw $this->invalid('invalid_artwork_sha256');
        }

        $width = $this->decimalInches($design['width']);
        $height = $this->decimalInches($design['height']);
        if ((float) $width > (float) config('incoming_order.sheet_width_in', 21.9)
            && (float) $height > (float) config('incoming_order.sheet_width_in', 21.9)) {
            throw $this->invalid('artwork_width_out_of_range');
        }
        $quantity = $this->positiveInteger($design['quantity'], 'quantity', 10_000);

        $labelResult = $this->validateLabel($data['job_label'] ?? null, $quantity);

        $semantic = [
            'contract' => 'incoming_order_v1',
            'source_order_id' => $sourceOrderId,
            'file_name' => $fileName,
            'shop' => $shop,
            'design' => [
                'sha256' => $expectedHash,
                'width_in' => $width,
                'height_in' => $height,
                'quantity' => $quantity,
            ],
            'job_label' => $labelResult['semantic'],
        ];

        return [
            'source_order_id' => $sourceOrderId,
            'file_name' => $fileName,
            'shop' => $shop,
            'sent_at' => $sentAt,
            'idempotency_key' => $key,
            'design' => [
                'image_url' => $imageUrl,
                'approved_host' => $host,
                'sha256' => $expectedHash,
                'width_in' => $width,
                'height_in' => $height,
                'quantity' => $quantity,
            ],
            'job_label' => $labelResult,
            'semantic' => $semantic,
            'request_fingerprint' => hash('sha256', $this->canonicalizer->canonicalize($semantic)),
        ];
    }

    /**
     * @return array{status: string|null, reason: string|null, mode: string|null, required: bool|null, metadata: array<string, mixed>|null, fingerprint: string|null, semantic: mixed}
     */
    private function validateLabel(mixed $rawLabel, int $designQuantity): array
    {
        if ($rawLabel === null) {
            return [
                'status' => null,
                'reason' => null,
                'mode' => null,
                'required' => null,
                'metadata' => null,
                'fingerprint' => null,
                'semantic' => null,
            ];
        }

        if (! is_array($rawLabel)) {
            throw $this->invalid('invalid_type');
        }

        $requiredValue = $rawLabel['required'] ?? false;
        if (! is_bool($requiredValue)) {
            // Fail closed because optional/required semantics cannot be trusted.
            throw $this->invalid('invalid_type');
        }

        try {
            $metadata = $this->normalizeLabel($rawLabel, $designQuantity, $requiredValue);
            $fingerprint = hash('sha256', $this->canonicalizer->canonicalize($metadata));

            if (! (bool) config('incoming_order.job_label_enabled', false)) {
                if ($requiredValue) {
                    throw $this->invalid('capability_disabled');
                }

                return $this->ignoredLabel(
                    $rawLabel,
                    'capability_disabled',
                    $requiredValue,
                    $metadata,
                );
            }

            return [
                'status' => 'accepted',
                'reason' => null,
                'mode' => 'metadata_only',
                'required' => $requiredValue,
                'metadata' => $metadata,
                'fingerprint' => $fingerprint,
                'semantic' => $metadata,
            ];
        } catch (JobLabelValidationException $exception) {
            if ($requiredValue) {
                throw $this->invalid($exception->reason);
            }

            return $this->ignoredLabel($rawLabel, $exception->reason, false);
        }
    }

    /** @return array<string, mixed> */
    private function normalizeLabel(array $label, int $designQuantity, bool $required): array
    {
        $unknown = array_diff(array_keys($label), self::LABEL_KEYS);
        if ($unknown !== []) {
            throw new JobLabelValidationException('unknown_field');
        }

        foreach (['version', 'mode', 'order_number', 'order_item_id', 'production_print_snapshot_id', 'product_name', 'color', 'size', 'placement', 'quantity', 'shop_domain'] as $field) {
            if (! array_key_exists($field, $label)) {
                throw new JobLabelValidationException('missing_field');
            }
        }

        if ($label['version'] !== 1) {
            throw new JobLabelValidationException('unsupported_version');
        }
        if ($label['mode'] !== 'metadata_only') {
            throw new JobLabelValidationException('unsupported_mode');
        }

        try {
            $orderNumber = $this->safeText($label['order_number'], 64, 'order_number');
            $orderItemId = $this->positiveInteger($label['order_item_id'], 'order_item_id', PHP_INT_MAX);
            $snapshotId = $this->positiveInteger($label['production_print_snapshot_id'], 'production_print_snapshot_id', PHP_INT_MAX);
            $productName = $this->safeText($label['product_name'], 160, 'product_name');
            $productSku = $label['product_sku'] ?? null;
            if ($productSku !== null) {
                $productSku = $this->safeText($productSku, 80, 'product_sku');
            }
            $color = $this->safeText($label['color'], 80, 'color');
            $size = $this->safeText($label['size'], 40, 'size');
            $placement = $this->safeText($label['placement'], 80, 'placement');
            $quantity = $this->positiveInteger($label['quantity'], 'quantity', 10_000);
            $domain = $this->hostname($label['shop_domain']);
        } catch (IncomingOrderValidationException $exception) {
            throw new JobLabelValidationException($exception->reason);
        }

        if ($quantity !== $designQuantity) {
            throw new JobLabelValidationException('quantity_mismatch');
        }

        foreach ([$productName, $color, $size, $placement] as $text) {
            if ($this->containsPii($text, true)) {
                throw new JobLabelValidationException('contains_pii');
            }
        }
        foreach ([$orderNumber, $productSku] as $identifier) {
            if (is_string($identifier) && $this->containsPii($identifier, false)) {
                throw new JobLabelValidationException('contains_pii');
            }
        }

        return [
            'version' => 1,
            'required' => $required,
            'mode' => 'metadata_only',
            'order_number' => $orderNumber,
            'order_item_id' => $orderItemId,
            'production_print_snapshot_id' => $snapshotId,
            'product_name' => $productName,
            'product_sku' => $productSku,
            'color' => $color,
            'size' => $size,
            'placement' => $placement,
            'quantity' => $quantity,
            'shop_domain' => $domain,
        ];
    }

    /** @param array<string, mixed>|null $normalizedSemantic */
    private function ignoredLabel(
        array $raw,
        string $reason,
        bool $required,
        ?array $normalizedSemantic = null,
    ): array {
        $mode = isset($raw['mode']) && $raw['mode'] === 'metadata_only' ? 'metadata_only' : null;
        $semantic = $normalizedSemantic ?? $raw;

        return [
            'status' => 'ignored',
            'reason' => $reason,
            'mode' => $mode,
            'required' => $required,
            'metadata' => null,
            'fingerprint' => hash('sha256', $this->canonicalizer->canonicalize($semantic)),
            'semantic' => $semantic,
        ];
    }

    private function assertOnlyKeys(array $value, array $allowed, string $reason): void
    {
        if (array_diff(array_keys($value), $allowed) !== []) {
            throw $this->invalid($reason);
        }
    }

    private function positiveInteger(mixed $value, string $field, int $max = PHP_INT_MAX): int
    {
        if (! is_int($value) || $value < 1 || $value > $max) {
            throw $this->invalid('invalid_value');
        }

        return $value;
    }

    private function decimalInches(mixed $value): string
    {
        if (is_string($value)) {
            if (! preg_match('/^(?:0|[1-9]\d*)(?:\.\d+)?$/D', $value)) {
                throw $this->invalid('invalid_dimension');
            }
            $numeric = (float) $value;
        } elseif (is_int($value) || is_float($value)) {
            $numeric = (float) $value;
        } else {
            throw $this->invalid('invalid_dimension');
        }

        if (! is_finite($numeric) || $numeric <= 0 || $numeric > 120) {
            throw $this->invalid('invalid_dimension');
        }
        $formatted = number_format($numeric, 4, '.', '');
        if ((float) $formatted <= 0 || (int) round((float) $formatted * 300) < 1) {
            throw $this->invalid('invalid_dimension');
        }

        return $formatted;
    }

    private function safeText(mixed $value, int $maxLength, string $field): string
    {
        if (! is_string($value) || ! mb_check_encoding($value, 'UTF-8')) {
            throw $this->invalid('invalid_type');
        }

        $normalized = class_exists(Normalizer::class)
            ? Normalizer::normalize($value, Normalizer::FORM_C)
            : $value;
        if (! is_string($normalized) || $normalized === '' || mb_strlen($normalized, 'UTF-8') > $maxLength) {
            throw $this->invalid($normalized === '' ? 'invalid_value' : 'too_long');
        }
        if (preg_match('/[\x{0000}-\x{001F}\x{007F}-\x{009F}\x{202A}-\x{202E}\x{2066}-\x{2069}]/u', $normalized)) {
            throw $this->invalid('unsafe_characters');
        }

        return $normalized;
    }

    private function hostname(mixed $value): string
    {
        if (! is_string($value) || $value === '' || strlen($value) > 253 || $value !== strtolower($value)) {
            throw $this->invalid('invalid_value');
        }
        if (! preg_match('/^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))+$/D', $value)) {
            throw $this->invalid('invalid_value');
        }

        return $value;
    }

    private function containsPii(string $value, bool $detectPhoneOrAddress): bool
    {
        if (filter_var($value, FILTER_VALIDATE_EMAIL)) {
            return true;
        }
        if (preg_match('/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i', $value)) {
            return true;
        }
        if ($detectPhoneOrAddress
            && preg_match('/^\s*\+?[\d\s().-]{7,}\s*$/', $value)
            && preg_match_all('/\d/', $value) >= 7) {
            return true;
        }

        return $detectPhoneOrAddress
            && (bool) preg_match('/\b\d{1,6}\s+[\pL0-9 .\'-]+\s(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd|court|ct)\b/ui', $value);
    }

    private function isRfc3339(string $value): bool
    {
        if (! preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/D', $value)) {
            return false;
        }

        try {
            new DateTimeImmutable($value);

            return true;
        } catch (\Throwable) {
            return false;
        }
    }

    private function invalid(string $reason): IncomingOrderValidationException
    {
        return new IncomingOrderValidationException('validation_failed', $reason);
    }
}
