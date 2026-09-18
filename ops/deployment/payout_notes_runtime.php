<?php

declare(strict_types=1);

use Illuminate\Contracts\Console\Kernel;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

const FUEL_CONNECTION = 'fuelmysql';
const MIGRATION_NAME = '2026_09_18_120000_add_notes_to_stripe_payout_entries_table';

function fail(string $message): never
{
    fwrite(STDERR, $message.PHP_EOL);
    exit(1);
}

function optionValue(string $value): string
{
    if (str_contains($value, "\0")) {
        fail('A database option contains an unsupported NUL byte.');
    }

    return '"'.strtr($value, [
        '\\' => '\\\\',
        '"' => '\\"',
        "\n" => '\\n',
        "\r" => '\\r',
        "\t" => '\\t',
    ]).'"';
}

if (PHP_SAPI !== 'cli') {
    fail('This helper may run only through PHP CLI.');
}

if ($argc < 3 || $argc > 4) {
    fail('Usage: php payout_notes_runtime.php APP_ROOT snapshot|write-defaults [OUTPUT_PATH]');
}

$appRoot = realpath($argv[1]);
$action = $argv[2];

if ($appRoot === false || ! is_dir($appRoot) || is_link($argv[1])) {
    fail('The application root is missing, invalid, or a symbolic link.');
}

if (! in_array($action, ['snapshot', 'write-defaults'], true)) {
    fail('Unsupported runtime-helper action.');
}

if (($action === 'snapshot' && $argc !== 3) || ($action === 'write-defaults' && $argc !== 4)) {
    fail('The selected runtime-helper action has invalid arguments.');
}

chdir($appRoot);
require $appRoot.'/vendor/autoload.php';
$app = require $appRoot.'/bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();

$configuredFuelConnection = config('database.fuel_connection');
if ($configuredFuelConnection !== FUEL_CONNECTION) {
    fail('The configured Fuel connection is not the audited fuelmysql connection.');
}

$connection = DB::connection(FUEL_CONNECTION);
$connectionConfig = $connection->getConfig();

if (($connectionConfig['driver'] ?? null) !== 'mysql') {
    fail('The audited Fuel connection is not a MySQL connection.');
}

$databaseInfo = $connection->selectOne('select database() as database_name, version() as server_version');
if ($databaseInfo === null || ! is_string($databaseInfo->database_name ?? null) || $databaseInfo->database_name === '') {
    fail('The Fuel connection did not resolve an active database.');
}

$databaseName = $databaseInfo->database_name;
$tableExists = Schema::connection(FUEL_CONNECTION)->hasTable('stripe_payout_entries');
$notesColumn = null;
$entryCount = null;
$payoutCount = null;
$showCreateHash = null;

if ($tableExists) {
    $column = $connection->selectOne(
        <<<'SQL'
            select data_type, column_type, is_nullable, ordinal_position
            from information_schema.columns
            where table_schema = database()
              and table_name = 'stripe_payout_entries'
              and column_name = 'notes'
            SQL,
    );

    if ($column !== null) {
        $notesColumn = [
            'data_type' => (string) $column->data_type,
            'column_type' => (string) $column->column_type,
            'is_nullable' => (string) $column->is_nullable,
            'ordinal_position' => (int) $column->ordinal_position,
        ];
    }

    $entryCount = (int) $connection->table('stripe_payout_entries')->count();
    $showCreate = $connection->selectOne('show create table `stripe_payout_entries`');
    if ($showCreate !== null) {
        $values = array_values((array) $showCreate);
        $showCreateHash = isset($values[1]) ? hash('sha256', (string) $values[1]) : null;
    }
}

if (Schema::connection(FUEL_CONNECTION)->hasTable('stripe_payouts')) {
    $payoutCount = (int) $connection->table('stripe_payouts')->count();
}

$migrationCount = null;
if (Schema::connection(FUEL_CONNECTION)->hasTable('migrations')) {
    $migrationCount = (int) $connection->table('migrations')
        ->where('migration', MIGRATION_NAME)
        ->count();
}

$snapshot = [
    'php_version' => PHP_VERSION,
    'fuel_connection' => FUEL_CONNECTION,
    'configured_fuel_connection' => $configuredFuelConnection,
    'driver' => (string) ($connectionConfig['driver'] ?? ''),
    'database_name' => $databaseName,
    'database_name_sha256' => hash('sha256', $databaseName),
    'server_version' => (string) ($databaseInfo->server_version ?? ''),
    'stripe_payout_entries_exists' => $tableExists,
    'stripe_payout_entries_count' => $entryCount,
    'stripe_payouts_count' => $payoutCount,
    'stripe_payout_entries_create_sha256' => $showCreateHash,
    'notes_column' => $notesColumn,
    'migration_ledger_count' => $migrationCount,
];

if ($action === 'write-defaults') {
    $outputPath = $argv[3];
    if (! str_starts_with($outputPath, DIRECTORY_SEPARATOR) || file_exists($outputPath) || is_link($outputPath)) {
        fail('The MySQL defaults output path must be a new absolute path.');
    }

    $parent = realpath(dirname($outputPath));
    if ($parent === false || ! is_dir($parent) || is_link(dirname($outputPath))) {
        fail('The MySQL defaults parent directory is invalid.');
    }

    $username = $connectionConfig['username'] ?? null;
    $password = $connectionConfig['password'] ?? null;
    $host = $connectionConfig['host'] ?? null;
    $port = $connectionConfig['port'] ?? null;
    $socket = $connectionConfig['unix_socket'] ?? null;

    if (! is_string($username) || ! is_string($password)) {
        fail('The Fuel connection credentials are not string values.');
    }

    $lines = [
        '[client]',
        'user='.optionValue($username),
        'password='.optionValue($password),
    ];

    if (is_string($socket) && $socket !== '') {
        $lines[] = 'socket='.optionValue($socket);
        $lines[] = 'protocol=socket';
    } else {
        if (! is_string($host) || $host === '' || (! is_string($port) && ! is_int($port))) {
            fail('The Fuel connection TCP endpoint is incomplete.');
        }

        $lines[] = 'host='.optionValue($host);
        $lines[] = 'port='.optionValue((string) $port);
        $lines[] = 'protocol=tcp';
    }

    $handle = @fopen($outputPath, 'x+b');
    if ($handle === false) {
        fail('Unable to create the exclusive MySQL defaults file.');
    }

    try {
        if (! chmod($outputPath, 0600)) {
            fail('Unable to restrict the MySQL defaults file permissions.');
        }

        $contents = implode(PHP_EOL, $lines).PHP_EOL;
        if (fwrite($handle, $contents) !== strlen($contents) || ! fflush($handle)) {
            fail('Unable to persist the MySQL defaults file.');
        }

        if (function_exists('fsync') && ! fsync($handle)) {
            fail('Unable to fsync the MySQL defaults file.');
        }
    } finally {
        fclose($handle);
    }
}

echo json_encode($snapshot, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES).PHP_EOL;
