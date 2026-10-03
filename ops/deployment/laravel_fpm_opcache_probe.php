<?php

declare(strict_types=1);

const BUYDTF_OPCACHE_PROBE_ARTIFACT = 'buy-dtf-php-fpm-opcache-probe-v1';
const BUYDTF_OPCACHE_BOOLEAN_DIRECTIVES = [
    'opcache.enable',
    'opcache.validate_timestamps',
];
const BUYDTF_OPCACHE_INTEGER_DIRECTIVES = [
    'opcache.revalidate_freq',
    'opcache.file_update_protection',
];

/**
 * @return never
 */
function failProbe(string $reason): void
{
    http_response_code(500);
    header('Content-Type: application/json; charset=UTF-8');
    header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
    echo json_encode(
        [
            'artifact' => BUYDTF_OPCACHE_PROBE_ARTIFACT,
            'status' => 'error',
            'reason' => $reason,
        ],
        JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES
    );
    exit(1);
}

/**
 * @return bool
 */
function normalizeBooleanDirective(string $name, string $raw): bool
{
    $normalized = strtolower(trim($raw));
    if (in_array($normalized, ['1', 'on', 'true', 'yes'], true)) {
        return true;
    }
    if (in_array($normalized, ['', '0', 'off', 'false', 'no'], true)) {
        return false;
    }
    failProbe("invalid_boolean_directive:{$name}");
}

/**
 * @return int
 */
function normalizeIntegerDirective(string $name, string $raw): int
{
    $normalized = trim($raw);
    if ($normalized === '' || !ctype_digit($normalized)) {
        failProbe("invalid_integer_directive:{$name}");
    }
    return (int) $normalized;
}

if (PHP_SAPI !== 'fpm-fcgi') {
    failProbe('unexpected_sapi');
}
if (!extension_loaded('Zend OPcache')) {
    failProbe('opcache_extension_unavailable');
}

$directives = [];
foreach (BUYDTF_OPCACHE_BOOLEAN_DIRECTIVES as $name) {
    $raw = ini_get($name);
    if ($raw === false) {
        failProbe("missing_directive:{$name}");
    }
    $normalized = normalizeBooleanDirective($name, $raw);
    $directives[$name] = ['raw' => $raw, 'normalized' => $normalized];
}
foreach (BUYDTF_OPCACHE_INTEGER_DIRECTIVES as $name) {
    $raw = ini_get($name);
    if ($raw === false) {
        failProbe("missing_directive:{$name}");
    }
    $normalized = normalizeIntegerDirective($name, $raw);
    $directives[$name] = ['raw' => $raw, 'normalized' => $normalized];
}

$opcacheConfiguration = opcache_get_configuration();
if (!is_array($opcacheConfiguration) || !isset($opcacheConfiguration['directives'])
    || !is_array($opcacheConfiguration['directives'])) {
    failProbe('opcache_configuration_unavailable');
}
$configurationDirectives = [];
foreach (BUYDTF_OPCACHE_BOOLEAN_DIRECTIVES as $name) {
    $value = $opcacheConfiguration['directives'][$name] ?? null;
    if (!is_bool($value)) {
        failProbe("invalid_configuration_directive:{$name}");
    }
    $configurationDirectives[$name] = $value;
}
foreach (BUYDTF_OPCACHE_INTEGER_DIRECTIVES as $name) {
    $value = $opcacheConfiguration['directives'][$name] ?? null;
    if (!is_int($value) || $value < 0) {
        failProbe("invalid_configuration_directive:{$name}");
    }
    $configurationDirectives[$name] = $value;
}

$payload = [
    'artifact' => BUYDTF_OPCACHE_PROBE_ARTIFACT,
    'sapi' => PHP_SAPI,
    'php_version' => PHP_VERSION,
    'directives' => $directives,
    'opcache_configuration_directives' => $configurationDirectives,
];

header('Content-Type: application/json; charset=UTF-8');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
echo json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
