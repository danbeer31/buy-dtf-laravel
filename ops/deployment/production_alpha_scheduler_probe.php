<?php

/** Read existing scheduler cache records without Cache::get/has or mutex::exists.
 * Those framework helpers can delete expired values or acquire/release locks.
 * This observer never runs a command, writes a cache record, or clears a mutex.
 */

use Illuminate\Cache\DatabaseStore;
use Illuminate\Cache\FileStore;
use Illuminate\Console\Scheduling\CacheEventMutex;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Support\Facades\Cache;

function alphaSchedulerProperty(object $object, string $name): mixed
{
    $property = new ReflectionProperty($object, $name);

    return $property->getValue($object);
}

function alphaSchedulerDecode(string $serialized): mixed
{
    set_error_handler(static function (int $severity, string $message): never {
        throw new RuntimeException('Malformed scheduler cache serialization.');
    });
    try {
        $value = unserialize($serialized, ['allowed_classes' => false]);
        if (serialize($value) !== $serialized) {
            throw new RuntimeException('Noncanonical scheduler cache serialization.');
        }

        return $value;
    } finally {
        restore_error_handler();
    }
}

function alphaSchedulerFileRecord(string $directory, string $key): ?array
{
    $hash = sha1($key);
    $path = $directory.'/'.substr($hash, 0, 2).'/'.substr($hash, 2, 2).'/'.$hash;
    foreach ([$directory, dirname(dirname($path)), dirname($path), $path] as $part) {
        if (is_link($part)) {
            throw new RuntimeException('Scheduler cache contains a symlink.');
        }
    }
    if (! file_exists($path)) {
        return null;
    }
    if (! is_file($path)) {
        throw new RuntimeException('Scheduler cache record is not a regular file.');
    }
    $file = fopen($path, 'rb');
    if ($file === false) {
        throw new RuntimeException('Scheduler cache record is unreadable.');
    }
    try {
        // This shared file-read lock is not the scheduler mutex. Never create it.
        $deadline = hrtime(true) + 100_000_000;
        while (! flock($file, LOCK_SH | LOCK_NB)) {
            if (hrtime(true) >= $deadline) {
                throw new RuntimeException('Scheduler cache record stayed unreadable.');
            }
            usleep(1000);
        }
        $bytes = stream_get_contents($file, 65537);
        if ($bytes === false || strlen($bytes) > 65536 || ! preg_match('/^[0-9]{10}/D', substr($bytes, 0, 10))) {
            throw new RuntimeException('Malformed scheduler cache record.');
        }

        return ['expiration' => (int) substr($bytes, 0, 10), 'value' => alphaSchedulerDecode(substr($bytes, 10))];
    } finally {
        flock($file, LOCK_UN);
        fclose($file);
    }
}

function alphaSchedulerCacheRecord(object $store, string $key, bool $mutex): ?array
{
    if ($store instanceof FileStore) {
        $directory = $mutex ? (alphaSchedulerProperty($store, 'lockDirectory') ?? $store->getDirectory()) : $store->getDirectory();

        return alphaSchedulerFileRecord($directory, ($mutex ? 'file-store-lock:' : '').$key);
    }
    if ($store instanceof DatabaseStore) {
        $connection = $mutex ? (alphaSchedulerProperty($store, 'lockConnection') ?? alphaSchedulerProperty($store, 'connection')) : alphaSchedulerProperty($store, 'connection');
        $table = alphaSchedulerProperty($store, $mutex ? 'lockTable' : 'table');
        $row = $connection->table($table)->where('key', $store->getPrefix().$key)->first();
        if ($row === null) {
            return null;
        }
        if ((! is_int($row->expiration) && ! is_string($row->expiration)) || ! preg_match('/^[0-9]+$/D', (string) $row->expiration)) {
            throw new RuntimeException('Malformed scheduler database expiry.');
        }

        return ['expiration' => (int) $row->expiration, 'value' => $mutex ? $row->owner : alphaSchedulerDecode($row->value)];
    }
    throw new RuntimeException('Unsupported read-only scheduler cache store.');
}

function alphaSchedulerTimestampUtc(string $value): string
{
    // Parse the writer's explicit offset; never reinterpret it in the current
    // timezone, normalize an invalid calendar date, or accept an unknown offset.
    if (! preg_match('/^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]{1,6}))?(Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$/D', $value, $parts)
        || str_starts_with($value, '0000-') || str_ends_with($value, '-00:00')) {
        throw new RuntimeException('Malformed QBO refresh timestamp.');
    }
    $fraction = $parts[2] ?? '';
    $offset = $parts[3] === 'Z' ? '+00:00' : $parts[3];
    $canonical = $parts[1].'.'.str_pad($fraction, 6, '0').$offset;
    $instant = DateTimeImmutable::createFromFormat('!Y-m-d\TH:i:s.uP', $canonical);
    $errors = DateTimeImmutable::getLastErrors();
    if ($instant === false || ($errors !== false && ($errors['warning_count'] || $errors['error_count']))
        || $instant->format('Y-m-d\TH:i:s.uP') !== $canonical) {
        throw new RuntimeException('Malformed QBO refresh timestamp.');
    }

    return $instant->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s')
        .($fraction === '' ? '' : '.'.$instant->format('u')).'Z';
}

function alphaSchedulerCapture(string $applicationRoot): array
{
    $events = app(Schedule::class)->events();
    $inventory = [];
    $mutexes = [];
    $stripeCount = 0;
    foreach ($events as $event) {
        $command = (string) ($event->command ?? '');
        $overlaps = (bool) ($event->withoutOverlapping ?? false);
        $inventory[] = [
            'command_sha256' => hash('sha256', $command),
            'expression' => $event->expression,
            'timezone' => $event->timezone ?? config('app.timezone'),
            'without_overlapping' => $overlaps,
            'expires_at_minutes' => $event->expiresAt,
            'run_in_background' => (bool) $event->runInBackground,
            'mutex_name_sha256' => $overlaps ? hash('sha256', $event->mutexName()) : null,
        ];
        if (str_contains($command, 'stripe:sync-payouts')) {
            $stripeCount++;
        }
        if (! $overlaps) {
            continue;
        }
        if (get_class($event->mutex) !== CacheEventMutex::class) {
            throw new RuntimeException('Unreviewed scheduler mutex implementation.');
        }
        $record = alphaSchedulerCacheRecord(Cache::store($event->mutex->store)->getStore(), $event->mutexName(), true);
        if ($record !== null && (! is_string($record['value']) || $record['value'] === '')) {
            throw new RuntimeException('Malformed scheduler mutex owner.');
        }
        $mutexes[] = [
            'command_sha256' => hash('sha256', $command),
            'mutex_name_sha256' => hash('sha256', $event->mutexName()),
            'exists' => $record !== null,
            'expires_at_unix' => $record['expiration'] ?? null,
            'owner_sha256' => $record === null ? null : hash('sha256', $record['value']),
        ];
    }
    usort($inventory, static fn (array $a, array $b): int => strcmp($a['command_sha256'], $b['command_sha256']));
    usort($mutexes, static fn (array $a, array $b): int => strcmp($a['mutex_name_sha256'], $b['mutex_name_sha256']));
    $store = Cache::store()->getStore();
    $record = alphaSchedulerCacheRecord($store, 'qbo:admin-refresh-status', false);
    if ($record === null || $record['expiration'] <= time() || ! is_array($record['value'])) {
        throw new RuntimeException('QBO refresh status is missing, expired, or malformed.');
    }
    $raw = $record['value'];
    $status = ['exists' => true];
    foreach (['state', 'last_attempt_at', 'last_success_at', 'last_error_at', 'circuit_retry_at', 'linked_businesses', 'updated_businesses', 'invoice_count'] as $key) {
        if (! array_key_exists($key, $raw)) {
            throw new RuntimeException('QBO refresh status lacks a required field.');
        }
        $status[$key] = $raw[$key];
    }
    if (! array_key_exists('last_error', $raw) || ($raw['last_error'] !== null && ! is_string($raw['last_error']))) {
        throw new RuntimeException('QBO refresh error status is malformed.');
    }
    $status['last_error_present'] = $raw['last_error'] !== null;
    if (! in_array($status['state'], ['ok', 'error', 'deferred', 'never'], true)) {
        throw new RuntimeException('Malformed QBO refresh state.');
    }
    foreach (['last_attempt_at', 'last_success_at', 'last_error_at', 'circuit_retry_at'] as $key) {
        if ($status[$key] !== null) {
            if (! is_string($status[$key])) {
                throw new RuntimeException('Malformed QBO refresh timestamp.');
            }
            $status[$key] = alphaSchedulerTimestampUtc($status[$key]);
        }
    }
    foreach (['linked_businesses', 'updated_businesses', 'invoice_count'] as $key) {
        if (! is_int($status[$key]) || $status[$key] < 0) {
            throw new RuntimeException('Malformed QBO refresh count.');
        }
    }
    $source = [];
    foreach (['routes/console.php', 'app/Console/Commands/RefreshQboAdminSnapshots.php', 'app/Services/QboAdminSnapshotRefresher.php', 'app/Services/QboAdminSnapshotStore.php'] as $path) {
        $source[$path] = hash_file('sha256', $applicationRoot.'/'.$path);
    }

    return [
        'observer_version' => 2, 'read_only' => true,
        'application_timezone' => config('app.timezone'), 'php_default_timezone' => date_default_timezone_get(),
        'cache_driver' => $store instanceof FileStore ? 'file' : 'database',
        'source_sha256' => $source, 'events' => $inventory,
        'event_count' => count($events), 'stripe_payout_sync_event_count' => $stripeCount,
        'overlap_mutexes' => $mutexes,
        'active_overlap_mutex_count' => count(array_filter($mutexes, static fn (array $row): bool => $row['exists'])),
        'refresh_status' => $status,
    ];
}

function alphaSchedulerSnapshot(string $applicationRoot): array
{
    // A mutex can change while its status is read. Require two identical,
    // read-only captures rather than mistaking that race for an orphan task.
    for ($attempt = 0; $attempt < 3; $attempt++) {
        $before = alphaSchedulerCapture($applicationRoot);
        $after = alphaSchedulerCapture($applicationRoot);
        if ($before === $after) {
            return $after;
        }
        usleep(1000);
    }
    throw new RuntimeException('Scheduler lock/status capture did not stabilize.');
}
