<?php

use Illuminate\Support\Facades\Route;

Route::view('/', 'welcome')->name('home');

// Optional: dashboard (requires login)
Route::view('/dashboard', 'dashboard')
    ->middleware(['auth'])
    ->name('dashboard');

// Breeze auth routes (login, logout, forgot-password, etc.)
require __DIR__.'/auth.php';
