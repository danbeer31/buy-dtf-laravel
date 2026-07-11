<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\Admin\BusinessController;
use App\Http\Controllers\Admin\CustomNamesController;
use App\Http\Controllers\Admin\CustomColorController;
use App\Http\Controllers\Admin\UserController;
use App\Http\Controllers\Admin\ShippingSettingsController;
use App\Http\Controllers\Admin\ShippingController;
use App\Http\Controllers\Admin\OrderController;
use App\Http\Controllers\Admin\OrderImageController;
use App\Http\Controllers\Admin\DropboxController;
use App\Http\Controllers\Admin\StripePaymentController;
use App\Http\Controllers\Admin\DashboardController;
use App\Http\Controllers\Admin\ReconciliationController;

Route::middleware(['auth', 'admin'])
    ->prefix('admin')
    ->name('admin.')
    ->group(function () {
        Route::get('/', [DashboardController::class, 'index'])->name('dashboard');

        Route::get('/dropbox/status', [DropboxController::class, 'status'])->name('dropbox.status');
        Route::get('/dropbox/connect', [DropboxController::class, 'connect'])->name('dropbox.connect');
        Route::get('/dropbox/callback', [DropboxController::class, 'callback'])->name('dropbox.callback');
        Route::get('/dropbox/refresh', [DropboxController::class, 'refresh'])->name('dropbox.refresh');

        Route::get('/shipping', [ShippingSettingsController::class, 'index'])->name('shipping.index');
        Route::post('/shipping', [ShippingSettingsController::class, 'update'])->name('shipping.update');

        Route::get('/orders/{order}/shipping', [ShippingController::class, 'orderShipping'])->name('orders.shipping');
        Route::get('/orders/{order}/shipping/rates', [ShippingController::class, 'getRates'])->name('orders.shipping.rates');
        Route::post('/orders/{order}/shipping/label', [ShippingController::class, 'createLabel'])->name('orders.shipping.label');
        Route::post('/orders/{order}/ready-for-pickup', [ShippingController::class, 'readyForPickup'])->name('orders.ready-for-pickup');
        Route::post('/orders/{order}/mark-picked-up', [ShippingController::class, 'markAsPickedUp'])->name('orders.mark-picked-up');

        Route::get('/orders', [OrderController::class, 'index'])->name('orders.index');
        Route::get('/orders/production', [OrderController::class, 'production'])->name('orders.production');
        Route::get('/orders/production/{order}', [OrderController::class, 'productionOrder'])->name('orders.production-order');
        Route::post('/orders/update-status', [OrderController::class, 'updateStatus'])->name('orders.update-status');
        Route::post('/orders/create-qbo-invoice', [OrderController::class, 'createQboInvoice'])->name('orders.create-qbo-invoice');
        Route::post('/orders/add-to-production', [OrderController::class, 'addToProduction'])->name('orders.add-to-production');
        Route::post('/orders/{order}/pricing/discount', [OrderController::class, 'applyOrderDiscount'])->name('orders.pricing.discount');
        Route::post('/orders/{order}/pricing/clear', [OrderController::class, 'clearPricingLocks'])->name('orders.pricing.clear');
        Route::post('/orders/{order}/images/{image}/pricing', [OrderController::class, 'updateLinePricing'])->name('orders.images.pricing.update');
        Route::post('/orders/{order}/images/{image}/pricing/clear', [OrderController::class, 'clearLinePricing'])->name('orders.images.pricing.clear');
        Route::get('/orders/{order}', [OrderController::class, 'show'])->name('orders.show');

        // Stripe Payments
        Route::get('/payments/stripe', [StripePaymentController::class, 'index'])->name('payments.stripe');
        Route::get('/payments/stripe/payouts', [\App\Http\Controllers\Admin\StripePayoutController::class, 'index'])->name('payments.stripe.payouts');
        Route::get('/payments/stripe/sync-logs', [\App\Http\Controllers\Admin\StripeSyncLogController::class, 'index'])->name('payments.stripe.sync-logs');
        Route::get('/payments/stripe/sync-logs/{log}', [\App\Http\Controllers\Admin\StripeSyncLogController::class, 'show'])->name('payments.stripe.sync-logs.show');
        Route::get('/payments/stripe/payouts/{payout}', [\App\Http\Controllers\Admin\StripePayoutController::class, 'show'])->name('payments.stripe.payouts.show');
        Route::post('/payments/stripe/payouts/sync', [\App\Http\Controllers\Admin\StripePayoutController::class, 'sync'])->name('payments.stripe.payouts.sync');
        Route::get('/payments/stripe/{payment}', [StripePaymentController::class, 'show'])->name('payments.stripe.show');
        Route::post('/payments/stripe/{payment}/refresh-fee', [StripePaymentController::class, 'refreshFee'])->name('payments.stripe.refresh-fee');
        Route::get('/payments/reconciliation', [ReconciliationController::class, 'index'])->name('payments.reconciliation.index');
        Route::get('/payments/reconciliation/{check}', [ReconciliationController::class, 'show'])->name('payments.reconciliation.show');
        Route::post('/payments/reconciliation/rerun', [ReconciliationController::class, 'rerun'])->name('payments.reconciliation.rerun');

        // QuickBooks Settings
        Route::prefix('qbo')->name('qbo.')->group(function () {
            Route::get('/', [\App\Http\Controllers\Admin\QboSettingsController::class, 'index'])->name('index');
            Route::post('/settings', [\App\Http\Controllers\Admin\QboSettingsController::class, 'updateSettings'])->name('settings.update');
            Route::get('/connect', [\App\Http\Controllers\Admin\QboSettingsController::class, 'connect'])->name('connect');
            Route::get('/callback', [\App\Http\Controllers\Admin\QboSettingsController::class, 'callback'])->name('callback');
            Route::post('/disconnect', [\App\Http\Controllers\Admin\QboSettingsController::class, 'disconnect'])->name('disconnect');
            Route::get('/items', [\App\Http\Controllers\Admin\QboSettingsController::class, 'getItems'])->name('items');
            Route::get('/accounts', [\App\Http\Controllers\Admin\QboSettingsController::class, 'getAccounts'])->name('accounts');
            Route::get('/terms', [\App\Http\Controllers\Admin\QboSettingsController::class, 'getSalesTerms'])->name('terms');
            Route::post('/reset-mappings', [\App\Http\Controllers\Admin\QboSettingsController::class, 'resetMappings'])->name('reset-mappings');
            Route::get('/download-items', [\App\Http\Controllers\Admin\QboSettingsController::class, 'downloadItems'])->name('download-items');
            Route::get('/download-accounts', [\App\Http\Controllers\Admin\QboSettingsController::class, 'downloadAccounts'])->name('download-accounts');
        });

        // Order Image Editing
        Route::prefix('orders/images')->name('orders.images.')->group(function () {
            Route::get('/{image}/edit', [OrderImageController::class, 'edit'])->name('edit');
            Route::post('/{image}/update', [OrderImageController::class, 'update'])->name('update');
            Route::post('/{image}/replace', [OrderImageController::class, 'replace'])->name('replace');
            Route::post('/{image}/alpha', [OrderImageController::class, 'alpha'])->name('alpha');
            Route::get('/{image}/download', [OrderImageController::class, 'download'])->name('download');
            Route::get('/{image}/compare', [OrderImageController::class, 'compare'])->name('compare');
        });

        Route::get('/businesses', [BusinessController::class, 'index'])->name('businesses.index');
        Route::get('/businesses/{business}', [BusinessController::class, 'show'])->name('businesses.show');
        Route::patch('/businesses/{business}/payment-methods', [BusinessController::class, 'updatePaymentMethods'])->name('businesses.update-payment-methods');
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
            Route::post('/template/save-preview', [CustomNamesController::class, 'savePreview'])->name('template.save-preview');

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
