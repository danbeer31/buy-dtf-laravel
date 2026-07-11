<x-guest-layout>
    <div class="text-center mb-4">
        <div class="d-inline-flex align-items-center justify-content-center bg-warning bg-opacity-10 rounded-circle p-3 mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="#f7941d" class="bi bi-person-plus" viewBox="0 0 16 16">
                <path d="M1 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1H1zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/>
                <path fill-rule="evenodd" d="M13.5 5a.5.5 0 0 1 .5.5V7h1.5a.5.5 0 0 1 0 1H14v1.5a.5.5 0 0 1-1 0V8h-1.5a.5.5 0 0 1 0-1H13V5.5a.5.5 0 0 1 .5-.5z"/>
            </svg>
        </div>
        <h2 class="h4 fw-bold text-dark">{{ __('Create Your Account') }}</h2>
        <p class="text-muted small">{{ __('Join us to start your DTF journey') }}</p>
    </div>

    <form method="POST" action="{{ route('register') }}" class="d-grid gap-4">
        @csrf

        <!-- Section: Business Information -->
        <div class="form-section">
            <h3 class="h6 fw-bold text-uppercase text-secondary mb-3 pb-2 border-bottom small tracking-wider">{{ __('Business Details') }}</h3>

            <div class="mb-3">
                <x-input-label for="business_name" :value="__('Business Name')" />
                <x-text-input id="business_name" class="mt-1" type="text" name="business_name" :value="old('business_name')" required autofocus autocomplete="business_name" />
                <x-input-error :messages="$errors->get('business_name')" class="mt-2" />
            </div>

            <div class="mb-0">
                <x-input-label for="phone" :value="__('Phone Number')" />
                <x-text-input id="phone" class="mt-1" type="text" name="phone" :value="old('phone')" required autocomplete="tel" />
                <x-input-error :messages="$errors->get('phone')" class="mt-2" />
            </div>
        </div>

        <!-- Section: Contact Information -->
        <div class="form-section">
            <h3 class="h6 fw-bold text-uppercase text-secondary mb-3 pb-2 border-bottom small tracking-wider">{{ __('Contact Person') }}</h3>

            <div class="mb-3">
                <x-input-label for="name" :value="__('Contact Name')" />
                <x-text-input id="name" class="mt-1" type="text" name="name" :value="old('name')" required autocomplete="name" />
                <x-input-error :messages="$errors->get('name')" class="mt-2" />
            </div>

            <div class="mb-0">
                <x-input-label for="email" :value="__('Email Address')" />
                <x-text-input id="email" class="mt-1" type="email" name="email" :value="old('email')" required autocomplete="username" />
                <x-input-error :messages="$errors->get('email')" class="mt-2" />
            </div>
        </div>

        <!-- Section: Address -->
        <div class="form-section">
            <h3 class="h6 fw-bold text-uppercase text-secondary mb-3 pb-2 border-bottom small tracking-wider">{{ __('Shipping Address') }}</h3>

            <div class="mb-3">
                <x-input-label for="address" :value="__('Address Line 1')" />
                <x-text-input id="address" class="mt-1" type="text" name="address" :value="old('address')" required autocomplete="address-line1" />
                <x-input-error :messages="$errors->get('address')" class="mt-2" />
            </div>

            <div class="mb-3">
                <x-input-label for="address2" :value="__('Address Line 2 (Optional)')" />
                <x-text-input id="address2" class="mt-1" type="text" name="address2" :value="old('address2')" autocomplete="address-line2" />
                <x-input-error :messages="$errors->get('address2')" class="mt-2" />
            </div>

            <div class="row g-3">
                <div class="col-12 col-md-6">
                    <x-input-label for="city" :value="__('City')" />
                    <x-text-input id="city" class="mt-1" type="text" name="city" :value="old('city')" required autocomplete="address-level2" />
                    <x-input-error :messages="$errors->get('city')" class="mt-2" />
                </div>

                <div class="col-6 col-md-3">
                    <x-input-label for="state" :value="__('State')" />
                    <x-text-input id="state" class="mt-1" type="text" name="state" :value="old('state')" required autocomplete="address-level1" maxlength="2" />
                    <x-input-error :messages="$errors->get('state')" class="mt-2" />
                </div>

                <div class="col-6 col-md-3">
                    <x-input-label for="zip" :value="__('Zip')" />
                    <x-text-input id="zip" class="mt-1" type="text" name="zip" :value="old('zip')" required autocomplete="postal-code" />
                    <x-input-error :messages="$errors->get('zip')" class="mt-2" />
                </div>
            </div>
        </div>

        <!-- Section: Security -->
        <div class="form-section">
            <h3 class="h6 fw-bold text-uppercase text-secondary mb-3 pb-2 border-bottom small tracking-wider">{{ __('Security') }}</h3>

            <div class="mb-3">
                <x-input-label for="password" :value="__('Password')" />
                <x-text-input id="password" class="mt-1" type="password" name="password" required autocomplete="new-password" />
                <x-input-error :messages="$errors->get('password')" class="mt-2" />
            </div>

            <div class="mb-0">
                <x-input-label for="password_confirmation" :value="__('Confirm Password')" />
                <x-text-input id="password_confirmation" class="mt-1" type="password" name="password_confirmation" required autocomplete="new-password" />
                <x-input-error :messages="$errors->get('password_confirmation')" class="mt-2" />
            </div>
        </div>

        <div class="d-grid gap-3 pt-2">
            <x-primary-button class="py-2">
                {{ __('Create Account') }}
            </x-primary-button>

            <div class="text-center">
                <a class="small text-secondary text-decoration-none hover-underline" href="{{ route('login') }}">
                    {{ __('Already have an account? Log in') }}
                </a>
            </div>
        </div>
    </form>

    @push('styles')
    <style>
        .hover-underline:hover {
            text-decoration: underline !important;
        }
        .tracking-wider {
            letter-spacing: 0.05em;
        }
    </style>
    @endpush
</x-guest-layout>
