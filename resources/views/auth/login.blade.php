<x-guest-layout>
    <div class="text-center mb-4">
        <div class="d-inline-flex align-items-center justify-content-center bg-warning bg-opacity-10 rounded-circle p-3 mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="#f7941d" class="bi bi-box-arrow-in-right" viewBox="0 0 16 16">
                <path fill-rule="evenodd" d="M6 3.5a.5.5 0 0 1 .5-.5h8a.5.5 0 0 1 .5.5v9a.5.5 0 0 1-.5.5h-8a.5.5 0 0 1-.5-.5v-2a.5.5 0 0 0-1 0v2A1.5 1.5 0 0 0 6.5 14h8a1.5 1.5 0 0 0 1.5-1.5v-9A1.5 1.5 0 0 0 14.5 2h-8A1.5 1.5 0 0 0 5 3.5v2a.5.5 0 0 0 1 0v-2z"/>
                <path fill-rule="evenodd" d="M11.854 8.354a.5.5 0 0 0 0-.708l-3-3a.5.5 0 1 0-.708.708L10.293 7.5H1.5a.5.5 0 0 0 0 1h8.793l-2.147 2.146a.5.5 0 0 0 .708.708l3-3z"/>
            </svg>
        </div>
        <h2 class="h4 fw-bold text-dark">{{ __('Welcome Back') }}</h2>
        <p class="text-muted small">{{ __('Log in to manage your DTF orders') }}</p>
    </div>

    <!-- Session Status -->
    <x-auth-session-status class="mb-4 text-center" :status="session('status')" />

    <form method="POST" action="{{ route('login') }}" class="d-grid gap-3">
        @csrf

        <!-- Email Address -->
        <div>
            <x-input-label for="email" :value="__('Email')" />
            <x-text-input id="email" class="mt-1" type="email" name="email" :value="old('email')" required autofocus autocomplete="username" />
            <x-input-error :messages="$errors->get('email')" class="mt-2" />
        </div>

        <!-- Password -->
        <div class="mb-1">
            <div class="d-flex justify-content-between align-items-center">
                <x-input-label for="password" :value="__('Password')" />
                @if (Route::has('password.request'))
                    <a class="small text-secondary text-decoration-none hover-underline" href="{{ route('password.request') }}">
                        {{ __('Forgot password?') }}
                    </a>
                @endif
            </div>

            <x-text-input id="password" class="mt-1"
                            type="password"
                            name="password"
                            required autocomplete="current-password" />

            <x-input-error :messages="$errors->get('password')" class="mt-2" />
        </div>

        <!-- Remember Me -->
        <div class="form-check mb-2">
            <input id="remember_me" type="checkbox" class="form-check-input shadow-sm" name="remember">
            <label for="remember_me" class="form-check-label small text-muted">
                {{ __('Keep me logged in') }}
            </label>
        </div>

        <div class="d-grid gap-3">
            <x-primary-button class="py-2">
                {{ __('Log In') }}
            </x-primary-button>

            @if (Route::has('register'))
                <div class="text-center">
                    <span class="small text-muted">{{ __("Don't have an account?") }}</span>
                    <a class="small text-warning fw-bold text-decoration-none hover-underline ms-1" href="{{ route('register') }}">
                        {{ __('Sign Up') }}
                    </a>
                </div>
            @endif
        </div>
    </form>

    @push('styles')
    <style>
        .hover-underline:hover {
            text-decoration: underline !important;
        }
    </style>
    @endpush
</x-guest-layout>
