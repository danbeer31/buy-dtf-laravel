<footer class="bg-black text-white py-5 mt-5">
    <div class="container">
        <div class="row g-4">
            <div class="col-lg-6">
                <h3 class="fw-bold mb-3">Next Level DTF</h3>
                <p class="text-secondary mb-4" style="max-width: 400px;">High-quality DTF prints for your business needs. Durable, vibrant, and customizable.</p>
                <div class="d-flex gap-3">
                    <!-- Social icons could go here -->
                </div>
            </div>
            <div class="col-md-3">
                <h4 class="fw-bold mb-3">Quick Links</h4>
                <ul class="list-unstyled d-grid gap-2">
                    <li><a href="{{ route('home') }}" class="text-secondary text-decoration-none hover:text-primary transition">Home</a></li>
                    <li><a href="{{ route('contact') }}" class="text-secondary text-decoration-none hover:text-primary transition">Contact Us</a></li>
                    @guest
                        <li><a href="{{ route('login') }}" class="text-secondary text-decoration-none hover:text-primary transition">Login</a></li>
                        <li><a href="{{ route('register') }}" class="text-secondary text-decoration-none hover:text-primary transition">Register</a></li>
                    @endguest
                </ul>
            </div>
            <div class="col-md-3">
                <h4 class="fw-bold mb-3">Contact</h4>
                <ul class="list-unstyled d-grid gap-2 text-secondary">
                    <li>Email: <a href="mailto:support@nextleveldtf.com" class="text-secondary text-decoration-none hover:text-primary">support@nextleveldtf.com</a></li>
                    <!-- Add other contact info if available -->
                </ul>
            </div>
        </div>
        <div class="border-top border-secondary mt-5 pt-4 text-center text-secondary small">
            <p class="mb-0">&copy; {{ date('Y') }} Next Level DTF. All rights reserved.</p>
        </div>
    </div>
</footer>
