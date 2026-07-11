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

    <!-- Top Bar (Dark) -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark py-3">
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

                @auth
                    <form method="POST" action="{{ route('logout') }}" class="m-0 d-none d-lg-block">
                        @csrf
                        <button type="submit" class="btn btn-outline-danger btn-sm px-3 fw-bold text-uppercase">Log Out</button>
                    </form>
                @endauth
            </div>
        </div>
    </nav>

    <!-- Secondary Nav (Desktop) -->
    <nav class="navbar navbar-expand-lg bg-white border-bottom border-light d-none d-lg-block py-0">
        <div class="container">
            <div class="navbar-nav w-100 d-flex justify-content-start align-items-center font-blinker tracking-wider" style="height: 56px;">
                <a href="{{ route('home') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('home') ? 'active text-primary border-bottom border-primary border-3' : '' }}">Home</a>

                @auth
                    <a href="{{ route('account') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('account') ? 'active text-primary border-bottom border-primary border-3' : '' }}">My Account</a>
                    <a href="{{ route('orders.new') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('orders.new') ? 'active text-primary border-bottom border-primary border-3' : '' }}">New Order</a>
                @endauth

                <!-- Buy DTF Dropdown -->
                <div class="nav-item dropdown h-100 d-flex align-items-center position-relative">
                    <a class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase dropdown-toggle {{ (request()->routeIs('about*') || request()->routeIs('heatpress') || request()->routeIs('faq') || request()->routeIs('imagerequirements')) ? 'active text-primary border-bottom border-primary border-3' : '' }}" href="#" id="buyDtfDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        Buy DTF
                    </a>
                    <ul class="dropdown-menu border-0 shadow-sm rounded-3 mt-0" aria-labelledby="buyDtfDropdown">
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary" href="{{ route('about.dtf') }}">Why buy from us?</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary" href="{{ route('about') }}">How to buy DTF's</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary" href="{{ route('heatpress') }}">Pressing Instructions</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary" href="{{ route('imagerequirements') }}">Image Requirements</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary" href="{{ route('faq') }}">FAQ</a></li>
                    </ul>
                </div>

                <a href="{{ route('contact') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('contact') ? 'active text-primary border-bottom border-primary border-3' : '' }}">Contact</a>

                @if(Auth::check() && Auth::user()->isAdmin())
                    <div class="ms-auto">
                        <a href="{{ route('admin.dashboard') }}" class="btn btn-sm btn-danger px-3 fw-bold text-uppercase">Admin Panel</a>
                    </div>
                @endif
            </div>
        </div>
    </nav>
</div>

<!-- Mobile Offcanvas Menu -->
<div class="offcanvas offcanvas-start bg-dark text-white" tabindex="-1" id="mobileMenu" aria-labelledby="mobileMenuLabel">
    <div class="offcanvas-header border-bottom border-secondary">
        <h5 class="offcanvas-title" id="mobileMenuLabel">Menu</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas" aria-label="Close"></button>
    </div>
    <div class="offcanvas-body p-0">
        <div class="list-group list-group-flush font-blinker">
            <a href="{{ route('home') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('home') ? 'text-primary' : '' }}">Home</a>

            @auth
                <a href="{{ route('account') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('account') ? 'text-primary' : '' }}">My Account</a>
                <a href="{{ route('orders.new') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('orders.new') ? 'text-primary' : '' }}">New Order</a>
            @endauth

            <div class="accordion accordion-flush" id="mobileNavAccordion">
                <div class="accordion-item bg-dark border-secondary">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed bg-dark text-white py-3 fw-bold text-uppercase shadow-none" type="button" data-bs-toggle="collapse" data-bs-target="#collapseBuyDtf">
                            Buy DTF
                        </button>
                    </h2>
                    <div id="collapseBuyDtf" class="accordion-collapse collapse" data-bs-parent="#mobileNavAccordion">
                        <div class="accordion-body bg-dark p-0">
                            <a href="{{ route('about.dtf') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase">Why buy from us?</a>
                            <a href="{{ route('about') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase">How to buy DTF's</a>
                            <a href="{{ route('heatpress') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase">Pressing Instructions</a>
                            <a href="{{ route('imagerequirements') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase">Image Requirements</a>
                            <a href="{{ route('faq') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase">FAQ</a>
                        </div>
                    </div>
                </div>
            </div>

            <a href="{{ route('contact') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('contact') ? 'text-primary' : '' }}">Contact</a>

            @guest
                <a href="{{ route('login') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase">Log In</a>
                <a href="{{ route('register') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase text-warning">Sign Up</a>
            @else
                <form method="POST" action="{{ route('logout') }}">
                    @csrf
                    <button type="submit" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase text-danger">Log Out</button>
                </form>
            @endguest
        </div>
    </div>
</div>
