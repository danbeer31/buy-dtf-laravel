<?php
header('Content-Type: application/json');

function check_binary($name) {
    return [
        'name' => $name,
        'path' => shell_exec("which $name 2>&1"),
        'version' => shell_exec("$name -version 2>&1")
    ];
}

echo json_encode([
    'php_version' => PHP_VERSION,
    'sapi' => PHP_SAPI,
    'imagick_loaded' => extension_loaded('imagick'),
    'user' => posix_getpwuid(posix_geteuid())['name'] ?? 'unknown',
    'hostname' => gethostname(),
    'exec_enabled' => function_exists('exec') && !in_array('exec', explode(',', ini_get('disable_functions'))),
    'binaries' => [
        'convert' => check_binary('convert'),
        'magick' => check_binary('magick'),
        'gs' => check_binary('gs'),
    ],
    'extensions' => get_loaded_extensions(),
]);
