<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class ForcePasswordReset
{
    public function handle(Request $request, Closure $next)
    {
        if (auth()->check() && auth()->user()->password_reset_required) {

            // allow force-reset page + logout while flagged
            if ($request->routeIs('password.force*') || $request->is('logout')) {
                return $next($request);
            }

            return redirect()->route('password.force');
        }

        return $next($request);
    }
}
