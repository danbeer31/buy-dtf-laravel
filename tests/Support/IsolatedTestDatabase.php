<?php

namespace Tests\Support;

use Illuminate\Contracts\Foundation\Application;
use Illuminate\Database\Connection;
use Illuminate\Database\DatabaseManager;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Database\Schema\Builder;
use LogicException;

final class IsolatedTestDatabase
{
    private const DATABASE = ':memory:';

    /**
     * Replace every application database alias immediately after Laravel loads
     * configuration and before it registers or boots service providers.
     */
    public static function configureBeforeProviders(Application $app): void
    {
        if (! $app->environment('testing')) {
            throw new LogicException('Refusing to configure the isolated database outside APP_ENV=testing.');
        }

        $path = self::databasePath();
        $config = $app->make('config');
        $connections = $config->get('database.connections', []);

        if (! is_array($connections) || $connections === []) {
            throw new LogicException('No database connections are configured for the test application.');
        }

        foreach (array_keys($connections) as $name) {
            $connections[$name] = self::sqliteConfiguration($path);
        }

        $config->set('database.default', 'sqlite');
        $config->set('database.fuel_connection', 'sqlite');
        $config->set('database.connections', $connections);

        self::assertSafeConfiguration($app);
    }

    /**
     * Rebuild only the schema needed by tests. Production migrations are
     * intentionally not executed because several still hard-code MySQL aliases
     * and assume legacy tables already exist.
     */
    public static function rebuild(Application $app): void
    {
        self::assertSafeConfiguration($app);

        /** @var DatabaseManager $database */
        $database = $app->make('db');
        $connectionNames = array_keys((array) $app->make('config')->get('database.connections', []));

        foreach ($connectionNames as $name) {
            $database->purge($name);
        }

        $primary = $database->connection('sqlite');
        self::sharePrimaryPdo($database, $primary, $connectionNames);

        $schema = $primary->getSchemaBuilder();
        $schema->dropAllTables();

        self::createAuthenticationSchema($schema);
        self::createBusinessSchema($schema);
        self::createOrderSchema($schema);
        self::createPaymentAndWebhookSchema($schema);
        self::seedReferenceRows($primary);
    }

    public static function assertSafeConfiguration(Application $app): void
    {
        if (! $app->environment('testing')) {
            throw new LogicException('Database safety check failed: APP_ENV must be testing.');
        }

        $expectedPath = self::databasePath();
        $config = $app->make('config');
        $connections = $config->get('database.connections', []);

        if ($config->get('database.default') !== 'sqlite') {
            throw new LogicException('Database safety check failed: the default connection is not sqlite.');
        }

        if ($config->get('database.fuel_connection') !== 'sqlite') {
            throw new LogicException('Database safety check failed: the Fuel alias is not sqlite.');
        }

        foreach ($connections as $name => $connection) {
            $driver = $connection['driver'] ?? null;
            $database = $connection['database'] ?? null;
            $url = $connection['url'] ?? null;

            if ($driver !== 'sqlite' || $database !== $expectedPath || ! empty($url)) {
                throw new LogicException(sprintf(
                    'Database safety check failed for [%s]; every test alias must use the allowlisted SQLite file.',
                    $name
                ));
            }

            foreach (['host', 'port', 'username', 'password', 'unix_socket'] as $networkKey) {
                if (array_key_exists($networkKey, $connection)) {
                    throw new LogicException(sprintf(
                        'Database safety check failed for [%s]; network option [%s] is present.',
                        $name,
                        $networkKey
                    ));
                }
            }
        }
    }

    public static function databasePath(): string
    {
        return self::DATABASE;
    }

    /** @return array<string, mixed> */
    private static function sqliteConfiguration(string $path): array
    {
        return [
            'driver' => 'sqlite',
            'url' => null,
            'database' => $path,
            'prefix' => '',
            'foreign_key_constraints' => true,
            'busy_timeout' => 5000,
            'journal_mode' => null,
            'synchronous' => null,
            'transaction_mode' => 'DEFERRED',
        ];
    }

    /** @param list<string> $connectionNames */
    private static function sharePrimaryPdo(
        DatabaseManager $database,
        Connection $primary,
        array $connectionNames
    ): void {
        $pdo = $primary->getPdo();

        foreach ($connectionNames as $name) {
            $connection = $database->connection($name);
            $connection->setPdo($pdo);
            $connection->setReadPdo($pdo);
        }
    }

    private static function createAuthenticationSchema(Builder $schema): void
    {
        $schema->create('users', function (Blueprint $table): void {
            $table->id();
            $table->unsignedInteger('fuel_business_id')->nullable()->index();
            $table->string('name');
            $table->string('email')->unique();
            $table->string('role', 20)->default('customer')->index();
            $table->timestamp('email_verified_at')->nullable();
            $table->string('password');
            $table->boolean('password_reset_required')->default(false)->index();
            $table->rememberToken();
            $table->timestamps();
        });

        $schema->create('password_reset_tokens', function (Blueprint $table): void {
            $table->string('email')->primary();
            $table->string('token');
            $table->timestamp('created_at')->nullable();
        });

        $schema->create('sessions', function (Blueprint $table): void {
            $table->string('id')->primary();
            $table->unsignedBigInteger('user_id')->nullable()->index();
            $table->string('ip_address', 45)->nullable();
            $table->text('user_agent')->nullable();
            $table->longText('payload');
            $table->integer('last_activity')->index();
        });
    }

    private static function createBusinessSchema(Builder $schema): void
    {
        $schema->create('businesses', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('user_id')->nullable();
            $table->string('business_name')->nullable();
            $table->string('contact_name')->nullable();
            $table->string('email')->nullable()->unique();
            $table->string('phone')->nullable();
            $table->string('address')->nullable();
            $table->string('address2')->nullable();
            $table->string('city')->nullable();
            $table->string('state', 2)->nullable();
            $table->string('zip', 10)->nullable();
            $table->string('qbo_customer_id')->nullable();
            $table->string('status')->default('unconfirmed');
            $table->boolean('tax_exempt')->default(false);
            $table->string('tax_number')->nullable();
            $table->string('confirmation_code')->nullable();
            $table->timestamps();
        });

        $schema->create('business_settings', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('business_id')->unique();
            $table->decimal('rate', 8, 4)->default(0.0300);
            $table->timestamps();
        });

        $schema->create('business_user', function (Blueprint $table): void {
            $table->id();
            $table->unsignedInteger('business_id');
            $table->unsignedBigInteger('user_id');
            $table->string('role', 20)->default('member');
            $table->boolean('is_active')->default(true);
            $table->unsignedBigInteger('invited_by')->nullable();
            $table->timestamps();
            $table->unique(['business_id', 'user_id']);
        });

        $schema->create('paymentmethods', function (Blueprint $table): void {
            $table->id();
            $table->string('method_name');
            $table->string('payment_controller')->nullable();
            $table->text('description')->nullable();
            $table->text('message')->nullable();
            $table->timestamps();
        });

        $schema->create('business_paymentmethods', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('business_id');
            $table->unsignedBigInteger('payment_method_id');
            $table->unique(['business_id', 'payment_method_id']);
        });

        $schema->create('settings', function (Blueprint $table): void {
            $table->id();
            $table->string('key')->unique();
            $table->text('value')->nullable();
            $table->timestamps();
        });
    }

    private static function createOrderSchema(Builder $schema): void
    {
        $schema->create('shippingmethods', function (Blueprint $table): void {
            $table->id();
            $table->string('shipping_method');
            $table->string('shipping_class')->nullable();
            $table->text('description')->nullable();
            $table->text('message')->nullable();
            $table->timestamps();
        });

        $schema->create('order_statuses', function (Blueprint $table): void {
            $table->id();
            $table->string('name');
            $table->string('color')->nullable();
            $table->integer('sort_order')->default(0);
            $table->boolean('locked')->default(false);
            $table->boolean('email')->default(false);
            $table->timestamps();
        });

        $schema->create('dtforders', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('business_id')->nullable()->index();
            $table->date('order_date')->nullable();
            $table->unsignedBigInteger('shipping_method_id')->nullable();
            $table->string('shipping_method')->nullable();
            $table->unsignedBigInteger('payment_method_id')->nullable();
            $table->string('paymentmethod')->nullable();
            $table->decimal('weight', 12, 4)->default(0);
            $table->decimal('price', 12, 4)->default(0);
            $table->decimal('shipping_cost', 12, 4)->default(0);
            $table->decimal('total_price', 12, 4)->default(0);
            $table->decimal('sales_tax', 12, 4)->default(0);
            $table->decimal('admin_discount_pct', 7, 4)->nullable();
            $table->unsignedTinyInteger('admin_discount_locked')->default(0);
            $table->decimal('square_inches', 14, 4)->default(0);
            $table->decimal('linear_inches', 14, 4)->default(0);
            $table->unsignedInteger('status')->default(1)->index();
            $table->string('qbo_invoice_id')->nullable();
            $table->string('qbo_invoice_number')->nullable();
            $table->string('shippo_service_name')->nullable();
            $table->string('shippo_transaction_id')->nullable();
            $table->string('tracking_number')->nullable()->index();
            $table->string('label_url')->nullable();
            $table->timestamps();
        });

        $schema->create('dtfimages', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('dtforder_id')->index();
            $table->string('image')->nullable();
            $table->string('thumbnail')->nullable();
            $table->string('native_filename')->nullable();
            $table->unsignedBigInteger('file_size')->nullable();
            $table->string('sha256_original', 64)->nullable();
            $table->string('sha256_bitmap', 64)->nullable();
            $table->string('upload_mime', 120)->nullable();
            $table->string('item_type', 40)->nullable();
            $table->text('item_meta')->nullable();
            $table->string('image_name')->nullable();
            $table->text('image_notes')->nullable();
            $table->decimal('width', 12, 4)->default(0);
            $table->decimal('height', 12, 4)->default(0);
            $table->decimal('width_ratio', 12, 6)->nullable();
            $table->decimal('height_ratio', 12, 6)->nullable();
            $table->decimal('orig_width', 12, 4)->nullable();
            $table->decimal('orig_height', 12, 4)->nullable();
            $table->unsignedInteger('quantity')->default(1);
            $table->decimal('price', 12, 4)->nullable();
            $table->decimal('admin_unit_price', 12, 4)->nullable();
            $table->unsignedTinyInteger('admin_price_locked')->default(0);
            $table->dateTime('date_uploaded')->nullable();
            $table->unsignedTinyInteger('production')->default(0);
            $table->timestamps();
        });

        $schema->create('shippingaddresses', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('order_id')->index();
            $table->string('name');
            $table->string('address1');
            $table->string('address2')->nullable();
            $table->string('city');
            $table->string('state', 2);
            $table->string('zip', 10);
            $table->timestamps();
        });

        $schema->create('savedimages', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('business_id')->index();
            $table->string('image');
            $table->string('thumbnail')->nullable();
            $table->string('image_name')->nullable();
            $table->text('image_notes')->nullable();
            $table->decimal('width', 12, 4)->nullable();
            $table->decimal('height', 12, 4)->nullable();
            $table->dateTime('date_uploaded')->nullable();
            $table->timestamps();
        });
    }

    private static function createPaymentAndWebhookSchema(Builder $schema): void
    {
        $schema->create('paymentinfos', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('dtforder_id')->index();
            $table->unsignedBigInteger('business_id')->nullable()->index();
            $table->string('processor')->nullable();
            $table->string('processor_confirm')->nullable();
            $table->string('stripe_charge_id')->nullable()->index();
            $table->string('qbo_payment_id')->nullable();
            $table->text('qbo_invoice_numbers')->nullable();
            $table->string('qbo_fee_expense_id')->nullable();
            $table->decimal('amount', 12, 4)->default(0);
            $table->decimal('stripe_fee', 12, 4)->nullable();
            $table->text('notes')->nullable();
            $table->string('status')->nullable();
            $table->timestamps();
        });

        $schema->create('stripe_payouts', function (Blueprint $table): void {
            $table->id();
            $table->string('stripe_payout_id')->unique();
            $table->decimal('amount', 12, 2)->default(0);
            $table->decimal('fee', 12, 2)->default(0);
            $table->decimal('net', 12, 2)->default(0);
            $table->string('currency', 3)->default('USD');
            $table->string('status')->nullable();
            $table->dateTime('arrival_date')->nullable();
            $table->text('description')->nullable();
            $table->string('qbo_deposit_id')->nullable();
            $table->string('qbo_transfer_id')->nullable();
            $table->timestamps();
        });

        $schema->create('stripe_payout_entries', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('stripe_payout_id')->index();
            $table->string('stripe_transaction_id')->index();
            $table->string('type')->nullable();
            $table->decimal('gross', 12, 2)->default(0);
            $table->decimal('fee', 12, 2)->default(0);
            $table->decimal('net', 12, 2)->default(0);
            $table->unsignedBigInteger('dtforder_id')->nullable()->index();
            $table->string('qbo_expense_id')->nullable();
            $table->string('qbo_refund_id')->nullable();
            $table->text('notes')->nullable();
            $table->timestamps();
        });

        $schema->create('stripe_webhook_events', function (Blueprint $table): void {
            $table->id();
            $table->string('stripe_event_id')->unique();
            $table->string('type');
            $table->json('payload');
            $table->timestamp('processed_at')->nullable();
            $table->timestamps();
        });

        $schema->create('stripe_sync_logs', function (Blueprint $table): void {
            $table->id();
            $table->string('sync_type');
            $table->string('event_type')->nullable();
            $table->string('stripe_id')->nullable();
            $table->string('status');
            $table->text('message')->nullable();
            $table->json('payload')->nullable();
            $table->timestamps();
        });
    }

    private static function seedReferenceRows(Connection $connection): void
    {
        $now = now();

        $connection->table('paymentmethods')->insert([
            [
                'id' => 1,
                'method_name' => 'Invoice',
                'payment_controller' => 'invoice',
                'created_at' => $now,
                'updated_at' => $now,
            ],
            [
                'id' => 2,
                'method_name' => 'Credit Card',
                'payment_controller' => 'cardpayment',
                'created_at' => $now,
                'updated_at' => $now,
            ],
        ]);
    }
}
