<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class AdminMiddleware
{
    public function handle(Request $request, Closure $next)
    {
        // Not logged in? Let 'auth' middleware handle redirect to login.
        $user = $request->user();
        if (! $user) {
            return $next($request);
        }

        // Allow admins only
        if ($user->role === 'admin' || $user->role === 'superadmin') {
            return $next($request);
        }

        return redirect()->route('home')->with('error', 'Admin access required.');
    }
}
