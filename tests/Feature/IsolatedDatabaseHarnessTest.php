<?php

namespace Tests\Feature;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use LogicException;
use Tests\Support\IsolatedTestDatabase;
use Tests\TestCase;

class IsolatedDatabaseHarnessTest extends TestCase
{
    public function test_every_database_alias_uses_the_same_isolated_sqlite_connection(): void
    {
        $expectedPath = IsolatedTestDatabase::databasePath();

        foreach (array_keys(config('database.connections')) as $name) {
            $this->assertSame('sqlite', config("database.connections.{$name}.driver"));
            $this->assertSame($expectedPath, config("database.connections.{$name}.database"));
            $this->assertSame(DB::connection('sqlite')->getPdo(), DB::connection($name)->getPdo());
        }

        $this->assertSame('sqlite', config('database.default'));
        $this->assertSame('sqlite', config('database.fuel_connection'));
        $this->assertTrue(Schema::hasTable('users'));
        $this->assertTrue(Schema::hasTable('dtforders'));
        $this->assertTrue(Schema::hasTable('stripe_webhook_events'));
    }

    public function test_database_guard_rejects_a_network_driver_before_it_can_be_used(): void
    {
        config()->set('database.connections.mysql.driver', 'mysql');
        config()->set('database.connections.mysql.host', 'production.invalid');

        $this->expectException(LogicException::class);
        $this->expectExceptionMessage('Database safety check failed for [mysql]');

        IsolatedTestDatabase::assertSafeConfiguration($this->app);
    }

    public function test_external_side_effect_drivers_and_credentials_are_forced_safe(): void
    {
        $this->assertSame('array', config('mail.default'));
        $this->assertSame('sync', config('queue.default'));
        $this->assertSame('array', config('cache.default'));
        $this->assertSame('array', config('session.driver'));
        $this->assertSame('local', config('filesystems.default'));
        $this->assertSame('null', config('logging.default'));
        $this->assertFalse(config('auth_legacy.enabled'));

        $this->assertSame('', (string) config('services.stripe.key'));
        $this->assertSame('', (string) config('services.stripe.secret'));
        $this->assertSame('', (string) config('services.qbo.client_id'));
        $this->assertSame('', (string) config('services.qbo.client_secret'));
        $this->assertSame('', (string) config('services.dropbox.client_id'));
        $this->assertSame('', (string) config('services.dropbox.client_secret'));
        $this->assertSame('test-token-never-used', config('services.shippo.token'));
        $this->assertSame('null', getenv('BROADCAST_CONNECTION'));
    }
}
