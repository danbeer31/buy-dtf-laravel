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

        <!-- Bootstrap Icons -->
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">

        <!-- Scripts -->
        <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
        @vite(['resources/css/app.scss', 'resources/js/app.js'])
        <script src="{{ asset('assets/js/cart/indicator.js') }}?v={{ filemtime(public_path('assets/js/cart/indicator.js')) }}"></script>

        @stack('styles')
    </head>
    <body class="font-sans antialiased">
        <div class="min-vh-100 bg-light d-flex flex-column">
            @if(request()->is('admin*') || request()->routeIs('admin.*'))
                @include('layouts.admin-navigation')
            @else
                @include('layouts.navigation')
            @endif

            <!-- Syncing Spinner Overlay -->
            <div id="syncing-overlay" class="position-fixed top-0 start-0 w-100 h-100 d-none align-items-center justify-content-center" style="background: rgba(255,255,255,0.8); z-index: 9999;">
                <div class="card shadow-lg border-0 rounded-4 p-4 text-center" style="max-width: 300px;">
                    <div class="d-flex justify-content-center mb-3">
                        <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                    <h5 class="fw-bold mb-1">Syncing with Stripe</h5>
                    <p class="text-muted small mb-0">Please wait while we fetch the latest transaction data...</p>
                </div>
            </div>

            <!-- Page Heading -->
            @isset($header)
                <header class="bg-white shadow-sm">
                    <div class="container py-4">
                        {{ $header }}
                    </div>
                </header>
            @endisset

            <!-- Page Content -->
            <main class="flex-grow-1" style="padding-bottom: 50px;">
                <div class="container mt-4">
                    @if(session('success'))
                        <div class="alert alert-success alert-dismissible fade show border-0 shadow-sm rounded-4" role="alert">
                            <i class="bi bi-check-circle-fill me-2"></i> {{ session('success') }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        </div>
                    @endif

                    @if(session('error'))
                        <div class="alert alert-danger alert-dismissible fade show border-0 shadow-sm rounded-4" role="alert">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i> {{ session('error') }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                        </div>
                    @endif
                </div>
                {{ $slot }}
            </main>

            @unless(request()->is('admin*') || request()->routeIs('admin.*'))
                @include('layouts.footer')
            @endunless
        </div>

        @stack('scripts')
        <script>
            $(document).ready(function() {
                $('.stripe-sync-form').on('submit', function() {
                    $('#syncing-overlay').removeClass('d-none').addClass('d-flex');
                });
            });
        </script>
    </body>
</html>
