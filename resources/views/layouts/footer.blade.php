<footer class="bg-black text-white py-5 mt-5">
    <div class="container">
        <div class="row g-4">
            <div class="col-lg-6">
                <div class="mb-4">
                    <img src="/assets/img/dtf_logo.svg" alt="Next Level DTF Logo" class="footer-logo mb-3" style="max-width: 200px;">
                    <p class="text-secondary" style="max-width: 400px;">High-quality DTF prints for your business needs. Durable, vibrant, and customizable.</p>
                </div>
            </div>
            <div class="col-md-3">
                <h4 class="fw-bold mb-3">Quick Links</h4>
                <ul class="list-unstyled d-grid gap-2">
                    <li>
                        <a href="{{ route('home') }}" class="text-secondary text-decoration-none hover:text-primary transition d-flex align-items-center gap-2">
                            <i class="bi bi-house-door-fill text-primary"></i> Home
                        </a>
                    </li>
                    <li>
                        <a href="{{ route('heatpress') }}" class="text-secondary text-decoration-none hover:text-primary transition d-flex align-items-center gap-2">
                            <i class="bi bi-fire text-primary"></i> Heat Press Instructions
                        </a>
                    </li>
                    <li>
                        <a href="{{ route('imagerequirements') }}" class="text-secondary text-decoration-none hover:text-primary transition d-flex align-items-center gap-2">
                            <i class="bi bi-file-earmark-image-fill text-primary"></i> Image Requirements
                        </a>
                    </li>
                    <li>
                        <a href="{{ route('faq') }}" class="text-secondary text-decoration-none hover:text-primary transition d-flex align-items-center gap-2">
                            <i class="bi bi-question-circle-fill text-primary"></i> FAQ
                        </a>
                    </li>
                    <li>
                        <a href="{{ route('contact') }}" class="text-secondary text-decoration-none hover:text-primary transition d-flex align-items-center gap-2">
                            <i class="bi bi-chat-dots-fill text-primary"></i> Contact Us
                        </a>
                    </li>
                    @guest
                        <li>
                            <a href="{{ route('login') }}" class="text-secondary text-decoration-none hover:text-primary transition d-flex align-items-center gap-2">
                                <i class="bi bi-box-arrow-in-right text-primary"></i> Login
                            </a>
                        </li>
                        <li>
                            <a href="{{ route('register') }}" class="text-secondary text-decoration-none hover:text-primary transition d-flex align-items-center gap-2">
                                <i class="bi bi-person-plus-fill text-primary"></i> Register
                            </a>
                        </li>
                    @endguest
                </ul>
            </div>
            <div class="col-md-3">
                <h4 class="fw-bold mb-3">Contact Us</h4>
                <ul class="list-unstyled d-grid gap-2 text-secondary">
                    <li class="d-flex align-items-start gap-2">
                        <i class="bi bi-geo-alt-fill text-primary"></i>
                        <span>811 Fairfield Ave,<br>LaPorte, IN 46350</span>
                    </li>
                    <li class="d-flex align-items-center gap-2">
                        <i class="bi bi-telephone-fill text-primary"></i>
                        <a href="tel:2192214060" class="text-secondary text-decoration-none hover:text-primary">(219) 221-4060</a>
                    </li>
                    <li class="d-flex align-items-center gap-2">
                        <i class="bi bi-envelope-fill text-primary"></i>
                        <a href="mailto:info@nlcustomtees.com" class="text-secondary text-decoration-none hover:text-primary">info@nlcustomtees.com</a>
                    </li>
                </ul>
            </div>
        </div>
        <div class="border-top border-secondary mt-5 pt-4 text-center text-secondary small">
            <p class="mb-0">&copy; {{ date('Y') }} Next Level DTF. All rights reserved.</p>
        </div>
    </div>
</footer>
