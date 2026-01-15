<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Admin\BusinessController;
use App\Http\Controllers\Admin\CustomNamesController;
use App\Http\Controllers\Admin\CustomColorController;
use App\Http\Controllers\Admin\UserController;

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

        Route::resource('users', UserController::class)->except(['show']);

        // Custom Names / Team Customization Admin
        Route::prefix('customnames')->name('customnames.')->group(function () {
            Route::get('/', [CustomNamesController::class, 'index'])->name('index');
            Route::get('/templates', [CustomNamesController::class, 'templates'])->name('templates');
            Route::get('/templatebuilder', [CustomNamesController::class, 'templateBuilder'])->name('templatebuilder');
            Route::get('/fonts', [CustomNamesController::class, 'fonts'])->name('fonts');
            Route::get('/fontsmap', [CustomNamesController::class, 'fontsMap'])->name('fontsmap');

            Route::get('/template/get', [CustomNamesController::class, 'getTemplate'])->name('template.get');
            Route::post('/template/create', [CustomNamesController::class, 'createTemplate'])->name('template.create');
            Route::post('/template/save', [CustomNamesController::class, 'saveTemplate'])->name('template.save');
            Route::post('/template/delete', [CustomNamesController::class, 'deleteTemplate'])->name('template.delete');
            Route::post('/templates/reload', [CustomNamesController::class, 'reloadTemplates'])->name('templates.reload');

            Route::post('/preview', [CustomNamesController::class, 'preview'])->name('preview');

            Route::get('/fonts/list', [CustomNamesController::class, 'listFonts'])->name('fonts.list');
            Route::post('/fonts/reload', [CustomNamesController::class, 'reloadFonts'])->name('fonts.reload');
            Route::post('/fonts/upload', [CustomNamesController::class, 'uploadFont'])->name('fonts.upload');
            Route::get('/fontsmap/get', [CustomNamesController::class, 'getFontsMap'])->name('fontsmap.get');
            Route::post('/fontsmap/save', [CustomNamesController::class, 'saveFontsMap'])->name('fontsmap.save');
            Route::post('/fonts/set', [CustomNamesController::class, 'setFont'])->name('fonts.set');
        });

        // Custom Colors Admin
        Route::prefix('customcolors')->name('customcolors.')->group(function () {
            Route::get('/', [CustomColorController::class, 'index'])->name('index');
            Route::get('/add', [CustomColorController::class, 'create'])->name('create');
            Route::post('/add', [CustomColorController::class, 'store'])->name('store');
            Route::get('/edit/{id}', [CustomColorController::class, 'edit'])->name('edit');
            Route::post('/edit/{id}', [CustomColorController::class, 'update'])->name('update');
            Route::get('/toggle/{id}', [CustomColorController::class, 'toggle'])->name('toggle');
        });
    });
