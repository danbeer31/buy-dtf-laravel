<x-guest-layout>
    <form method="POST" action="{{ route('register') }}" class="d-grid gap-3">
        @csrf

        <!-- Business Name -->
        <div>
            <x-input-label for="business_name" :value="__('Business Name')" />
            <x-text-input id="business_name" class="mt-1" type="text" name="business_name" :value="old('business_name')" required autofocus autocomplete="business_name" />
            <x-input-error :messages="$errors->get('business_name')" class="mt-2" />
        </div>

        <!-- Contact Name -->
        <div>
            <x-input-label for="name" :value="__('Contact Name')" />
            <x-text-input id="name" class="mt-1" type="text" name="name" :value="old('name')" required autocomplete="name" />
            <x-input-error :messages="$errors->get('name')" class="mt-2" />
        </div>

        <!-- Email Address -->
        <div>
            <x-input-label for="email" :value="__('Email')" />
            <x-text-input id="email" class="mt-1" type="email" name="email" :value="old('email')" required autocomplete="username" />
            <x-input-error :messages="$errors->get('email')" class="mt-2" />
        </div>

        <!-- Phone -->
        <div>
            <x-input-label for="phone" :value="__('Phone')" />
            <x-text-input id="phone" class="mt-1" type="text" name="phone" :value="old('phone')" required autocomplete="tel" />
            <x-input-error :messages="$errors->get('phone')" class="mt-2" />
        </div>

        <!-- Address -->
        <div>
            <x-input-label for="address" :value="__('Address')" />
            <x-text-input id="address" class="mt-1" type="text" name="address" :value="old('address')" required autocomplete="address-line1" />
            <x-input-error :messages="$errors->get('address')" class="mt-2" />
        </div>

        <!-- Address 2 -->
        <div>
            <x-input-label for="address2" :value="__('Address 2 (Optional)')" />
            <x-text-input id="address2" class="mt-1" type="text" name="address2" :value="old('address2')" autocomplete="address-line2" />
            <x-input-error :messages="$errors->get('address2')" class="mt-2" />
        </div>

        <div class="row g-3">
            <!-- City -->
            <div class="col-6 col-md-4">
                <x-input-label for="city" :value="__('City')" />
                <x-text-input id="city" class="mt-1" type="text" name="city" :value="old('city')" required autocomplete="address-level2" />
                <x-input-error :messages="$errors->get('city')" class="mt-2" />
            </div>

            <!-- State -->
            <div class="col-3 col-md-4">
                <x-input-label for="state" :value="__('State')" />
                <x-text-input id="state" class="mt-1" type="text" name="state" :value="old('state')" required autocomplete="address-level1" maxlength="2" />
                <x-input-error :messages="$errors->get('state')" class="mt-2" />
            </div>

            <!-- Zip -->
            <div class="col-3 col-md-4">
                <x-input-label for="zip" :value="__('Zip')" />
                <x-text-input id="zip" class="mt-1" type="text" name="zip" :value="old('zip')" required autocomplete="postal-code" />
                <x-input-error :messages="$errors->get('zip')" class="mt-2" />
            </div>
        </div>

        <!-- Password -->
        <div>
            <x-input-label for="password" :value="__('Password')" />
            <x-text-input id="password" class="mt-1" type="password" name="password" required autocomplete="new-password" />
            <x-input-error :messages="$errors->get('password')" class="mt-2" />
        </div>

        <!-- Confirm Password -->
        <div>
            <x-input-label for="password_confirmation" :value="__('Confirm Password')" />
            <x-text-input id="password_confirmation" class="mt-1" type="password" name="password_confirmation" required autocomplete="new-password" />
            <x-input-error :messages="$errors->get('password_confirmation')" class="mt-2" />
        </div>

        <div class="d-flex align-items-center justify-content-between mt-2">
            <a class="small text-secondary text-decoration-underline" href="{{ route('login') }}">
                {{ __('Already registered?') }}
            </a>

            <x-primary-button>
                {{ __('Register') }}
            </x-primary-button>
        </div>
    </form>
</x-guest-layout>
