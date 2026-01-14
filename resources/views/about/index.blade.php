<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('About Our DTF Services') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="text-center mb-5">
                <h1 class="display-4 fw-bold">Why Choose Our DTF Printing Services?</h1>
                <p class="lead text-muted">High-quality, fast, and reliable DTF printing services tailored for your needs.</p>
            </div>

            <!-- Key Features Section -->
            <section class="mb-5">
                <div class="row text-center">
                    <div class="col-md-4 mb-4">
                        <i class="bi bi-palette-fill fs-1 text-primary"></i>
                        <h5 class="mt-3 fw-bold">High Quality Prints</h5>
                        <p class="text-muted">Our DTF prints are vibrant, durable, and stand out on any fabric.</p>
                    </div>
                    <div class="col-md-4 mb-4">
                        <i class="bi bi-speedometer2 fs-1 text-primary"></i>
                        <h5 class="mt-3 fw-bold">Fast Turnaround</h5>
                        <p class="text-muted">Most orders are printed the same day or the next day to ensure quick delivery.</p>
                    </div>
                    <div class="col-md-4 mb-4">
                        <i class="bi bi-bounding-box-circles fs-1 text-primary"></i>
                        <h5 class="mt-3 fw-bold">Pay for What You Use</h5>
                        <p class="text-muted">You only pay for the square inches of your image—no extra charge for empty film.</p>
                    </div>
                </div>
            </section>

            <!-- Quick Guide Section -->
            <section class="mb-5">
                <h2 class="text-center mb-4 fw-bold text-primary">Getting Started is Easy</h2>
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div class="card h-100 border-0 shadow-sm rounded-4 p-4">
                            <h4 class="text-primary fw-bold">1. Create an Account</h4>
                            <p>Sign up for a free account to access our services. Provide your business details and set up your profile.</p>
                            <a href="{{ route('register') }}" class="btn btn-primary mt-auto">Sign Up Now</a>
                        </div>
                    </div>
                    <div class="col-md-6 mb-4">
                        <div class="card h-100 border-0 shadow-sm rounded-4 p-4">
                            <h4 class="text-primary fw-bold">2. Place Your First Order</h4>
                            <p>Upload your designs, select sizes and quantities, and submit your order. It’s quick and simple!</p>
                            <a href="/orders/order" class="btn btn-primary mt-auto">Place an Order</a>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Order Process Section -->
            <section class="mb-5">
                <h2 class="text-center mb-4 fw-bold text-primary">What Happens After You Order?</h2>
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div class="card h-100 border-0 shadow-sm rounded-4 p-4 text-center">
                            <h4 class="text-primary fw-bold">Receive Your Invoice</h4>
                            <p>Once you place an order, you’ll receive an invoice via QuickBooks. Check your email for the details.</p>
                        </div>
                    </div>
                    <div class="col-md-6 mb-4">
                        <div class="card h-100 border-0 shadow-sm rounded-4 p-4 text-center">
                            <h4 class="text-primary fw-bold">Pay and Begin Production</h4>
                            <p>As soon as your payment is processed, your order moves into production. We’ll get started right away!</p>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Call to Action -->
            <div class="text-center mt-5">
                <h3 class="mb-4 fw-bold">Ready to Experience the Best in DTF Printing?</h3>
                <a href="{{ route('register') }}" class="btn btn-lg btn-warning px-5 fw-bold text-uppercase">Get Started Today</a>
            </div>
        </div>
    </div>
</x-app-layout>
