<?php

namespace App\Providers;

use Illuminate\Support\ServiceProvider;
use Illuminate\Pagination\Paginator;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        Paginator::useBootstrapFive();

        if (!defined('DOCROOT')) {
            define('DOCROOT', public_path() . DIRECTORY_SEPARATOR);
        }

        // Force FuelModel to use the local fuelmysql connection
        $fuelConn = env('FUEL_DB_CONNECTION', 'fuelmysql');
        if ($fuelConn === 'remotefuel') {
            $fuelConn = 'fuelmysql';
        }
        config(['database.fuel_connection' => $fuelConn]);
    }
}
