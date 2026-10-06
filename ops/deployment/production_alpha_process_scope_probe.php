<?php
declare(strict_types=1);

// Internal FastCGI control only. No Laravel boot, database, environment read,
// scheduler action, process signal, privilege escalation, or permission change.
header('Content-Type: application/json');
header('Cache-Control: no-store');

function failScope(string $message): never
{
    http_response_code(503);
    echo json_encode(['artifact' => 'buy-dtf-process-scope-v1', 'status' => 'rejected',
        'reason' => $message, 'read_only' => true], JSON_THROW_ON_ERROR);
    exit;
}

function facts(int $pid): array
{
    $prefix = '/proc/'.$pid;
    $status = @file_get_contents($prefix.'/status');
    $command = @file_get_contents($prefix.'/cmdline');
    $stat = @file_get_contents($prefix.'/stat');
    if ($status === false || $command === false || $stat === false) {
        throw new RuntimeException('Process identity unavailable.');
    }
    if (!preg_match('/^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$/m', $status, $match)
        || count(array_unique(array_slice($match, 1))) !== 1) {
        throw new RuntimeException('Process owner is ambiguous.');
    }
    $end = strrpos($stat, ') ');
    $fields = $end === false ? [] : preg_split('/\s+/', trim(substr($stat, $end + 2)));
    if (count($fields) < 20 || !ctype_digit($fields[19]) || !str_starts_with($stat, $pid.' (')) {
        throw new RuntimeException('Process start identity is malformed.');
    }
    return ['pid' => $pid, 'uid' => (int) $match[1],
        'start_ticks' => (int) $fields[19], 'argv_sha256' => hash('sha256', $command)];
}

try {
    if (PHP_SAPI !== 'fpm-fcgi' || ($_SERVER['REMOTE_ADDR'] ?? '') !== '127.0.0.1'
        || ($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET') {
        failScope('Internal FPM identity required.');
    }
    $actor = facts(getmypid());
    $actorStatus = @file_get_contents('/proc/self/status');
    if ($actor['uid'] !== 33 || $actorStatus === false
        || !preg_match('/^Gid:\s+33\s+33\s+33\s+33\s*$/m', $actorStatus)) {
        failScope('Read-only observer is not UID/GID 33.');
    }
    $encoded = $_SERVER['BUYDTF_PROCESS_SCOPE_REQUEST'] ?? '';
    if (!is_string($encoded) || strlen($encoded) > 1024) {
        failScope('Request is unavailable.');
    }
    $raw = base64_decode($encoded, true);
    $request = $raw === false ? null : json_decode($raw, true, 16, JSON_THROW_ON_ERROR);
    if (!is_array($request) || count($request) !== 5
        || !is_int($request['pid'] ?? null) || $request['pid'] <= 1
        || ($request['uid'] ?? null) !== 33
        || !is_int($request['start_ticks'] ?? null) || $request['start_ticks'] <= 0
        || !is_string($request['argv_sha256'] ?? null)
        || !preg_match('/^[0-9a-f]{64}$/D', $request['argv_sha256'])
        || !is_string($request['nonce'] ?? null)
        || !preg_match('/^[0-9a-f]{48}$/D', $request['nonce'])) {
        failScope('Request identity is malformed.');
    }
    $expected = ['pid' => $request['pid'], 'uid' => $request['uid'],
        'start_ticks' => $request['start_ticks'], 'argv_sha256' => $request['argv_sha256']];
    $before = facts($request['pid']);
    if ($before !== $expected) {
        failScope('Process identity changed before observation.');
    }
    $cwd = @readlink('/proc/'.$request['pid'].'/cwd');
    $exe = @readlink('/proc/'.$request['pid'].'/exe');
    if ($cwd === false || $exe === false || $cwd === '' || $exe === ''
        || $cwd[0] !== '/' || $exe[0] !== '/'
        || str_contains($cwd, "\0") || str_contains($exe, "\0")
        || str_ends_with($cwd, ' (deleted)') || str_ends_with($exe, ' (deleted)')) {
        failScope('Process scope unavailable to its own UID.');
    }
    $after = facts($request['pid']);
    if ($after !== $before || @readlink('/proc/'.$request['pid'].'/cwd') !== $cwd
        || @readlink('/proc/'.$request['pid'].'/exe') !== $exe) {
        failScope('Process identity changed during observation.');
    }
    echo json_encode(['artifact' => 'buy-dtf-process-scope-v1', 'status' => 'pass',
        'nonce' => $request['nonce'], 'identity' => $after, 'working_directory' => $cwd,
        'executable' => $exe, 'observer_uid' => 33, 'observer_gid' => 33, 'sapi' => PHP_SAPI,
        'php_version' => PHP_VERSION, 'read_only' => true,
        'environments_read' => false, 'process_or_permission_actions' => false],
        JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
} catch (Throwable $error) {
    // Do not emit command lines, paths, environment values, or exception traces.
    failScope('Process scope evidence unavailable or malformed.');
}
