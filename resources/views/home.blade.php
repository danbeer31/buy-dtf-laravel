<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Welcome to Next Level DTF') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Welcome / Hero -->
            <div class="bg-dark text-white text-center py-5 rounded-4 shadow-lg mb-5 px-4">
                <h1 class="display-4 fw-bold mb-3">Welcome to Next Level DTF</h1>
                <p class="lead mb-5 text-light opacity-75">High-quality DTF prints for your business needs. Durable, vibrant, and customizable.</p>

                <div class="d-flex flex-column flex-sm-row gap-3 justify-content-center">
                    @auth
                        <a href="{{ route('account') }}" class="btn btn-warning btn-lg px-4 fw-bold text-uppercase tracking-wider">
                            <span class="badge bg-black text-warning me-2">NEW</span>
                            My Account Dashboard
                        </a>
                        <a href="/orders/order" class="btn btn-outline-light btn-lg px-4 fw-bold text-uppercase tracking-wider">
                            Classic Order Form
                        </a>
                    @else
                        <a href="/cart" class="btn btn-warning btn-lg px-4 fw-bold text-uppercase tracking-wider">
                            <span class="badge bg-black text-warning me-2">NEW</span>
                            Try our Cart & Uploader
                        </a>
                        <a href="{{ route('register') }}" class="btn btn-outline-light btn-lg px-4 fw-bold text-uppercase tracking-wider">
                            Create Account
                        </a>
                    @endauth
                </div>

                <div class="text-secondary small mt-4">
                    Upload PNG / SVG / PDF • Smart duplicate detection • Live progress
                </div>
            </div>

            <!-- Features -->
            <section class="py-5 bg-white rounded-4 shadow-sm mb-5">
                <div class="container text-center">
                    <h2 class="h1 fw-bold text-dark text-uppercase mb-5 tracking-wide">Why Choose Us?</h2>
                    <div class="row g-4">
                        <div class="col-md-4">
                            <div class="text-primary mb-4">
                                <svg class="bi" width="64" height="64" fill="currentColor"><use xlink:href="#vibrant-icon"/></svg>
                                <!-- Inline SVG for icon if use not working -->
                                <svg class="w-16 h-16 mx-auto text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="width: 64px; height: 64px;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.172-1.172a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"></path></svg>
                            </div>
                            <h5 class="fw-bold fs-4 mb-3">High Quality & Vibrant Colors</h5>
                            <p class="text-muted">Our prints are vivid, long-lasting, and stand out on any fabric.</p>
                        </div>
                        <div class="col-md-4">
                            <div class="text-primary mb-4">
                                <svg class="w-16 h-16 mx-auto text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="width: 64px; height: 64px;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 4l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path></svg>
                            </div>
                            <h5 class="fw-bold fs-4 mb-3">Don't Pay for Empty Film</h5>
                            <p class="text-muted">You only pay by the square inches of the images—no charges for blank film.</p>
                        </div>
                        <div class="col-md-4">
                            <div class="text-primary mb-4">
                                <svg class="w-16 h-16 mx-auto text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="width: 64px; height: 64px;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            </div>
                            <h5 class="fw-bold fs-4 mb-3">Fast Delivery</h5>
                            <p class="text-muted">Quick turnaround to get your orders on time.</p>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Contact -->
            <section class="bg-primary text-white py-5 rounded-4 shadow-lg">
                <div class="container text-center">
                    <h2 class="h1 fw-bold text-uppercase mb-3 tracking-wide">Get In Touch</h2>
                    <p class="lead mb-4 opacity-75">Have questions or need assistance? Contact us!</p>
                    <a href="/contact" class="btn btn-light btn-lg px-5 fw-bold text-primary text-uppercase tracking-wider shadow-sm">
                        Contact Us
                    </a>
                </div>
            </section>
        </div>
    </div>
</x-app-layout>
