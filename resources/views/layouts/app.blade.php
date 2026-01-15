<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="csrf-token" content="{{ csrf_token() }}">

        <title>{{ config('app.name', 'Laravel') }}</title>

        <!-- Fonts -->
        <link rel="preconnect" href="https://fonts.bunny.net">
        <link href="https://fonts.bunny.net/css?family=figtree:400,500,600|blinker:400,600,700|ubuntu:400,500,700&display=swap" rel="stylesheet" />

        <!-- Scripts -->
        <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
        @vite(['resources/css/app.scss', 'resources/js/app.js'])
        <script src="{{ asset('assets/js/cart/indicator.js') }}"></script>

        @stack('styles')
    </head>
    <body class="font-sans antialiased">
        <div class="min-vh-100 bg-light d-flex flex-column">
            @if(request()->is('admin*'))
                @include('layouts.admin-navigation')
            @else
                @include('layouts.navigation')
            @endif

            <!-- Page Heading -->
            @isset($header)
                <header class="bg-white shadow-sm d-none">
                    <div class="container py-4">
                        {{ $header }}
                    </div>
                </header>
            @endisset

            <!-- Page Content -->
            <main class="flex-grow-1">
                @if(session('success') && !request()->is('admin*'))
                    <div class="container mt-4">
                        <div class="alert alert-success alert-dismissible fade show border-0 shadow-sm rounded-4" role="alert">
                            {{ session('success') }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        </div>
                    </div>
                @endif

                @if(session('error') && !request()->is('admin*'))
                    <div class="container mt-4">
                        <div class="alert alert-danger alert-dismissible fade show border-0 shadow-sm rounded-4" role="alert">
                            {{ session('error') }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        </div>
                    </div>
                @endif
                {{ $slot }}
            </main>

            @unless(request()->is('admin*'))
                @include('layouts.footer')
            @endunless
        </div>

        @stack('scripts')
    </body>
</html>
