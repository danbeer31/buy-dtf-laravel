<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Admin\BusinessController;

Route::middleware(['auth', 'admin'])
    ->prefix('admin')
    ->name('admin.')
    ->group(function () {
        Route::view('/', 'admin.dashboard')->name('dashboard');

        Route::get('/businesses', [BusinessController::class, 'index'])->name('businesses.index');
        Route::get('/businesses/{business}', [BusinessController::class, 'show'])->name('businesses.show');
        Route::patch('/businesses/{business}/rate', [BusinessController::class, 'updateRate'])->name('businesses.update-rate');
        Route::patch('/businesses/{business}/tax-exempt', [BusinessController::class, 'toggleTaxExempt'])->name('businesses.toggle-tax-exempt');
        Route::post('/businesses/{business}/impersonate', [BusinessController::class, 'impersonate'])->name('businesses.impersonate');
        Route::post('/stop-impersonating', [BusinessController::class, 'stopImpersonating'])->name('businesses.stop-impersonating');
    });
