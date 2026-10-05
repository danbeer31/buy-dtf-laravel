<?php

// Disposable-cache integration with real Laravel and QBO status writer. No task runs.
require $argv[1].'/vendor/autoload.php';
require __DIR__.'/production_alpha_scheduler_probe.php';
require_once $argv[3].'/app/Services/QboAdminSnapshotStore.php';

use Illuminate\Foundation\Application;
use Illuminate\Config\Repository;
use Illuminate\Cache\CacheServiceProvider;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Support\Facades\Facade;
use Illuminate\Support\Facades\Date;

$root = $argv[2];
if (! is_dir($root) || count(scandir($root)) !== 2) {
    throw new RuntimeException('A new empty disposable directory is required.');
}
$app = new Application($root);
date_default_timezone_set('America/Chicago'); // This disposable test process only.
$app->instance('files', new \Illuminate\Filesystem\Filesystem());
$app->instance('config', new Repository([
    'app' => ['timezone' => 'America/Chicago'],
    'cache' => ['default' => 'file', 'stores' => ['file' => ['driver' => 'file', 'path' => $root.'/cache', 'lock_path' => $root.'/cache']]],
]));
$app->register(CacheServiceProvider::class);
Facade::setFacadeApplication($app);
$schedule = new Schedule('America/Chicago');
$schedule->command('stripe:sync-payouts')->hourly();
$schedule->command('accounting:reconcile-stripe-holding')->dailyAt('01:30');
$event = $schedule->command('qbo:refresh-admin-cache')->everyTenMinutes()->withoutOverlapping(15)->runInBackground();
$app->instance(Schedule::class, $schedule);
$store = $app['cache']->store()->getStore();

function fixture(string $path, int $expiration, mixed $value): void
{
    if (! is_dir(dirname($path))) {
        mkdir(dirname($path), 0700, true);
    }
    file_put_contents($path, (string) $expiration.serialize($value));
    chmod($path, 0600);
}

function cacheIdentity(string $root): array
{
    $rows = [];
    foreach (new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS)) as $path) {
        if ($path->isFile()) {
            $rows[$path->getPathname()] = [hash_file('sha256', $path->getPathname()), $path->getSize(), $path->getPerms() & 07777];
        }
    }
    ksort($rows);

    return $rows;
}

$now = time();
$statusPath = $store->path('qbo:admin-refresh-status');
fixture($statusPath, 9999999999, [
    'state' => 'ok', 'last_attempt_at' => gmdate('Y-m-d\TH:i:s\Z', $now), 'last_success_at' => gmdate('Y-m-d\TH:i:s\Z', $now),
    'last_error_at' => null, 'last_error' => null, 'circuit_retry_at' => null,
    'linked_businesses' => 4, 'updated_businesses' => 4, 'invoice_count' => 10,
]);
$mutexPath = $store->path('file-store-lock:'.$event->mutexName());
fixture($mutexPath, $now + 900, 'SYNTHETIC-PRIVATE-MUTEX-OWNER');
$before = cacheIdentity($root);
$snapshot = alphaSchedulerSnapshot($argv[3]);
$after = cacheIdentity($root);
if ($before !== $after || $snapshot['active_overlap_mutex_count'] !== 1) {
    throw new RuntimeException('Read-only scheduler observation altered a record or missed the active mutex.');
}
// Even an expired mutex must be observed and rejected by policy, never pruned.
fixture($mutexPath, $now - 1, 'SYNTHETIC-PRIVATE-MUTEX-OWNER');
$beforeExpired = cacheIdentity($root);
$expired = alphaSchedulerSnapshot($argv[3]);
if ($beforeExpired !== cacheIdentity($root) || $expired['overlap_mutexes'][0]['expires_at_unix'] !== $now - 1) {
    throw new RuntimeException('Expired scheduler record was silently pruned.');
}
file_put_contents($mutexPath, 'malformed');
$malformedBefore = cacheIdentity($root);
$rejected = false;
try {
    alphaSchedulerSnapshot($argv[3]);
} catch (RuntimeException $exception) {
    $rejected = true;
}
if (! $rejected || $malformedBefore !== cacheIdentity($root)) {
    throw new RuntimeException('Malformed scheduler record was accepted or modified.');
}
$connection = new \Illuminate\Database\SQLiteConnection(new PDO('sqlite::memory:'));
$connection->statement('CREATE TABLE cache (key TEXT PRIMARY KEY, value TEXT, expiration INTEGER)');
$connection->statement('CREATE TABLE cache_locks (key TEXT PRIMARY KEY, owner TEXT, expiration INTEGER)');
$connection->table('cache')->insert(['key' => 'review-qbo:admin-refresh-status', 'value' => serialize(['state' => 'ok']), 'expiration' => 9999999999]);
$connection->table('cache_locks')->insert(['key' => 'review-mutex', 'owner' => 'SYNTHETIC-PRIVATE-MUTEX-OWNER', 'expiration' => $now - 1]);
$databaseStore = new \Illuminate\Cache\DatabaseStore($connection, 'cache', 'review-', 'cache_locks');
$connection->enableQueryLog();
$dbStatus = alphaSchedulerCacheRecord($databaseStore, 'qbo:admin-refresh-status', false);
$dbMutex = alphaSchedulerCacheRecord($databaseStore, 'mutex', true);
$queries = $connection->getQueryLog();
if ($dbStatus['value'] !== ['state' => 'ok'] || $dbMutex['expiration'] !== $now - 1 || count($queries) !== 2) {
    throw new RuntimeException('Database scheduler observation differs.');
}
foreach ($queries as $query) {
    if (! str_starts_with(strtolower($query['query']), 'select ')) {
        throw new RuntimeException('Database scheduler observer issued a write.');
    }
}

// Exercise the real writer and Laravel's real mutex-before-worker lifecycle in
// an empty local cache. No command, QBO client, database business model or cron.
unlink($mutexPath); // Only the malformed record created above, in the new fixture.
$writer = new \App\Services\QboAdminSnapshotStore();
$lifecycles = [];
foreach ([
    'summer' => '2026-07-10T06:20:00Z',
    'winter' => '2026-12-10T07:20:00Z',
] as $label => $instant) {
    $start = new DateTimeImmutable($instant);
    Date::setTestNow($start->modify('-588 seconds'));
    $writer->markSuccess(4, 4, 10);
    Date::setTestNow($start);
    if ($event->shouldSkipDueToOverlapping()) {
        throw new RuntimeException('Disposable event could not acquire its overlap mutex.');
    }
    $rows = [];
    foreach (['startup' => 1, 'running' => 5, 'success_before_release' => 12, 'released' => 13] as $phase => $seconds) {
        $at = $start->modify('+'.$seconds.' seconds');
        Date::setTestNow($at);
        if ($phase === 'running') {
            $writer->markAttempt();
        } elseif ($phase === 'success_before_release') {
            $writer->markSuccess(4, 4, 10);
        } elseif ($phase === 'released') {
            $event->finish($app, 0); // Framework completion of the disposable event only.
        }
        $raw = $writer->status();
        $beforeRead = cacheIdentity($root);
        $observed = alphaSchedulerSnapshot($argv[3]);
        if ($beforeRead !== cacheIdentity($root)) {
            throw new RuntimeException('Observer altered a real writer/lifecycle cache record.');
        }
        $rows[] = ['phase' => $phase, 'generated_at_utc' => $at->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z'),
            'raw_writer_last_attempt_at' => $raw['last_attempt_at'], 'raw_writer_last_success_at' => $raw['last_success_at'],
            'scheduler' => $observed, 'observer_cache_unchanged' => true];
    }
    $lifecycles[$label] = $rows;
}

$dueCases = [];
Date::setTestNow();
$expressionPasses = new ReflectionMethod(\Illuminate\Console\Scheduling\Event::class, 'expressionPasses');
foreach ([
    '2026-07-10T06:20:01Z', '2026-07-10T06:30:01Z', '2026-07-10T07:00:01Z',
    '2026-12-10T07:20:01Z', '2026-12-10T07:30:01Z', '2026-12-10T08:00:01Z',
    '2026-03-08T07:30:01Z', '2026-03-08T08:30:01Z',
    '2026-11-01T06:30:01Z', '2026-11-01T07:30:01Z', '2026-11-01T08:30:01Z',
] as $instant) {
    // An absolute-instant date factory avoids mock-clock reparsing of the
    // repeated 01:30 wall time. The actual Laravel scheduling method still
    // converts that instant through its configured America/Chicago zone.
    $absolute = new DateTimeImmutable($instant);
    Date::useCallable(static fn ($date) => \Illuminate\Support\Carbon::createFromTimestampUTC($absolute->getTimestamp())->setTimezone('America/Chicago'));
    $due = [];
    foreach ($schedule->events() as $scheduled) {
        if ($expressionPasses->invoke($scheduled)) {
            $due[] = str_replace('php artisan ', '', $scheduled::normalizeCommand($scheduled->command));
        }
    }
    $dueCases[] = ['at_utc' => $instant, 'local_time' => now()->toIso8601String(), 'due_commands' => $due];
}
$writer->markFailure(new RuntimeException('SYNTHETIC-LOCAL-FAILURE'), null);
$failureBefore = cacheIdentity($root);
$writerFailure = alphaSchedulerSnapshot($argv[3]);
if ($failureBefore !== cacheIdentity($root) || ! $writerFailure['refresh_status']['last_error_present']) {
    throw new RuntimeException('Real writer failure was lost or modified.');
}
Date::useDefault();

$timestampCases = [];
foreach (['2026-10-04T19:20:12-05:00', '2026-12-10T01:20:12-06:00', '2026-11-01T01:30:01-05:00', '2026-11-01T01:30:01-06:00', '2026-10-05T09:20:12+09:00', '2026-10-05T00:20:12.123456Z'] as $value) {
    $timestampCases[$value] = alphaSchedulerTimestampUtc($value);
}
$invalidCases = ['2026-02-30T19:20:12-05:00', '2026-10-04T25:20:12-05:00', '2026-10-04T19:20:12-05:99',
    '2026-10-04T19:20:12-24:00', '2026-10-04T19:20:12', '2026-10-04T19:20:12-00:00',
    '2026-10-04T19:20:12.1234567Z', '0000-01-01T00:00:00Z', '2026-10-04T19:20:12-05:00 trailing'];
foreach ($invalidCases as $value) {
    $rejected = false;
    try { alphaSchedulerTimestampUtc($value); } catch (RuntimeException $exception) { $rejected = true; }
    if (! $rejected) { throw new RuntimeException('Invalid timestamp was accepted.'); }
}
$result = [
    'status' => 'pass', 'php_version' => PHP_VERSION, 'laravel_version' => Application::VERSION,
    'events' => $snapshot['events'], 'source_sha256' => $snapshot['source_sha256'],
    'active_mutex_read_only' => true, 'expired_mutex_read_only' => true, 'malformed_mutex_read_only_rejected' => true,
    'database_observer_select_only' => true, 'database_select_count' => count($queries),
    'normalized_commands' => array_map(static fn ($event): string => $event::normalizeCommand($event->command), $schedule->events()),
    'cookie_or_customer_data' => false, 'accounting_task_executed' => false,
    'snapshot_owner_is_only_sha256' => $snapshot['overlap_mutexes'][0]['owner_sha256'] === hash('sha256', 'SYNTHETIC-PRIVATE-MUTEX-OWNER'),
    'real_writer_class' => get_class($writer), 'real_writer_sha256' => hash_file('sha256', $argv[3].'/app/Services/QboAdminSnapshotStore.php'),
    'lifecycles' => $lifecycles, 'laravel_due_cases' => $dueCases, 'writer_failure' => $writerFailure,
    'timestamp_cases' => $timestampCases, 'invalid_timestamp_cases_rejected' => count($invalidCases),
    'production_cache_or_timezone_changes' => false, 'disposable_framework_mutex_lifecycle_only' => true,
];
echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR).PHP_EOL;
