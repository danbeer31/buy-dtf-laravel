<?php

namespace App\Http\Controllers\Auth;

use App\Http\Controllers\Controller;
use App\Models\User;
use App\Models\Business;
use App\Models\BusinessSetting;
use Illuminate\Auth\Events\Registered;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Hash;
use Illuminate\Validation\Rules;
use Illuminate\View\View;
use Illuminate\Support\Facades\DB;

class RegisteredUserController extends Controller
{
    /**
     * Display the registration view.
     */
    public function create(): View
    {
        return view('auth.register');
    }

    /**
     * Handle an incoming registration request.
     *
     * @throws \Illuminate\Validation\ValidationException
     */
    public function store(Request $request): RedirectResponse
    {
        $request->validate([
            'business_name' => ['required', 'string', 'max:255'],
            'name' => ['required', 'string', 'max:255'],
            'email' => ['required', 'string', 'lowercase', 'email', 'max:255', 'unique:'.User::class, 'unique:'.Business::class],
            'phone' => ['required', 'string', 'max:20'],
            'address' => ['required', 'string', 'max:255'],
            'city' => ['required', 'string', 'max:255'],
            'state' => ['required', 'string', 'size:2'],
            'zip' => ['required', 'string', 'max:10'],
            'password' => ['required', 'confirmed', Rules\Password::defaults()],
        ]);

        return DB::transaction(function () use ($request) {
            $user = User::create([
                'name' => $request->name,
                'email' => $request->email,
                'password' => Hash::make($request->password),
            ]);

            $business = Business::create([
                'user_id' => $user->id,
                'business_name' => $request->business_name,
                'contact_name' => $request->name,
                'email' => $request->email,
                'phone' => $request->phone,
                'address' => $request->address,
                'address2' => $request->address2,
                'city' => $request->city,
                'state' => $request->state,
                'zip' => $request->zip,
                'status' => 'unconfirmed',
            ]);

            BusinessSetting::create([
                'business_id' => $business->id,
                'rate' => 0.0300,
            ]);

            event(new Registered($user));

            Auth::login($user);

            return redirect(route('dashboard', absolute: false));
        });
    }
}
