<x-guest-layout>
    <div class="text-center mb-4">
        <div class="d-inline-flex align-items-center justify-content-center bg-warning bg-opacity-10 rounded-circle p-3 mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="#f7941d" class="bi bi-shield-lock" viewBox="0 0 16 16">
                <path d="M5.338 1.59a6.1 6.1 0 0 0-2.837.856.5.5 0 0 0 .23.874A4.81 4.81 0 0 1 7 3.5c.379 0 .75.043 1.107.126a.5.5 0 0 0 .214-.977 6.11 6.11 0 0 0-2.983-.06Zm3.352 1.141a.5.5 0 0 0-.214.977 4.81 4.81 0 0 1 2.508 1.91.5.5 0 1 0 .822-.572 6.11 6.11 0 0 0-3.116-2.315Zm3.71 3.71a.5.5 0 1 0-.572.822 4.81 4.81 0 0 1 1.91 2.508.5.5 0 0 0 .977-.214 6.11 6.11 0 0 0-2.315-3.116Zm1.141 3.352a.5.5 0 0 0-.977.214 4.81 4.81 0 0 1-.126 1.107.5.5 0 0 0 .977.214 6.11 6.11 0 0 0 .126-1.535Zm-1.141 3.352a.5.5 0 1 0 .572-.822 4.81 4.81 0 0 1-2.508-1.91.5.5 0 1 0-.822.572 6.11 6.11 0 0 0 3.116 2.315Zm-3.352 1.141a.5.5 0 0 0 .214-.977 4.81 4.81 0 0 1-1.107-.126.5.5 0 0 0-.214.977 6.11 6.11 0 0 0 1.535.126Zm-3.352-1.141a.5.5 0 0 0 .214-.977 4.81 4.81 0 0 1-1.91-2.508.5.5 0 1 0-.822.572 6.11 6.11 0 0 0 2.315 3.116Zm-1.141-3.352a.5.5 0 0 0 .977-.214 4.81 4.81 0 0 1 .126-1.107.5.5 0 0 0-.977-.214 6.11 6.11 0 0 0-.126 1.535Zm1.141-3.352a.5.5 0 1 0-.572.822 4.81 4.81 0 0 1 2.508 1.91.5.5 0 1 0 .822-.572 6.11 6.11 0 0 0-3.116-2.315ZM8 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z"/>
            </svg>
        </div>
        <h2 class="h4 fw-bold text-dark">{{ __('Reset Password') }}</h2>
        <p class="text-muted small">{{ __('We will email you a password reset link') }}</p>
    </div>

    @if (session('status'))
        <x-auth-session-status class="mb-4 text-center" :status="session('status')" />
    @endif

    <form method="POST" action="{{ route('password.email') }}" class="d-grid gap-3">
        @csrf

        <!-- Email Address -->
        <div>
            <x-input-label for="email" :value="__('Email Address')" />
            <x-text-input id="email" class="mt-1" type="email" name="email" :value="old('email')" required autofocus />
            <x-input-error :messages="$errors->get('email')" class="mt-2" />
        </div>

        <div class="d-grid gap-3 mt-2">
            <x-primary-button class="py-2">
                {{ __('Send Reset Link') }}
            </x-primary-button>

            <div class="text-center">
                <a class="small text-secondary text-decoration-none hover-underline" href="{{ route('login') }}">
                    {{ __('Back to Log In') }}
                </a>
            </div>
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
