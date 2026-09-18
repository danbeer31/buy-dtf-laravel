<?php

declare(strict_types=1);

use Illuminate\Contracts\Console\Kernel;
use Illuminate\Foundation\Application;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

if (PHP_SAPI !== 'cli' || $argc !== 2) {
    fwrite(STDERR, 'Usage: php dependency_runtime_probe.php APP_ROOT'.PHP_EOL);
    exit(1);
}

$appRoot = realpath($argv[1]);
if ($appRoot === false || ! is_dir($appRoot) || is_link($argv[1])) {
    fwrite(STDERR, 'The application root is invalid or symbolic.'.PHP_EOL);
    exit(1);
}

chdir($appRoot);
require $appRoot.'/vendor/autoload.php';
$app = require $appRoot.'/bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();

$fuelConnection = config('database.fuel_connection');
if (! is_string($fuelConnection) || $fuelConnection === '') {
    fwrite(STDERR, 'The Fuel connection is not configured.'.PHP_EOL);
    exit(1);
}

$summary = [];
foreach ([
    'dtforders' => 'updated_at',
    'dtfimages' => 'updated_at',
    'paymentinfos' => 'updated_at',
    'stripe_sync_logs' => 'created_at',
] as $table => $timestampColumn) {
    if (! Schema::connection($fuelConnection)->hasTable($table)) {
        $summary[$table] = null;

        continue;
    }

    $query = DB::connection($fuelConnection)->table($table);
    $summary[$table] = [
        'count' => (int) (clone $query)->count(),
        'latest_sha256' => null,
    ];

    if (Schema::connection($fuelConnection)->hasColumn($table, $timestampColumn)) {
        $latest = (clone $query)->max($timestampColumn);
        $summary[$table]['latest_sha256'] = $latest === null
            ? null
            : hash('sha256', (string) $latest);
    }
}

$defaultConnection = DB::getDefaultConnection();
$queueSummary = [];
foreach (['jobs', 'failed_jobs'] as $table) {
    $queueSummary[$table] = Schema::connection($defaultConnection)->hasTable($table)
        ? (int) DB::connection($defaultConnection)->table($table)->count()
        : null;
}

$payload = [
    'app_environment' => (string) $app->environment(),
    'config_cached' => $app->configurationIsCached(),
    'queue_connection' => (string) config('queue.default'),
    'default_database_connection' => $defaultConnection,
    'fuel_database_connection' => $fuelConnection,
    'laravel_version' => Application::VERSION,
    'guzzle_version' => Composer\InstalledVersions::getPrettyVersion('guzzlehttp/guzzle'),
    'laravel_class_path' => (new ReflectionClass(Application::class))->getFileName(),
    'guzzle_class_path' => (new ReflectionClass(GuzzleHttp\Client::class))->getFileName(),
    'business_activity' => $summary,
    'queue_tables' => $queueSummary,
];

echo json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES).PHP_EOL;
