<?php

namespace Tests;

use Illuminate\Contracts\Console\Kernel;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Bootstrap\LoadConfiguration;
use Illuminate\Foundation\Testing\TestCase as BaseTestCase;
use Illuminate\Support\Facades\Http;
use Tests\Support\IsolatedTestDatabase;

abstract class TestCase extends BaseTestCase
{
    public function createApplication()
    {
        $app = require Application::inferBasePath().'/bootstrap/app.php';
        $app->loadEnvironmentFrom('tests/testing.env');

        $app->afterBootstrapping(
            LoadConfiguration::class,
            static function (Application $app): void {
                IsolatedTestDatabase::configureBeforeProviders($app);
            }
        );

        $app->make(Kernel::class)->bootstrap();

        return $app;
    }

    protected function setUp(): void
    {
        parent::setUp();

        $this->withoutVite();
        IsolatedTestDatabase::rebuild($this->app);
        Http::preventStrayRequests();
    }
}
