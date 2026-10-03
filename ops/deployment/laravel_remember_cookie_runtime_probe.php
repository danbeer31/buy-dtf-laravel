<?php

declare(strict_types=1);

use Illuminate\Contracts\Console\Kernel;
use Illuminate\Foundation\Application;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

const EXPECTED_FUEL_CONNECTION = 'fuelmysql';
const ITEM_META_MIGRATION = '2026_10_01_120000_add_item_meta_to_savedimages_table';
const INCOMING_ORDER_MIGRATION = '2026_09_27_120000_create_incoming_order_v1_tables';
const INCOMING_ORDER_TABLES = ['incoming_order_jobs', 'api_asset_records'];
const REQUIRED_FUEL_TABLES = [
    'businesses',
    'dtforders',
    'dtfimages',
    'savedimages',
    'incoming_order_jobs',
    'api_asset_records',
];

set_exception_handler(static function (Throwable $exception): never {
    fwrite(STDERR, json_encode([
        'status' => 'error',
        'exception_class' => get_class($exception),
        'message_sha256' => hash('sha256', $exception->getMessage()),
    ], JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR).PHP_EOL);
    exit(1);
});

if (PHP_SAPI !== 'cli' || $argc !== 2) {
    fwrite(STDERR, 'Usage: php laravel_remember_cookie_runtime_probe.php APP_ROOT'.PHP_EOL);
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
if ($fuelConnection !== EXPECTED_FUEL_CONNECTION) {
    failProbe('The configured Fuel connection is not the reviewed fuelmysql connection.');
}

$fuelConfig = config('database.connections.'.EXPECTED_FUEL_CONNECTION);
if (! is_array($fuelConfig) || ($fuelConfig['driver'] ?? null) !== 'mysql') {
    failProbe('The reviewed fuelmysql connection is not configured as MySQL.');
}
$databaseName = $fuelConfig['database'] ?? null;
if (! is_string($databaseName) || $databaseName === '') {
    failProbe('The reviewed Fuel database name is unavailable.');
}
$ledgerTable = config('database.migrations.table', 'migrations');
if (! is_string($ledgerTable) || ! preg_match('/\A[A-Za-z0-9_]+\z/', $ledgerTable)) {
    failProbe('The migration ledger table name is invalid.');
}

$fuelSchema = Schema::connection(EXPECTED_FUEL_CONNECTION);
if (! $fuelSchema->hasTable($ledgerTable)) {
    failProbe('The Fuel migration ledger does not exist.');
}
$requiredTables = [];
foreach (REQUIRED_FUEL_TABLES as $requiredTable) {
    $requiredTables[$requiredTable] = $fuelSchema->hasTable($requiredTable);
}
if (in_array(false, $requiredTables, true)) {
    failProbe('One or more required Fuel tables are missing.');
}

$fuel = DB::connection(EXPECTED_FUEL_CONNECTION);
$fuel->getPdo();
$ledgerRows = array_map(
    static fn (object $row): array => [
        'migration' => (string) $row->migration,
        'batch' => (int) $row->batch,
    ],
    $fuel->table($ledgerTable)
        ->select(['migration', 'batch'])
        ->orderBy('migration')
        ->orderBy('batch')
        ->get()
        ->all(),
);
$itemMetaMigrationCount = count(array_filter(
    $ledgerRows,
    static fn (array $row): bool => $row['migration'] === ITEM_META_MIGRATION,
));
$incomingOrderMigrationCount = count(array_filter(
    $ledgerRows,
    static fn (array $row): bool => $row['migration'] === INCOMING_ORDER_MIGRATION,
));

$schemaSections = [
    'tables' => selectRows($fuel, <<<'SQL'
SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_COLLATION, CREATE_OPTIONS
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = ?
ORDER BY TABLE_NAME
SQL, [$databaseName]),
    'columns' => selectRows($fuel, <<<'SQL'
SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
       COLUMN_DEFAULT, EXTRA, CHARACTER_SET_NAME, COLLATION_NAME,
       GENERATION_EXPRESSION
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = ?
ORDER BY TABLE_NAME, ORDINAL_POSITION
SQL, [$databaseName]),
    'statistics' => selectRows($fuel, <<<'SQL'
SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME,
       COLLATION, SUB_PART, NULLABLE, INDEX_TYPE, EXPRESSION
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = ?
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
SQL, [$databaseName]),
    'table_constraints' => selectRows($fuel, <<<'SQL'
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
FROM information_schema.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = ?
ORDER BY TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
SQL, [$databaseName]),
    'key_column_usage' => selectRows($fuel, <<<'SQL'
SELECT TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION, COLUMN_NAME,
       POSITION_IN_UNIQUE_CONSTRAINT, REFERENCED_TABLE_SCHEMA,
       REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE CONSTRAINT_SCHEMA = ?
ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
SQL, [$databaseName]),
    'referential_constraints' => selectRows($fuel, <<<'SQL'
SELECT TABLE_NAME, CONSTRAINT_NAME, UNIQUE_CONSTRAINT_NAME,
       MATCH_OPTION, UPDATE_RULE, DELETE_RULE
FROM information_schema.REFERENTIAL_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = ?
ORDER BY TABLE_NAME, CONSTRAINT_NAME
SQL, [$databaseName]),
];
$schemaSectionCounts = [];
foreach ($schemaSections as $section => $rows) {
    $schemaSectionCounts[$section] = count($rows);
}
$itemMetaDefinitions = array_values(array_filter(
    $schemaSections['columns'],
    static fn (array $row): bool => (string) ($row['TABLE_NAME'] ?? '') === 'savedimages'
        && (string) ($row['COLUMN_NAME'] ?? '') === 'item_meta',
));
if (count($itemMetaDefinitions) !== 1) {
    failProbe('The savedimages.item_meta definition is missing or non-unique.');
}
$incomingOrderDefinitions = [];
foreach ($schemaSections as $section => $rows) {
    $incomingOrderDefinitions[$section] = array_values(array_filter(
        $rows,
        static fn (array $row): bool => in_array(
            (string) ($row['TABLE_NAME'] ?? ''),
            INCOMING_ORDER_TABLES,
            true,
        ),
    ));
}
$incomingOrderTables = [];
$incomingOrderRowCounts = [];
foreach (INCOMING_ORDER_TABLES as $targetTable) {
    $incomingOrderTables[$targetTable] = $requiredTables[$targetTable];
    $incomingOrderRowCounts[$targetTable] = (int) $fuel->table($targetTable)->count();
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

$packageNames = [
    'guzzlehttp/guzzle',
    'laravel/framework',
    'league/commonmark',
    'league/flysystem',
    'league/flysystem-local',
];
$packageVersions = [];
$packageInstallPaths = [];
foreach ($packageNames as $packageName) {
    if (! Composer\InstalledVersions::isInstalled($packageName)) {
        fwrite(STDERR, 'Required package is not installed: '.$packageName.PHP_EOL);
        exit(1);
    }

    $prettyVersion = Composer\InstalledVersions::getPrettyVersion($packageName);
    $installPath = Composer\InstalledVersions::getInstallPath($packageName);
    $realInstallPath = is_string($installPath) ? realpath($installPath) : false;
    if (! is_string($prettyVersion) || $prettyVersion === '' || $realInstallPath === false) {
        fwrite(STDERR, 'Required package identity is unavailable: '.$packageName.PHP_EOL);
        exit(1);
    }

    $packageVersions[$packageName] = ltrim($prettyVersion, 'v');
    $packageInstallPaths[$packageName] = $realInstallPath;
}

$phpExtensions = get_loaded_extensions();
sort($phpExtensions, SORT_STRING);

$allowedIncomingOrderHosts = config('incoming_order.allowed_hosts', []);
if (! is_array($allowedIncomingOrderHosts)) {
    fwrite(STDERR, 'The incoming-order allowed-host configuration is invalid.'.PHP_EOL);
    exit(1);
}

$payload = [
    'database_envelope_version' => 1,
    'app_environment' => (string) $app->environment(),
    'app_debug' => (bool) config('app.debug'),
    'config_cached' => $app->configurationIsCached(),
    'queue_connection' => (string) config('queue.default'),
    'default_database_connection' => $defaultConnection,
    'fuel_database_connection' => $fuelConnection,
    'connections' => [
        'configured_fuel_connection' => $fuelConnection,
        'expected_fuel_connection' => EXPECTED_FUEL_CONNECTION,
        'fuel_driver' => (string) $fuel->getDriverName(),
        'fuel_database_name_sha256' => hash('sha256', $databaseName),
        'default_connection' => $defaultConnection,
        'connection_match' => $fuelConnection === EXPECTED_FUEL_CONNECTION,
    ],
    'migration_ledger' => [
        'table' => $ledgerTable,
        'exists' => true,
        'row_count' => count($ledgerRows),
        'rows_sha256' => canonicalHash($ledgerRows),
        'target_migration' => ITEM_META_MIGRATION,
        'target_entry_count' => $itemMetaMigrationCount,
        'incoming_order_migration' => INCOMING_ORDER_MIGRATION,
        'incoming_order_entry_count' => $incomingOrderMigrationCount,
    ],
    'schema' => [
        'sha256' => canonicalHash($schemaSections),
        'section_row_counts' => $schemaSectionCounts,
        'required_tables' => $requiredTables,
        'savedimages_item_meta' => [
            'exists' => true,
            'definition' => $itemMetaDefinitions,
            'nonnull_rows' => (int) $fuel->table('savedimages')->whereNotNull('item_meta')->count(),
        ],
        'incoming_order_tables' => $incomingOrderTables,
        'incoming_order_row_counts' => $incomingOrderRowCounts,
        'incoming_order_definitions' => $incomingOrderDefinitions,
    ],
    'laravel_version' => Application::VERSION,
    'guzzle_version' => Composer\InstalledVersions::getPrettyVersion('guzzlehttp/guzzle'),
    'package_versions' => $packageVersions,
    'package_install_paths' => $packageInstallPaths,
    'php_version' => PHP_VERSION,
    'php_extensions' => $phpExtensions,
    'laravel_class_path' => (new ReflectionClass(Application::class))->getFileName(),
    'guzzle_class_path' => (new ReflectionClass(GuzzleHttp\Client::class))->getFileName(),
    'disabled_capabilities' => [
        'incoming_order_receiver_enabled' => (bool) config('incoming_order.receiver_enabled', false),
        'incoming_order_job_label_enabled' => (bool) config('incoming_order.job_label_enabled', false),
        'incoming_order_retention_enabled' => (bool) config('incoming_order.retention.enabled', false),
        'incoming_order_allowed_host_count' => count($allowedIncomingOrderHosts),
    ],
    'business_activity' => $summary,
    'queue_tables' => $queueSummary,
];

echo json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES).PHP_EOL;

/**
 * @param array<int, mixed> $bindings
 * @return array<int, array<string, int|float|string|null>>
 */
function selectRows(object $connection, string $sql, array $bindings): array
{
    return array_map(
        static fn (object $row): array => normalizeRow((array) $row),
        $connection->select($sql, $bindings),
    );
}

/** @param array<string, mixed> $row
 *  @return array<string, int|float|string|null>
 */
function normalizeRow(array $row): array
{
    $normalized = [];
    foreach ($row as $key => $value) {
        if ($value === null || is_int($value) || is_float($value) || is_string($value)) {
            $normalized[(string) $key] = $value;
        } elseif (is_bool($value)) {
            $normalized[(string) $key] = $value ? 1 : 0;
        } else {
            $normalized[(string) $key] = (string) $value;
        }
    }

    return $normalized;
}

/** @param mixed $value */
function canonicalHash(mixed $value): string
{
    return hash('sha256', json_encode(
        $value,
        JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION | JSON_THROW_ON_ERROR,
    ));
}

function failProbe(string $message): never
{
    fwrite(STDERR, $message.PHP_EOL);
    exit(1);
}
