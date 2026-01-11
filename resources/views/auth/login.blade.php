<x-guest-layout>
    <div class="min-h-[100svh] bg-gradient-to-br from-slate-50 via-white to-slate-100">

        <div class="mx-auto flex min-h-[100svh] items-center justify-center px-4 py-10">
            <div class="w-full max-w-md">
                <div class="mb-6 text-center">
                    <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-sm">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                  d="M12 6V4m0 2a4 4 0 00-4 4v6a4 4 0 004 4m0-14a4 4 0 014 4v6a4 4 0 01-4 4m0 0v2m0-2H8m4 0h4"/>
                        </svg>
                    </div>

                    <h1 class="text-2xl font-semibold tracking-tight text-slate-900">Sign in</h1>
                    <p class="mt-1 text-sm text-slate-600">
                        Access your account and manage your orders.
                    </p>
                </div>

                <div class="rounded-2xl border border-slate-200 bg-white/90 p-6 shadow-lg shadow-slate-900/5 backdrop-blur sm:p-8">
                    <x-auth-session-status class="mb-4" :status="session('status')" />

                    <form method="POST" action="{{ route('login') }}" class="space-y-5">
                        @csrf

                        <div>
                            <x-input-label for="email" :value="__('Email')" />
                            <x-text-input
                                id="email"
                                class="mt-1 block w-full rounded-xl border-slate-300 bg-white px-3 py-2 shadow-sm focus:border-slate-900 focus:ring-slate-900"
                                type="email"
                                name="email"
                                :value="old('email')"
                                required
                                autofocus
                                autocomplete="username"
                                placeholder="you@company.com"
                            />
                            <x-input-error :messages="$errors->get('email')" class="mt-2" />
                        </div>

                        <div>
                            <div class="flex items-center justify-between">
                                <x-input-label for="password" :value="__('Password')" />
                                @if (Route::has('password.request'))
                                    <a class="text-sm font-medium text-slate-700 hover:text-slate-900 underline-offset-4 hover:underline"
                                       href="{{ route('password.request') }}">
                                        Forgot password?
                                    </a>
                                @endif
                            </div>

                            <x-text-input
                                id="password"
                                class="mt-1 block w-full rounded-xl border-slate-300 bg-white px-3 py-2 shadow-sm focus:border-slate-900 focus:ring-slate-900"
                                type="password"
                                name="password"
                                required
                                autocomplete="current-password"
                                placeholder="••••••••••"
                            />
                            <x-input-error :messages="$errors->get('password')" class="mt-2" />
                        </div>

                        <div class="flex items-center justify-between">
                            <label for="remember_me" class="inline-flex items-center">
                                <input id="remember_me" type="checkbox"
                                       class="rounded border-slate-300 text-slate-900 shadow-sm focus:ring-slate-900"
                                       name="remember">
                                <span class="ms-2 text-sm text-slate-700">{{ __('Remember me') }}</span>
                            </label>
                        </div>

                        <button
                            type="submit"
                            class="inline-flex w-full items-center justify-center rounded-xl bg-blue-600 px-4 py-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:ring-offset-2"
                        >
                            Log in
                        </button>
                    </form>
                </div>

                <p class="mt-6 text-center text-xs text-slate-500">
                    © {{ date('Y') }} Buy DTF. All rights reserved.
                </p>
            </div>
        </div>
    </div>
</x-guest-layout>
