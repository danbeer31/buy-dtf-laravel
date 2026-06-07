<?php

namespace App\Http\Requests\Auth;

use App\Models\User;
use App\Support\LegacyFuelPassword;
use Illuminate\Auth\Events\Lockout;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;

class LoginRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return true;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, \Illuminate\Contracts\Validation\ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        return [
            'email' => ['required', 'string', 'email'],
            'password' => ['required', 'string'],
        ];
    }

    /**
     * Attempt to authenticate the request's credentials.
     *
     * @throws \Illuminate\Validation\ValidationException
     */
    public function authenticate(): void
    {
        $this->ensureIsNotRateLimited();

        $credentials = $this->only('email', 'password');
        $remember = $this->boolean('remember');

        $user = User::where('email', $credentials['email'])->first();
        if ($user) {
            $stored = (string) $user->password;
            $isLaravelHash = Str::startsWith($stored, ['$2y$', '$2a$', '$2b$', '$argon2i$', '$argon2id$']);

            // Avoid Auth::attempt on legacy hashes; BcryptHasher throws on non-bcrypt input.
            if ($isLaravelHash && Hash::check($credentials['password'], $stored)) {
                Auth::login($user, $remember);
                RateLimiter::clear($this->throttleKey());
                return;
            }

            // Legacy FuelPHP fallback: verify old PBKDF2 hash, then upgrade to Laravel hash.
            if (
                config('auth_legacy.enabled', true) &&
                ! $isLaravelHash &&
                LegacyFuelPassword::check($credentials['password'], $stored)
            ) {
                $user->password = Hash::make($credentials['password']);
                $user->save();

                Auth::login($user, $remember);
                RateLimiter::clear($this->throttleKey());
                return;
            }
        }

        RateLimiter::hit($this->throttleKey());

        throw ValidationException::withMessages([
            'email' => trans('auth.failed'),
        ]);
    }

    /**
     * Ensure the login request is not rate limited.
     *
     * @throws \Illuminate\Validation\ValidationException
     */
    public function ensureIsNotRateLimited(): void
    {
        if (! RateLimiter::tooManyAttempts($this->throttleKey(), 5)) {
            return;
        }

        event(new Lockout($this));

        $seconds = RateLimiter::availableIn($this->throttleKey());

        throw ValidationException::withMessages([
            'email' => trans('auth.throttle', [
                'seconds' => $seconds,
                'minutes' => ceil($seconds / 60),
            ]),
        ]);
    }

    /**
     * Get the rate limiting throttle key for the request.
     */
    public function throttleKey(): string
    {
        return Str::transliterate(Str::lower($this->string('email')).'|'.$this->ip());
    }
}
