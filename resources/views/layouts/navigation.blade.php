<div class="sticky-top shadow-sm">
    @if(session()->has('admin_impersonator'))
        <div class="bg-warning text-dark py-2 text-center fw-bold">
            <div class="container d-flex align-items-center justify-content-center">
                <span class="me-3">You are currently impersonating {{ Auth::user()->name }}</span>
                <form action="{{ route('admin.businesses.stop-impersonating') }}" method="POST">
                    @csrf
                    <button type="submit" class="btn btn-dark btn-sm fw-bold px-3">Return to Admin</button>
                </form>
            </div>
        </div>
    @endif
    <!-- Top Bar (Black) -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-black py-3">
        <div class="container d-flex align-items-center justify-content-between">
            <!-- Logo and Mobile Menu Toggler -->
            <div class="d-flex align-items-center">
                <button class="navbar-toggler me-3" type="button" data-bs-toggle="offcanvas" data-bs-target="#mobileMenu" aria-controls="mobileMenu">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <a href="{{ route('home') }}" class="navbar-brand d-flex align-items-center p-0 m-0">
                    <img src="/assets/img/dtf_logo.svg" alt="Logo" class="header-logo" style="max-width: 220px;">
                </a>
            </div>

            <!-- Greeting + Cart -->
            <div class="d-flex align-items-center gap-3">
                <span class="d-none d-md-inline font-blinker fs-5 text-light opacity-75">
                    @auth
                        Welcome, <span class="text-white fw-bold">{{ Auth::user()->name }}</span>
                    @else
                        <a href="{{ route('login') }}" class="text-light text-decoration-none hover:text-white transition">Log in</a>
                    @endauth
                </span>

                <!-- Cart button -->
                <a href="{{ route('cart.index') }}" id="cart-indicator" class="btn btn-outline-light d-flex align-items-center px-3 py-2 position-relative rounded-3 border-secondary border-opacity-50">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="currentColor" class="bi bi-cart3 me-2 text-warning" viewBox="0 0 16 16">
                        <path d="M0 1.5A.5.5 0 0 1 .5 1H2a.5.5 0 0 1 .485.379L2.89 3H14.5a.5.5 0 0 1 .49.598l-1 5a.5.5 0 0 1-.465.401l-9.397.472L4.415 11H13a.5.5 0 0 1 0 1H4a.5.5 0 0 1-.491-.408L2.01 3.607 1.61 2H.5a.5.5 0 0 1-.5-.5zM3.102 4l.84 4.479 9.144-.459L13.89 4H3.102zM5 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm7 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm-7 1a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm7 0a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
                    </svg>
                    <span class="font-blinker fw-bold">Cart</span>
                    <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-warning text-dark shadow-sm px-2 d-none" id="cart-badge">
                        0
                    </span>
                </a>
            </div>
        </div>
    </nav>

    <!-- Main Menu (Desktop) -->
    <nav class="navbar navbar-expand-lg bg-white border-bottom border-light d-none d-lg-block py-0">
        <div class="container">
            <div class="navbar-nav w-100 d-flex justify-content-start align-items-center font-blinker tracking-wider position-relative" style="height: 64px;">
                <a href="{{ route('home') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-5 fw-semibold text-sp-secondary text-uppercase">Home</a>
                <a href="/aboutus" class="nav-link px-3 h-100 d-flex align-items-center fs-5 fw-semibold text-sp-secondary text-uppercase">About Us</a>

                <!-- Buy Direct to Film Dropdown -->
                <li class="nav-item dropdown h-100 d-flex align-items-center me-4">
                    <a class="nav-link fs-5 fw-semibold text-sp-secondary dropdown-toggle text-uppercase" href="#" id="buyDtfDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        Buy Direct to Film
                    </a>
                    <div class="dropdown-menu w-100 py-5" aria-labelledby="buyDtfDropdown">
                        <div class="container">
                            <div class="row mb-5">
                                <div class="col-12 col-lg">
                                    <h4 class="text-sp-secondary border-2 border-bottom font-ubuntu mb-3">About our DTF's</h4>
                                    <ul class="list-unstyled">
                                        <li class="mb-2 font-blinker fs-5">
                                            <a class="text-sp-primary text-decoration-none" href="/aboutdtf">Why buy from us?</a>
                                        </li>
                                        <li class="mb-2 font-blinker fs-5">
                                            <a class="text-sp-primary text-decoration-none" href="/about">How to buy DTF's</a>
                                        </li>
                                        <li class="mb-2 font-blinker fs-5">
                                            <a class="text-sp-primary text-decoration-none" href="/heatpress">Pressing Instructions</a>
                                        </li>
                                    </ul>
                                </div>
                                <div class="col-12 col-lg">
                                    <h4 class="text-sp-secondary border-2 border-bottom font-ubuntu mb-3">How to Order</h4>
                                    <ul class="list-unstyled">
                                        <li class="mb-2 font-blinker fs-5">
                                            <a class="text-sp-primary text-decoration-none" href="{{ route('register') }}">Sign up for an Account</a>
                                        </li>
                                        <li class="mb-2 font-blinker fs-5">
                                            <a class="text-sp-primary text-decoration-none" href="{{ route('login') }}">Login to your Account</a>
                                        </li>
                                        <li class="mb-2 font-blinker fs-5">
                                            <a class="text-sp-primary text-decoration-none fw-bold" href="{{ route('orders.new') }}">Start New Order</a>
                                        </li>
                                        <li class="mb-2 font-blinker fs-5">
                                            <a class="text-sp-primary text-decoration-none" href="/faq">FAQ</a>
                                        </li>
                                    </ul>
                                </div>
                                <div class="col-12 col-lg">
                                    <h4 class="text-sp-secondary border-2 border-bottom font-ubuntu mb-3">Artwork</h4>
                                    <ul class="list-unstyled">
                                        <li class="mb-2 font-blinker fs-5">
                                            <a class="text-sp-primary text-decoration-none" href="/imagerequirements">Image Requirements</a>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </li>

                @auth
                    <!-- My Account Dropdown -->
                    <li class="nav-item dropdown h-100 d-flex align-items-center me-4">
                        <a class="nav-link fs-5 fw-semibold text-sp-secondary dropdown-toggle text-uppercase" href="#" id="accountDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                            My Account
                        </a>
                        <div class="dropdown-menu w-100 py-5" aria-labelledby="accountDropdown">
                            <div class="container">
                                <div class="row mb-5">
                                    <div class="col-12 col-lg">
                                        <h4 class="text-sp-secondary border-2 border-bottom font-ubuntu mb-3">Account</h4>
                                        <ul class="list-unstyled">
                                            <li class="mb-2 font-blinker fs-5">
                                                <a class="text-sp-primary text-decoration-none" href="{{ route('account') }}">My Dashboard</a>
                                            </li>
                                            <li class="mb-2 font-blinker fs-5">
                                                <a class="text-sp-primary text-decoration-none fw-bold" href="{{ route('orders.new') }}">Start New Order</a>
                                            </li>
                                        </ul>
                                    </div>
                                    <div class="col-12 col-lg">
                                        <h4 class="text-sp-secondary border-2 border-bottom font-ubuntu mb-3">User Settings</h4>
                                        <ul class="list-unstyled">
                                            <li class="mb-2 font-blinker fs-5">
                                                <a class="text-sp-primary text-decoration-none" href="{{ route('profile.edit') }}">Update Profile</a>
                                            </li>
                                        </ul>
                                    </div>
                                    <div class="col-12 col-lg">
                                        <h4 class="text-sp-secondary border-2 border-bottom font-ubuntu mb-3">User</h4>
                                        <ul class="list-unstyled">
                                            <li class="mb-2 font-blinker fs-5">
                                                <form method="POST" action="{{ route('logout') }}">
                                                    @csrf
                                                    <button type="submit" class="btn btn-link p-0 font-blinker fs-5 text-danger text-decoration-none fw-bold">Log Out</button>
                                                </form>
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </li>
                @endauth

                <a href="{{ route('contact') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-5 fw-semibold text-sp-secondary text-uppercase">Contact Us</a>
            </div>
        </div>
    </nav>

    <!-- Optional Login Banner -->
    @guest
        <div class="bg-warning text-dark py-2 text-center small fw-bold shadow-sm">
            <span class="me-2">🚀 Ready to order?</span>
            Please <a href="{{ route('login') }}" class="text-dark text-decoration-underline hover:text-black">log in</a> or <a href="{{ route('register') }}" class="text-dark text-decoration-underline hover:text-black">sign up</a> to start your DTF journey.
        </div>
    @endguest
</div>

<!-- Mobile Offcanvas Menu -->
<div class="offcanvas offcanvas-start bg-white" tabindex="-1" id="mobileMenu" aria-labelledby="mobileMenuLabel">
    <div class="offcanvas-header border-bottom">
        <img src="/assets/img/dtf_logo.svg" alt="Logo" class="h-8" style="height: 32px;">
        <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
    </div>
    <div class="offcanvas-body p-0">
        <div class="list-group list-group-flush font-blinker">
            <a href="{{ route('home') }}" class="list-group-item list-group-item-action py-3 fw-bold text-uppercase">Home</a>
            <a href="/aboutus" class="list-group-item list-group-item-action py-3 fw-bold text-uppercase">About Us</a>

            <div class="accordion accordion-flush" id="mobileNavAccordion">
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed py-3 fw-bold text-uppercase" type="button" data-bs-toggle="collapse" data-bs-target="#collapseBuyDtf">
                            Buy Direct to Film
                        </button>
                    </h2>
                    <div id="collapseBuyDtf" class="accordion-collapse collapse" data-bs-parent="#mobileNavAccordion">
                        <div class="accordion-body bg-light">
                            <ul class="list-unstyled d-grid gap-3">
                                <li><a href="/aboutdtf" class="text-secondary text-decoration-none">Why buy from us?</a></li>
                                <li><a href="/about" class="text-secondary text-decoration-none">How to buy DTF's</a></li>
                                <li><a href="/heatpress" class="text-secondary text-decoration-none">Pressing Instructions</a></li>
                                <li><a href="{{ route('register') }}" class="text-secondary text-decoration-none">Sign up for an Account</a></li>
                                <li><a href="{{ route('login') }}" class="text-secondary text-decoration-none">Login to your Account</a></li>
                                <li><a href="{{ route('orders.new') }}" class="fw-bold text-dark text-decoration-none">Start New Order</a></li>
                                <li><a href="/faq" class="text-secondary text-decoration-none">FAQ</a></li>
                                <li><a href="/imagerequirements" class="text-secondary text-decoration-none">Image Requirements</a></li>
                            </ul>
                        </div>
                    </div>
                </div>

                @auth
                <div class="accordion-item">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed py-3 fw-bold text-uppercase" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAccount">
                            My Account
                        </button>
                    </h2>
                    <div id="collapseAccount" class="accordion-collapse collapse" data-bs-parent="#mobileNavAccordion">
                        <div class="accordion-body bg-light">
                            <ul class="list-unstyled d-grid gap-3">
                                <li><a href="{{ route('account') }}" class="text-secondary text-decoration-none">My Dashboard</a></li>
                                <li><a href="{{ route('orders.new') }}" class="fw-bold text-dark text-decoration-none">Start New Order</a></li>
                                <li><a href="{{ route('profile.edit') }}" class="text-secondary text-decoration-none">Account Information</a></li>
                            </ul>
                        </div>
                    </div>
                </div>
                @endauth
            </div>

            <a href="{{ route('contact') }}" class="list-group-item list-group-item-action py-3 fw-bold text-uppercase">Contact Us</a>
        </div>

        <div class="p-4 bg-light mt-auto">
            @guest
                <div class="d-grid gap-2">
                    <a href="{{ route('login') }}" class="btn btn-outline-dark fw-bold text-uppercase">Log in</a>
                    <a href="{{ route('register') }}" class="btn btn-warning fw-bold text-uppercase">Sign up</a>
                </div>
            @else
                <form method="POST" action="{{ route('logout') }}">
                    @csrf
                    <button type="submit" class="btn btn-outline-danger w-100 fw-bold text-uppercase">Log Out</button>
                </form>
            @endauth
        </div>
    </div>
</div>
