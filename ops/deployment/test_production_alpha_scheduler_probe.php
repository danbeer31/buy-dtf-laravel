<?php

// Disposable-cache integration with real Laravel 12.69.1 classes. No task runs.
require $argv[1].'/vendor/autoload.php';
require __DIR__.'/production_alpha_scheduler_probe.php';

use Illuminate\Foundation\Application;
use Illuminate\Config\Repository;
use Illuminate\Cache\CacheServiceProvider;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Support\Facades\Facade;

$root = $argv[2];
if (! is_dir($root) || count(scandir($root)) !== 2) {
    throw new RuntimeException('A new empty disposable directory is required.');
}
$app = new Application($root);
$app->instance('files', new \Illuminate\Filesystem\Filesystem());
$app->instance('config', new Repository([
    'app' => ['timezone' => 'UTC'],
    'cache' => ['default' => 'file', 'stores' => ['file' => ['driver' => 'file', 'path' => $root.'/cache', 'lock_path' => $root.'/cache']]],
]));
$app->register(CacheServiceProvider::class);
Facade::setFacadeApplication($app);
$schedule = new Schedule('UTC');
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
$result = [
    'status' => 'pass', 'php_version' => PHP_VERSION, 'laravel_version' => Application::VERSION,
    'events' => $snapshot['events'], 'source_sha256' => $snapshot['source_sha256'],
    'active_mutex_read_only' => true, 'expired_mutex_read_only' => true, 'malformed_mutex_read_only_rejected' => true,
    'database_observer_select_only' => true, 'database_select_count' => count($queries),
    'normalized_commands' => array_map(static fn ($event): string => $event::normalizeCommand($event->command), $schedule->events()),
    'cookie_or_customer_data' => false, 'accounting_task_executed' => false,
    'snapshot_owner_is_only_sha256' => $snapshot['overlap_mutexes'][0]['owner_sha256'] === hash('sha256', 'SYNTHETIC-PRIVATE-MUTEX-OWNER'),
];
echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR).PHP_EOL;
