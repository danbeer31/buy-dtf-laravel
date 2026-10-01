<?php

declare(strict_types=1);

use Illuminate\Contracts\Console\Kernel;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

const EXPECTED_FUEL_CONNECTION = 'fuelmysql';
const TARGET_MIGRATION = '2026_09_27_120000_create_incoming_order_v1_tables';
const TARGET_TABLES = ['incoming_order_jobs', 'api_asset_records'];
const REQUIRED_FUEL_TABLES = ['businesses', 'dtforders', 'dtfimages'];

/**
 * Boot the installed application and emit a credential-free, deterministic
 * snapshot of the database/configuration facts required by the reviewed
 * incoming-order v1 deployment procedure.
 *
 * Usage: php incoming_order_v1_runtime_probe.php /absolute/application/root
 */

if (PHP_SAPI !== 'cli') {
    fail('This probe is CLI-only.');
}

$applicationRoot = $argv[1] ?? '';
$realApplicationRoot = is_string($applicationRoot) ? realpath($applicationRoot) : false;

if ($realApplicationRoot === false || ! is_dir($realApplicationRoot)) {
    fail('The application root is not a real directory.');
}

$autoload = $realApplicationRoot.'/vendor/autoload.php';
$bootstrap = $realApplicationRoot.'/bootstrap/app.php';

if (! is_file($autoload) || ! is_file($bootstrap)) {
    fail('The application bootstrap files are unavailable.');
}

$composerLoader = require $autoload;

$app = require $bootstrap;
$kernel = $app->make(Kernel::class);
$kernel->bootstrap();

try {
    $configuredFuelConnection = config('database.fuel_connection');
    if ($configuredFuelConnection !== EXPECTED_FUEL_CONNECTION) {
        throw new RuntimeException('The configured Fuel connection is not the reviewed fuelmysql connection.');
    }

    $fuelConfig = config('database.connections.'.EXPECTED_FUEL_CONNECTION);
    if (! is_array($fuelConfig) || ($fuelConfig['driver'] ?? null) !== 'mysql') {
        throw new RuntimeException('The reviewed fuelmysql connection is not configured as MySQL.');
    }

    $databaseName = $fuelConfig['database'] ?? null;
    if (! is_string($databaseName) || $databaseName === '') {
        throw new RuntimeException('The reviewed Fuel database name is unavailable.');
    }

    if (($argv[2] ?? '') === '--write-mysql-client') {
        $clientPath = $argv[3] ?? '';
        if (! is_string($clientPath) || $clientPath === '' || file_exists($clientPath)) {
            throw new RuntimeException('The temporary MySQL client path is invalid or already exists.');
        }
        $clientDirectory = dirname($clientPath);
        $realClientDirectory = realpath($clientDirectory);
        if ($realClientDirectory === false || ! is_dir($realClientDirectory)) {
            throw new RuntimeException('The temporary MySQL client directory is invalid.');
        }
        $approvedClientRoot = realpath(
            $realApplicationRoot.'/storage/app/private/operations/incoming-order-v1-rollbacks',
        );
        if (
            $approvedClientRoot === false
            || ($realClientDirectory !== $approvedClientRoot
                && ! str_starts_with(
                    $realClientDirectory,
                    $approvedClientRoot.DIRECTORY_SEPARATOR,
                ))
        ) {
            throw new RuntimeException('The temporary MySQL client path is outside the approved rollback root.');
        }
        $options = [
            'host' => $fuelConfig['host'] ?? null,
            'port' => $fuelConfig['port'] ?? null,
            'socket' => $fuelConfig['unix_socket'] ?? null,
            'user' => $fuelConfig['username'] ?? null,
            'password' => $fuelConfig['password'] ?? null,
        ];
        $lines = ['[client]'];
        foreach ($options as $name => $value) {
            if ($value === null || $value === '') {
                continue;
            }
            $lines[] = $name.'='.mysqlOptionValue((string) $value);
        }
        $handle = @fopen($clientPath, 'x');
        if ($handle === false) {
            throw new RuntimeException('Unable to create the temporary MySQL client file.');
        }
        try {
            if (fwrite($handle, implode(PHP_EOL, $lines).PHP_EOL) === false) {
                throw new RuntimeException('Unable to write the temporary MySQL client file.');
            }
        } finally {
            fclose($handle);
        }
        if (! chmod($clientPath, 0600)) {
            @unlink($clientPath);
            throw new RuntimeException('Unable to restrict the temporary MySQL client file.');
        }
        fwrite(STDOUT, json_encode([
            'status' => 'created',
            'client_file' => $clientPath,
            'database_name' => $databaseName,
            'database_name_sha256' => hash('sha256', $databaseName),
        ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR).PHP_EOL);
        exit(0);
    }

    $ledgerTable = config('database.migrations.table', 'migrations');
    if (! is_string($ledgerTable) || ! preg_match('/\A[A-Za-z0-9_]+\z/', $ledgerTable)) {
        throw new RuntimeException('The migration ledger table name is invalid.');
    }

    $fuelSchema = Schema::connection(EXPECTED_FUEL_CONNECTION);
    $ledgerExists = $fuelSchema->hasTable($ledgerTable);
    if (! $ledgerExists) {
        throw new RuntimeException('The Fuel migration ledger does not exist; refusing to permit Artisan migrate.');
    }

    $requiredTables = [];
    foreach (REQUIRED_FUEL_TABLES as $requiredTable) {
        $requiredTables[$requiredTable] = $fuelSchema->hasTable($requiredTable);
    }

    if (in_array(false, $requiredTables, true)) {
        throw new RuntimeException('One or more required Fuel tables are missing.');
    }

    $targetTables = [];
    foreach (TARGET_TABLES as $targetTable) {
        $targetTables[$targetTable] = $fuelSchema->hasTable($targetTable);
    }

    $fuel = DB::connection(EXPECTED_FUEL_CONNECTION);
    $fuel->getPdo();

    $requiredTableRowCounts = [];
    foreach (REQUIRED_FUEL_TABLES as $requiredTable) {
        $requiredTableRowCounts[$requiredTable] = $fuel->table($requiredTable)->count();
    }
    $targetTableRowCounts = [];
    foreach (TARGET_TABLES as $targetTable) {
        $targetTableRowCounts[$targetTable] = $targetTables[$targetTable]
            ? $fuel->table($targetTable)->count()
            : null;
    }

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

    $targetMigrationEntries = array_values(array_filter(
        $ledgerRows,
        static fn (array $row): bool => $row['migration'] === TARGET_MIGRATION,
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

    $schemaCounts = [];
    foreach ($schemaSections as $section => $rows) {
        $schemaCounts[$section] = count($rows);
    }
    $targetDefinitions = [];
    foreach ($schemaSections as $section => $rows) {
        $targetDefinitions[$section] = array_values(array_filter(
            $rows,
            static fn (array $row): bool => in_array(
                (string) ($row['TABLE_NAME'] ?? ''),
                TARGET_TABLES,
                true,
            ),
        ));
    }

    $defaultConnection = DB::getDefaultConnection();
    $queueConnection = (string) config('queue.default', '');
    $defaultSchema = Schema::connection($defaultConnection);
    $queueCounts = [
        'jobs_table_exists' => $defaultSchema->hasTable('jobs'),
        'failed_jobs_table_exists' => $defaultSchema->hasTable('failed_jobs'),
        'jobs' => null,
        'failed_jobs' => null,
    ];

    if ($queueCounts['jobs_table_exists']) {
        $queueCounts['jobs'] = DB::connection($defaultConnection)->table('jobs')->count();
    }
    if ($queueCounts['failed_jobs_table_exists']) {
        $queueCounts['failed_jobs'] = DB::connection($defaultConnection)->table('failed_jobs')->count();
    }

    $allowedHosts = config('incoming_order.allowed_hosts', []);
    if (! is_array($allowedHosts)) {
        $allowedHosts = [];
    }

    $rendererClass = 'App\\Services\\IncomingOrders\\JobCardRenderer';
    $renderer = [
        'class_available' => false,
        'readiness' => null,
    ];
    if (class_exists($rendererClass)) {
        $readiness = app($rendererClass)->readiness();
        $renderer = [
            'class_available' => true,
            'readiness' => [
                'ready' => (bool) ($readiness['ready'] ?? false),
                'reason' => isset($readiness['reason']) ? (string) $readiness['reason'] : null,
                'renderer_version' => (string) ($readiness['renderer_version'] ?? ''),
                'font_sha256' => isset($readiness['font_sha256'])
                    ? (string) $readiness['font_sha256']
                    : null,
                'width_px' => (int) ($readiness['width_px'] ?? 0),
                'height_px' => (int) ($readiness['height_px'] ?? 0),
                'dpi' => (int) ($readiness['dpi'] ?? 0),
            ],
        ];
    }

    $result = [
        'probe_version' => 1,
        'generated_at_utc' => gmdate('Y-m-d\TH:i:s\Z'),
        'application_root' => $realApplicationRoot,
        'application_environment' => (string) app()->environment(),
        'application_debug' => (bool) config('app.debug', false),
        'runtime' => [
            'php_version' => PHP_VERSION,
            'laravel_version' => (string) app()->version(),
            'composer_classmap_authoritative' => is_object($composerLoader)
                && method_exists($composerLoader, 'isClassMapAuthoritative')
                ? (bool) $composerLoader->isClassMapAuthoritative()
                : null,
            'imagick_loaded' => extension_loaded('imagick'),
            'imagick_version' => extension_loaded('imagick')
                ? (string) (Imagick::getVersion()['versionString'] ?? '')
                : null,
        ],
        'connections' => [
            'configured_fuel_connection' => $configuredFuelConnection,
            'expected_fuel_connection' => EXPECTED_FUEL_CONNECTION,
            'fuel_driver' => (string) $fuel->getDriverName(),
            'fuel_database_name_sha256' => hash('sha256', $databaseName),
            'default_connection' => $defaultConnection,
            'migration_invocation_connection' => EXPECTED_FUEL_CONNECTION,
            'connection_match' => $configuredFuelConnection === EXPECTED_FUEL_CONNECTION,
        ],
        'migration_ledger' => [
            'table' => $ledgerTable,
            'exists' => true,
            'row_count' => count($ledgerRows),
            'rows_sha256' => canonicalHash($ledgerRows),
            'target_migration' => TARGET_MIGRATION,
            'target_entry_count' => count($targetMigrationEntries),
        ],
        'schema' => [
            'sha256' => canonicalHash($schemaSections),
            'section_row_counts' => $schemaCounts,
            'target_definitions' => $targetDefinitions,
            'required_tables' => $requiredTables,
            'required_table_row_counts' => $requiredTableRowCounts,
            'target_tables' => $targetTables,
            'target_table_row_counts' => $targetTableRowCounts,
        ],
        'capabilities' => [
            'receiver_enabled' => (bool) config('incoming_order.receiver_enabled', false),
            'job_label_enabled' => (bool) config('incoming_order.job_label_enabled', false),
            'retention_enabled' => (bool) config('incoming_order.retention.enabled', false),
            'allowed_host_count' => count($allowedHosts),
        ],
        'job_card_renderer' => $renderer,
        'queue' => [
            'connection' => $queueConnection,
            'counts' => $queueCounts,
        ],
    ];

    fwrite(STDOUT, json_encode(
        $result,
        JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR,
    ).PHP_EOL);
} catch (Throwable $exception) {
    fail($exception->getMessage());
}

/**
 * @param array<int, mixed> $bindings
 * @return array<int, array<string, int|float|string|null>>
 */
function selectRows(object $connection, string $sql, array $bindings): array
{
    return array_map(
        static function (object $row): array {
            $normalized = [];
            foreach ((array) $row as $key => $value) {
                if ($value === null || is_int($value) || is_float($value) || is_string($value)) {
                    $normalized[(string) $key] = $value;
                } elseif (is_bool($value)) {
                    $normalized[(string) $key] = $value ? 1 : 0;
                } else {
                    $normalized[(string) $key] = (string) $value;
                }
            }

            return $normalized;
        },
        $connection->select($sql, $bindings),
    );
}

/** @param mixed $value */
function canonicalHash(mixed $value): string
{
    return hash('sha256', json_encode(
        $value,
        JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION | JSON_THROW_ON_ERROR,
    ));
}

function mysqlOptionValue(string $value): string
{
    return '"'.str_replace(
        ['\\', '"', "\n", "\r"],
        ['\\\\', '\\"', '\\n', '\\r'],
        $value,
    ).'"';
}

function fail(string $message): never
{
    fwrite(STDERR, json_encode([
        'status' => 'error',
        'message' => $message,
    ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE).PHP_EOL);
    exit(1);
}
