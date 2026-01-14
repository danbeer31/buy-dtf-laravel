<x-guest-layout>
    <div class="mb-4 small text-muted">
        {{ __('You must update your password before continuing.') }}
    </div>

    <x-auth-session-status class="mb-4" :status="session('status')" />

    <form method="POST" action="{{ route('password.force.update') }}" class="d-grid gap-3">
        @csrf

        <div>
            <x-input-label for="current_password" value="Current Password" />
            <x-text-input id="current_password" class="mt-1"
                     type="password" name="current_password" required autocomplete="current-password" />
            <x-input-error :messages="$errors->get('current_password')" class="mt-2" />
        </div>

        <div>
            <x-input-label for="password" value="New Password" />
            <x-text-input id="password" class="mt-1"
                     type="password" name="password" required autocomplete="new-password" />
            <x-input-error :messages="$errors->get('password')" class="mt-2" />
        </div>

        <div>
            <x-input-label for="password_confirmation" value="Confirm New Password" />
            <x-text-input id="password_confirmation" class="mt-1"
                     type="password" name="password_confirmation" required autocomplete="new-password" />
            <x-input-error :messages="$errors->get('password_confirmation')" class="mt-2" />
        </div>

        <div class="d-grid mt-2">
            <x-primary-button>
                {{ __('Update Password') }}
            </x-primary-button>
        </div>
    </form>
</x-guest-layout>
