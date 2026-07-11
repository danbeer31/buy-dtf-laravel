<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class CustomerMiddleware
{
    public function handle(Request $request, Closure $next)
    {
        $user = $request->user();
        if (! $user) {
            \Illuminate\Support\Facades\Log::info('CustomerMiddleware: No user found.');
            return $next($request);
        }

        \Illuminate\Support\Facades\Log::info('CustomerMiddleware: User role is ' . $user->role, [
            'user_id' => $user->id,
            'email' => $user->email
        ]);

        // Allow customers and all admin roles.
        if ($user->role !== 'customer' && ! $user->isAdmin()) {
            \Illuminate\Support\Facades\Log::info('CustomerMiddleware: Redirecting to home because role is not customer or admin.');
            return redirect()->route('home')->with('error', 'Access denied.');
        }

        return $next($request);
    }
}
