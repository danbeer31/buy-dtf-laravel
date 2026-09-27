<?php

$csv = static function (?string $value): array {
    if (! is_string($value) || trim($value) === '') {
        return [];
    }

    return array_values(array_unique(array_filter(array_map(
        static fn (string $item): string => strtolower(trim($item)),
        explode(',', $value),
    ))));
};

return [
    'receiver_enabled' => (bool) env('INCOMING_ORDER_V1_ENABLED', false),
    'job_label_enabled' => (bool) env('INCOMING_ORDER_JOB_LABEL_ENABLED', false),
    'integration_client' => (string) env('INCOMING_ORDER_INTEGRATION_CLIENT', 'shopnltees'),
    'business_id' => (int) env('INCOMING_ORDER_BUSINESS_ID', 1),
    'shared_secret' => (string) env('BUY_DTF_SECRET', ''),

    'allowed_hosts' => $csv(env('INCOMING_ORDER_ALLOWED_HOSTS')),
    'fetch' => [
        'connect_timeout_seconds' => (int) env('INCOMING_ORDER_FETCH_CONNECT_TIMEOUT', 10),
        'timeout_seconds' => (int) env('INCOMING_ORDER_FETCH_TIMEOUT', 30),
        'max_bytes' => (int) env('INCOMING_ORDER_FETCH_MAX_BYTES', 50 * 1024 * 1024),
        'max_redirects' => 3,
        'max_width_px' => 30_000,
        'max_height_px' => 30_000,
        'max_area_px' => 100_000_000,
        'formats' => ['png', 'jpeg', 'webp'],
    ],

    'request_max_bytes' => (int) env('INCOMING_ORDER_REQUEST_MAX_BYTES', 128 * 1024),
    'request_budget_seconds' => (int) env('INCOMING_ORDER_REQUEST_BUDGET_SECONDS', 60),
    'lease_seconds' => (int) env('INCOMING_ORDER_LEASE_SECONDS', 90),
    'heartbeat_seconds' => (int) env('INCOMING_ORDER_HEARTBEAT_SECONDS', 20),
    'max_attempts' => (int) env('INCOMING_ORDER_MAX_ATTEMPTS', 10),
    'dimension_precision' => 4,
    'aspect_ratio_max_relative_error' => 0.001,
    'sheet_width_in' => 21.9,

    'job_card' => [
        'renderer_version' => 'separate-job-card-v1',
        'width_in' => (float) env('INCOMING_ORDER_JOB_CARD_WIDTH_IN', 5.0),
        'height_in' => (float) env('INCOMING_ORDER_JOB_CARD_HEIGHT_IN', 3.0),
        'dpi' => (int) env('INCOMING_ORDER_JOB_CARD_DPI', 300),
        'font' => env('INCOMING_ORDER_JOB_CARD_FONT'),
        'production_lease_seconds' => (int) env('INCOMING_ORDER_PRODUCTION_LEASE_SECONDS', 300),
    ],

    'retention' => [
        // Fail-safe: missing/unknown/unclassified records are permanent.
        'enabled' => (bool) env('INCOMING_ORDER_RETENTION_ENABLED', false),
        'days' => env('INCOMING_ORDER_RETENTION_DAYS') !== null
            ? (int) env('INCOMING_ORDER_RETENTION_DAYS')
            : null,
    ],

    'customer_artwork' => [
        'deletion_enabled' => (bool) env('CUSTOMER_ARTWORK_DELETION_ENABLED', false),
        'physical_purge_enabled' => (bool) env('CUSTOMER_ARTWORK_PHYSICAL_PURGE_ENABLED', false),
    ],
];
