<?php

declare(strict_types=1);

$testEnvironment = [
    'APP_ENV' => 'testing',
    'APP_DEBUG' => 'false',
    'APP_KEY' => 'base64:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
    'APP_URL' => 'http://localhost',
    'APP_MAINTENANCE_DRIVER' => 'file',
    'AUTH_ENABLE_FUEL_LEGACY' => 'false',
    'BROADCAST_CONNECTION' => 'null',
    'CACHE_STORE' => 'array',
    'DB_CONNECTION' => 'sqlite',
    'DB_DATABASE' => ':memory:',
    'DB_URL' => '',
    'FILESYSTEM_DISK' => 'local',
    'FUEL_DB_CONNECTION' => 'sqlite',
    'FUEL_DB_URL' => '',
    'LOG_CHANNEL' => '"null"',
    'MAIL_MAILER' => 'array',
    'QUEUE_CONNECTION' => 'sync',
    'REMOTE_FUEL_DB_URL' => '',
    'SESSION_DRIVER' => 'array',
    'AWS_ACCESS_KEY_ID' => '',
    'AWS_SECRET_ACCESS_KEY' => '',
    'BUY_DTF_SECRET' => '',
    'DROPBOX_CLIENT_ID' => '',
    'DROPBOX_CLIENT_SECRET' => '',
    'NAMENUMBER_TOKEN' => '',
    'POSTMARK_API_KEY' => '',
    'QBO_CLIENT_ID' => '',
    'QBO_CLIENT_SECRET' => '',
    'QBO_ENVIRONMENT' => 'Development',
    'RESEND_API_KEY' => '',
    'SHIPPO_TOKEN' => 'test-token-never-used',
    'SLACK_BOT_USER_OAUTH_TOKEN' => '',
    'STRIPE_KEY' => '',
    'STRIPE_SECRET' => '',
    'STRIPE_WEBHOOK_SECRET' => '',
    'STRIPE_WEBHOOK_SECRET_DEV' => '',
    'STRIPE_WEBHOOK_SECRET_PROD' => '',
    'STRIPE_WEBHOOK_SECRETS' => '',
];

foreach ($testEnvironment as $name => $value) {
    putenv($name.'='.$value);
    $_ENV[$name] = $value;
    $_SERVER[$name] = $value;
}

if (! extension_loaded('pdo_sqlite')) {
    throw new RuntimeException(
        'The isolated test suite requires pdo_sqlite. No MySQL fallback is permitted.'
    );
}

require dirname(__DIR__).'/vendor/autoload.php';
