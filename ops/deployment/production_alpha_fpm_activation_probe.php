<?php
declare(strict_types=1);

// Internal FPM witness only: no application boot, data, environment read,
// scheduler action, signal, permission change or OPcache invalidation.
header('Content-Type: application/json');
header('Cache-Control: no-store');

function rejectActivationProbe(): never
{
    http_response_code(503);
    echo '{"artifact":"buy-dtf-fpm-activation-witness-v1","status":"rejected"}';
    exit;
}

try {
    if (PHP_SAPI !== 'fpm-fcgi' || PHP_VERSION !== '8.2.30'
        || ($_SERVER['REMOTE_ADDR'] ?? '') !== '127.0.0.1'
        || ($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
        rejectActivationProbe();
    }
    $nonce = $_SERVER['BUYDTF_FPM_ACTIVATION_NONCE'] ?? '';
    if (!is_string($nonce) || !preg_match('/^[0-9a-f]{48}$/D', $nonce)) {
        rejectActivationProbe();
    }
    $pid = getmypid();
    $status = @file_get_contents('/proc/self/status');
    $command = @file_get_contents('/proc/self/cmdline');
    $stat = @file_get_contents('/proc/self/stat');
    if (!is_string($status) || !is_string($command) || $command === '' || !is_string($stat)
        || !preg_match('/^Uid:\s+33\s+33\s+33\s+33\s*$/m', $status)
        || !preg_match('/^Gid:\s+33\s+33\s+33\s+33\s*$/m', $status)) {
        rejectActivationProbe();
    }
    $end = strrpos($stat, ') ');
    $fields = $end === false ? [] : preg_split('/\s+/', trim(substr($stat, $end + 2)));
    if (count($fields) < 20 || !ctype_digit($fields[19]) || (int)$fields[19] <= 0
        || !str_starts_with($stat, $pid.' (')) {
        rejectActivationProbe();
    }
    $probe = __DIR__.'/scope.php';
    if (is_link($probe) || !is_file($probe)
        || hash_file('sha256', $probe) !== '1dca015bffdaf4433ff00ecb0569faad0928c28a726b827f773d4cae4b4737c6') {
        rejectActivationProbe();
    }
    // Run the byte-identical accepted helper against this same FPM worker.
    // No cross-worker ptrace/dumpability assumption or PID selection is needed.
    $_SERVER['BUYDTF_PROCESS_SCOPE_REQUEST'] = base64_encode(json_encode([
        'pid' => $pid, 'uid' => 33, 'start_ticks' => (int)$fields[19],
        'argv_sha256' => hash('sha256', $command), 'nonce' => $nonce,
    ], JSON_THROW_ON_ERROR));
    require $probe;
} catch (Throwable $error) {
    rejectActivationProbe();
}
