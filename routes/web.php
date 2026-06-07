<?php

use App\Http\Controllers\AccountController;
use App\Http\Controllers\ProfileController;
use App\Http\Controllers\ContactController;
use App\Http\Controllers\AboutController;
use App\Http\Controllers\CartController;
use App\Http\Controllers\ImageEditorController;
use App\Http\Controllers\TeamCustomizationController;
use App\Http\Controllers\HeatpressController;
use App\Http\Controllers\FaqController;
use App\Http\Controllers\GangSheetController;
use App\Http\Controllers\ImageRequirementsController;
use App\Http\Controllers\Webhooks\ShippoWebhookController;
use Illuminate\Support\Facades\Route;

Route::post('/webhooks/shippo', [ShippoWebhookController::class, 'handle'])->name('webhooks.shippo');

Route::get('/', function () {
    return view('home');
})->name('home');

Route::get('/about', [AboutController::class, 'index'])->name('about');
Route::get('/aboutdtf', [AboutController::class, 'dtf'])->name('about.dtf');
Route::get('/aboutus', [AboutController::class, 'us'])->name('about.us');

Route::get('/heatpress', [HeatpressController::class, 'index'])->name('heatpress');
Route::get('/faq', [FaqController::class, 'index'])->name('faq');
Route::get('/imagerequirements', [ImageRequirementsController::class, 'index'])->name('imagerequirements');

Route::get('/contact', [ContactController::class, 'index'])->name('contact');
Route::post('/contact', [ContactController::class, 'store'])->name('contact.store');
Route::view('/legal/eula', 'legal.eula')->name('legal.eula');
Route::view('/legal/privacy-policy', 'legal.privacy')->name('legal.privacy');

Route::get('/dashboard', function () {
    return view('dashboard');
})->middleware(['auth', 'verified'])->name('dashboard');

Route::middleware(['auth', 'verified', 'customer'])->group(function () {
    Route::get('/test-dropbox-refresh', function() {
        if (!auth()->user()->isAdmin()) {
            abort(403);
        }
        try {
            $service = new \App\Services\DropboxService();
            $token = \App\Models\DropboxToken::first();
            if (!$token) return response()->json(['error' => 'No token record found']);
            $service->refreshTokens($token);
            return response()->json(['success' => true, 'token_id' => $token->id, 'updated_at' => $token->updated_at]);
        } catch (\Exception $e) {
            return response()->json(['error' => $e->getMessage(), 'trace' => $e->getTraceAsString()], 500);
        }
    });

    Route::get('/test-dropbox-upload', function() {
        if (!auth()->user()->isAdmin()) {
            abort(403);
        }
        try {
            $service = new \App\Services\DropboxService();
            $tempFile = tempnam(sys_get_temp_dir(), 'dbtest');
            file_put_contents($tempFile, 'Dropbox test upload at ' . date('Y-m-d H:i:s'));
            $remotePath = '/test_upload_' . time() . '.txt';
            $result = $service->upload($tempFile, $remotePath);
            unlink($tempFile);
            return response()->json(['success' => true, 'remote_path' => $result]);
        } catch (\Exception $e) {
            return response()->json([
                'error' => $e->getMessage(),
                'class' => get_class($e),
                'trace' => $e->getTraceAsString()
            ], 500);
        }
    });

    Route::get('/cart', [CartController::class, 'index'])->name('cart.index');
    Route::get('/gang-sheet-uploader', [GangSheetController::class, 'index'])->name('gang-sheet.index');
    Route::post('/gang-sheet-uploader', [GangSheetController::class, 'store'])->name('gang-sheet.store');
    Route::post('/cart/preflight', [CartController::class, 'preflight'])->name('cart.preflight');
    Route::post('/cart/put/{upload_id?}', [CartController::class, 'put'])->name('cart.put');
    Route::get('/cart/status', [CartController::class, 'status'])->name('cart.status');
    Route::post('/cart/image_update/{id}', [CartController::class, 'updateImage'])->name('cart.update');
    Route::post('/cart/delete/{id}', [CartController::class, 'delete'])->name('cart.delete');
    Route::post('/cart/duplicate/{id}', [CartController::class, 'duplicate'])->name('cart.duplicate');
    Route::get('/cart/indicator', [CartController::class, 'indicator'])->name('cart.indicator');
    Route::post('/cart/render_dtfimage_card', [CartController::class, 'renderDtfImageCard'])->name('cart.render_card');

    Route::get('/cart/editor/{image}', [ImageEditorController::class, 'edit'])->name('cart.editor');
    Route::post('/cart/editor/{image}/process', [ImageEditorController::class, 'process'])->name('cart.editor.process');

    Route::prefix('checkout')->name('checkout.')->group(function () {
        Route::get('/', [\App\Http\Controllers\Checkout\CheckoutController::class, 'index'])->name('index');
        Route::post('/shipping-address', [\App\Http\Controllers\Checkout\CheckoutController::class, 'updateShippingAddress'])->name('shipping-address.update');
        Route::post('/payment', [\App\Http\Controllers\Checkout\CheckoutController::class, 'startPayment'])->name('payment');
        Route::get('/invoice/disclaimer/{order}', [\App\Http\Controllers\Checkout\CheckoutController::class, 'invoiceDisclaimer'])->name('invoice.disclaimer');
        Route::post('/invoice/complete/{order}', [\App\Http\Controllers\Checkout\CheckoutController::class, 'completeInvoiceOrder'])->name('invoice.complete');
        Route::get('/complete', [\App\Http\Controllers\Checkout\CheckoutController::class, 'complete'])->name('complete');
    });

    Route::get('/qbo/pay', function () {
        return redirect()->route('account')->with('error', 'Please start invoice payment from your account invoice list.');
    });
    Route::post('/qbo/pay', [\App\Http\Controllers\Checkout\CheckoutController::class, 'payQboInvoices'])->name('qbo.pay');
    Route::get('/qbo/pay/complete', [\App\Http\Controllers\Checkout\CheckoutController::class, 'completeQboPayment'])->name('qbo.pay.complete');

    Route::post('/cart/dupe_check', [CartController::class, 'dupeCheck'])->name('cart.dupe_check');
    Route::post('/cart/dupe_check_hash', [CartController::class, 'dupeCheckHash'])->name('cart.dupe_check_hash');
    Route::post('/cart/use_existing', [CartController::class, 'useExisting'])->name('cart.use_existing');
    Route::post('/cart/save/{id}', [CartController::class, 'saveImage'])->name('cart.save');
    Route::get('/cart/my_images', [CartController::class, 'myImages'])->name('cart.my_images');
    Route::get('/cart/quick_search', [CartController::class, 'myImages'])->name('cart.quick_search');
    Route::post('/cart/use_saved', [CartController::class, 'useSaved'])->name('cart.use_saved');

    Route::get('/debug-user', function() {
        $user = auth()->user();
        return response()->json([
            'id' => $user->id,
            'name' => $user->name,
            'email' => $user->email,
            'role' => $user->role,
            'attributes' => $user->getAttributes(),
        ]);
    });

    Route::get('/account', [AccountController::class, 'index'])->name('account');
    Route::get('/account/orders', [AccountController::class, 'orders'])->name('account.orders');
    Route::get('/account/orders/{order}', [AccountController::class, 'showOrder'])->name('account.orders.show');
    Route::get('/account/invoices', [AccountController::class, 'invoices'])->name('account.invoices');
    Route::get('/account/images', [AccountController::class, 'images'])->name('account.images');
    Route::get('/account/images/{image}/download', [AccountController::class, 'downloadImage'])->name('account.images.download');

    Route::get('/orders', function() {
        return redirect()->route('account');
    })->name('orders.index');

    Route::get('/orders/new', [\App\Http\Controllers\OrderController::class, 'newOrder'])->name('orders.new');
    Route::get('/orders/neworder', [\App\Http\Controllers\OrderController::class, 'newOrder']); // Legacy alias
    Route::get('/orders/order/{id}', function() {
        return redirect()->route('cart.index');
    })->name('orders.show');
    Route::get('/orders/place/{id}', [\App\Http\Controllers\OrderController::class, 'placeOrder'])->name('orders.place');

    Route::get('/profile', [ProfileController::class, 'edit'])->name('profile.edit');
    Route::patch('/profile', [ProfileController::class, 'update'])->name('profile.update');
    Route::delete('/profile', [ProfileController::class, 'destroy'])->name('profile.destroy');

    // Team Customization
    Route::prefix('teamcustomization')->name('teamcustomization.')->group(function () {
        Route::get('/', [TeamCustomizationController::class, 'index'])->name('index');
        Route::get('/fonts', [TeamCustomizationController::class, 'getFonts'])->name('fonts');
        Route::post('/preview', [TeamCustomizationController::class, 'preview'])->name('preview');
        Route::post('/validate_csv', [TeamCustomizationController::class, 'validateCsv'])->name('validate_csv');
        Route::post('/run_one', [TeamCustomizationController::class, 'runOne'])->name('run_one');
        Route::get('/progress', [TeamCustomizationController::class, 'getProgress'])->name('progress');
        Route::get('/templates', [TeamCustomizationController::class, 'getTemplates'])->name('templates');
        Route::get('/template/{id?}', [TeamCustomizationController::class, 'getTemplate'])->name('template');
        Route::get('/colors', [TeamCustomizationController::class, 'getColors'])->name('colors');
    });
});

require __DIR__.'/auth.php';
