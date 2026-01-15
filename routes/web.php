<?php

use App\Http\Controllers\AccountController;
use App\Http\Controllers\ProfileController;
use App\Http\Controllers\ContactController;
use App\Http\Controllers\AboutController;
use App\Http\Controllers\CartController;
use App\Http\Controllers\TeamCustomizationController;
use Illuminate\Support\Facades\Route;

Route::get('/', function () {
    return view('home');
})->name('home');

Route::get('/about', [AboutController::class, 'index'])->name('about');
Route::get('/aboutdtf', [AboutController::class, 'dtf'])->name('about.dtf');
Route::get('/aboutus', [AboutController::class, 'us'])->name('about.us');

Route::get('/contact', [ContactController::class, 'index'])->name('contact');
Route::post('/contact', [ContactController::class, 'store'])->name('contact.store');

Route::get('/dashboard', function () {
    return view('dashboard');
})->middleware(['auth', 'verified'])->name('dashboard');

Route::middleware(['auth', 'customer'])->group(function () {
    Route::get('/cart', [CartController::class, 'index'])->name('cart.index');
    Route::post('/cart/preflight', [CartController::class, 'preflight'])->name('cart.preflight');
    Route::post('/cart/put/{upload_id?}', [CartController::class, 'put'])->name('cart.put');
    Route::get('/cart/status', [CartController::class, 'status'])->name('cart.status');
    Route::post('/cart/image_update/{id}', [CartController::class, 'updateImage'])->name('cart.update');
    Route::post('/cart/delete/{id}', [CartController::class, 'delete'])->name('cart.delete');
    Route::post('/cart/duplicate/{id}', [CartController::class, 'duplicate'])->name('cart.duplicate');
    Route::get('/cart/indicator', [CartController::class, 'indicator'])->name('cart.indicator');
    Route::post('/cart/render_dtfimage_card', [CartController::class, 'renderDtfImageCard'])->name('cart.render_card');
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

    Route::get('/orders', function() {
        return redirect()->route('account');
    })->name('orders.index');

    Route::get('/orders/new', [\App\Http\Controllers\OrderController::class, 'newOrder'])->name('orders.new');
    Route::get('/orders/neworder', [\App\Http\Controllers\OrderController::class, 'newOrder']); // Legacy alias
    Route::get('/orders/order/{id}', [\App\Http\Controllers\OrderController::class, 'show'])->name('orders.show');
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
