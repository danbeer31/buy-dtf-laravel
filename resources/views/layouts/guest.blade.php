<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="csrf-token" content="{{ csrf_token() }}">

        <title>{{ config('app.name', 'Laravel') }}</title>

        <!-- Fonts -->
        <link rel="preconnect" href="https://fonts.bunny.net">
        <link href="https://fonts.bunny.net/css?family=figtree:400,500,600&display=swap" rel="stylesheet" />

        <!-- Scripts -->
        <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
        @vite(['resources/css/app.scss', 'resources/js/app.js'])
        <script src="{{ asset('assets/js/cart/indicator.js') }}"></script>

        @stack('styles')
    </head>
    <body class="font-sans text-dark antialiased bg-light">
        <div class="min-vh-100 d-flex flex-column align-items-center pt-5">
            <div class="flex-grow-1 d-flex flex-column justify-content-center align-items-center w-100 px-3">
                <div class="mb-4">
                    <a href="/">
                        <img src="/assets/img/dtf_logo.svg" alt="Logo" class="header-logo" style="max-width: 280px;">
                    </a>
                </div>

                <div class="card shadow-sm border-0 w-100 overflow-hidden" style="max-width: 450px;">
                    <div class="card-body p-4 p-md-5">
                        {{ $slot }}
                    </div>
                </div>
            </div>

            @unless(request()->is('admin*'))
                <div class="w-100">
                    @include('layouts.footer')
                </div>
            @endunless
        </div>

        @stack('scripts')
    </body>
</html>
