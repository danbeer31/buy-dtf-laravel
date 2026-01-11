<x-guest-layout>
    <div class="mb-4 text-sm text-gray-600">
        You must update your password before continuing.
    </div>

    @if (session('status'))
        <div class="mb-4 text-sm text-green-600">
            {{ session('status') }}
        </div>
    @endif

    <x-validation-errors class="mb-4" />

    <form method="POST" action="{{ route('password.force.update') }}">
        @csrf

        <div>
            <x-label for="current_password" value="Current Password" />
            <x-input id="current_password" class="block mt-1 w-full"
                     type="password" name="current_password" required autocomplete="current-password" />
        </div>

        <div class="mt-4">
            <x-label for="password" value="New Password" />
            <x-input id="password" class="block mt-1 w-full"
                     type="password" name="password" required autocomplete="new-password" />
        </div>

        <div class="mt-4">
            <x-label for="password_confirmation" value="Confirm New Password" />
            <x-input id="password_confirmation" class="block mt-1 w-full"
                     type="password" name="password_confirmation" required autocomplete="new-password" />
        </div>

        <div class="flex items-center justify-end mt-4">
            <x-button>
                Update Password
            </x-button>
        </div>
    </form>
</x-guest-layout>
