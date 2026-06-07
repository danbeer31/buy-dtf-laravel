<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Third Party Services
    |--------------------------------------------------------------------------
    |
    | This file is for storing the credentials for third party services such
    | as Mailgun, Postmark, AWS and more. This file provides the de facto
    | location for this type of information, allowing packages to have
    | a conventional file to locate the various service credentials.
    |
    */

    'postmark' => [
        'key' => env('POSTMARK_API_KEY'),
    ],

    'resend' => [
        'key' => env('RESEND_API_KEY'),
    ],

    'ses' => [
        'key' => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],

    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel' => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    'namenumber' => [
        'url' => env('NAMENUMBER_URL', 'http://127.0.0.1:3000'),
        'token' => env('NAMENUMBER_TOKEN'),
    ],

    'shippo' => [
        'token' => env('SHIPPO_TOKEN'),
        'from_address' => [
            'name'    => env('SHIPPO_FROM_NAME', 'Next Level DTF'),
            'street1' => env('SHIPPO_FROM_STREET1', '811 Fairfield Ave.'),
            'street2' => env('SHIPPO_FROM_STREET2', ''),
            'city'    => env('SHIPPO_FROM_CITY', 'Laporte'),
            'state'   => env('SHIPPO_FROM_STATE', 'IN'),
            'zip'     => env('SHIPPO_FROM_ZIP', '46350'),
            'country' => env('SHIPPO_FROM_COUNTRY', 'US'),
        ],
        'default_parcel' => [
            'length'        => env('SHIPPO_PARCEL_LENGTH', '12'),
            'width'         => env('SHIPPO_PARCEL_WIDTH', '10'),
            'height'        => env('SHIPPO_PARCEL_HEIGHT', '4'),
            'distance_unit' => env('SHIPPO_PARCEL_DISTANCE_UNIT', 'in'),
        ],
    ],

    'stripe' => [
        'key' => env('STRIPE_KEY'),
        'secret' => env('STRIPE_SECRET'),
        'webhook_secret' => env('APP_ENV') === 'production'
            ? env('STRIPE_WEBHOOK_SECRET_PROD')
            : env('STRIPE_WEBHOOK_SECRET_DEV', env('STRIPE_WEBHOOK_SECRET')),
        // Optional comma-separated fallback list for secret rotation.
        // Example: STRIPE_WEBHOOK_SECRETS="whsec_old,whsec_new"
        'webhook_secrets' => array_values(array_filter(array_map(
            static fn ($secret) => trim((string) $secret),
            explode(',', (string) env('STRIPE_WEBHOOK_SECRETS', ''))
        ))),
    ],

    'qbo' => [
        'client_id' => env('QBO_CLIENT_ID'),
        'client_secret' => env('QBO_CLIENT_SECRET'),
        'environment' => env('QBO_ENVIRONMENT', 'Development'),
        'redirect_uri' => env('QBO_REDIRECT_URI'),
    ],

    'dropbox' => [
        'client_id' => env('DROPBOX_CLIENT_ID'),
        'client_secret' => env('DROPBOX_CLIENT_SECRET'),
        'redirect_uri' => env('DROPBOX_REDIRECT_URI'),
        'token_url' => 'https://api.dropboxapi.com/oauth2/token',
        'authorize_url' => 'https://www.dropbox.com/oauth2/authorize',
    ],

];
