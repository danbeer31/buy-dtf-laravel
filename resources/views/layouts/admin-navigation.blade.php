<div class="sticky-top shadow-sm">
    <!-- Top Bar (Admin - Dark Blue) -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark py-3">
        <div class="container d-flex align-items-center justify-content-between">
            <!-- Logo and Mobile Menu Toggler -->
            <div class="d-flex align-items-center">
                <button class="navbar-toggler me-3" type="button" data-bs-toggle="offcanvas" data-bs-target="#adminMobileMenu" aria-controls="adminMobileMenu">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <a href="{{ route('admin.dashboard') }}" class="navbar-brand d-flex align-items-center p-0 m-0">
                    <img src="/assets/img/dtf_logo.svg" alt="Logo" class="header-logo" style="max-width: 220px; filter: brightness(0) invert(1);">
                    <span class="ms-2 badge bg-danger text-uppercase tracking-wider">Admin</span>
                </a>
            </div>

            <!-- Admin Profile + Logout -->
            <div class="d-flex align-items-center gap-3">
                <span class="d-none d-md-inline font-blinker fs-5 text-light opacity-75">
                    Logged in as: <span class="text-white fw-bold">{{ Auth::user()->name }}</span>
                </span>

                <form method="POST" action="{{ route('logout') }}" class="m-0">
                    @csrf
                    <button type="submit" class="btn btn-outline-danger btn-sm px-3 fw-bold text-uppercase">Log Out</button>
                </form>
            </div>
        </div>
    </nav>

    <!-- Admin Secondary Nav -->
    <nav class="navbar navbar-expand-lg bg-white border-bottom border-light d-none d-lg-block py-0">
        <div class="container">
            <div class="navbar-nav w-100 d-flex justify-content-start align-items-center font-blinker tracking-wider" style="height: 56px;">
                <a href="{{ route('admin.dashboard') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('admin.dashboard') ? 'active text-primary' : '' }}">Dashboard</a>

                <a href="{{ route('admin.businesses.index') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('admin.businesses.*') ? 'active text-primary' : '' }}">Businesses</a>

                <a href="{{ route('admin.customnames.index') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('admin.customnames.*') ? 'active text-primary' : '' }}">Custom Names</a>

                <a href="{{ route('admin.customcolors.index') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('admin.customcolors.*') ? 'active text-primary' : '' }}">Custom Colors</a>

                <!-- Example Admin Links (Can be expanded) -->
                <a href="#" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase">Orders</a>
                <a href="{{ route('admin.users.index') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('admin.users.*') ? 'active text-primary' : '' }}">Users</a>
                <a href="#" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase">Products</a>

                <div class="ms-auto">
                    <a href="{{ route('home') }}" class="btn btn-sm btn-link text-decoration-none text-secondary">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-box-arrow-left me-1" viewBox="0 0 16 16">
                            <path fill-rule="evenodd" d="M6 12.5a.5.5 0 0 0 .5.5h8a.5.5 0 0 0 .5-.5v-9a.5.5 0 0 0-.5-.5h-8a.5.5 0 0 0-.5.5v2a.5.5 0 0 1-1 0v-2A1.5 1.5 0 0 1 6.5 2h8A1.5 1.5 0 0 1 16 3.5v9a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 5 12.5v-2a.5.5 0 0 1 1 0v2z"/>
                            <path fill-rule="evenodd" d="M.146 8.354a.5.5 0 0 1 0-.708l3-3a.5.5 0 1 1 .708.708L1.707 7.5H10.5a.5.5 0 0 1 0 1H1.707l2.147 2.146a.5.5 0 0 1-.708.708l-3-3z"/>
                        </svg>
                        Exit to Store
                    </a>
                </div>
            </div>
        </div>
    </nav>
</div>

<!-- Admin Mobile Offcanvas -->
<div class="offcanvas offcanvas-start bg-dark text-white" tabindex="-1" id="adminMobileMenu" aria-labelledby="adminMobileMenuLabel">
    <div class="offcanvas-header border-bottom border-secondary">
        <h5 class="offcanvas-title" id="adminMobileMenuLabel">Admin Menu</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas" aria-label="Close"></button>
    </div>
    <div class="offcanvas-body p-0">
        <div class="list-group list-group-flush font-blinker">
            <a href="{{ route('admin.dashboard') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('admin.dashboard') ? 'text-primary' : '' }}">Dashboard</a>
            <a href="{{ route('admin.businesses.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('admin.businesses.*') ? 'text-primary' : '' }}">Businesses</a>
            <a href="{{ route('admin.customnames.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('admin.customnames.*') ? 'text-primary' : '' }}">Custom Names</a>
            <a href="{{ route('admin.customcolors.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('admin.customcolors.*') ? 'text-primary' : '' }}">Custom Colors</a>
            <a href="#" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase">Orders</a>
            <a href="{{ route('admin.users.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('admin.users.*') ? 'text-primary' : '' }}">Users</a>
            <a href="#" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase">Products</a>
            <a href="{{ route('home') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase">View Store</a>
        </div>
    </div>
</div>
