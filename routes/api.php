<?php

use App\Http\Controllers\Api\IncomingOrderController;
use App\Http\Controllers\Webhook\StripeWebhookController;
use Illuminate\Support\Facades\Route;

Route::post('/incomingorder', [IncomingOrderController::class, 'store']);
Route::post('/stripe/webhook', [StripeWebhookController::class, 'handle']);
