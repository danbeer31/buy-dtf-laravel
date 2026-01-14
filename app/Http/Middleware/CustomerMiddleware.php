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
            return $next($request);
        }

        // Allow customers and admins
        if ($user->role !== 'customer' && $user->role !== 'admin') {
            return redirect()->route('home')->with('error', 'Access denied.');
        }

        return $next($request);
    }
}
