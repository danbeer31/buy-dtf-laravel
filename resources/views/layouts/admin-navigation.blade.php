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
                    <img src="/assets/img/dtf_logo.svg" alt="Logo" class="header-logo" style="max-width: 220px;">
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

                <div class="nav-item dropdown h-100 d-flex align-items-center position-relative">
                    <a class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase dropdown-toggle {{ request()->routeIs('admin.orders.*') ? 'active text-primary' : '' }}" href="#" id="ordersDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        Orders
                    </a>
                    <ul class="dropdown-menu border-0 shadow-sm rounded-3 mt-0" aria-labelledby="ordersDropdown">
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary" href="{{ route('admin.orders.index') }}">All Orders</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary" href="{{ route('admin.orders.production') }}">Production</a></li>
                    </ul>
                </div>

                <a href="{{ route('admin.businesses.index') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('admin.businesses.*') ? 'active text-primary' : '' }}">Businesses</a>

                <a href="{{ route('admin.users.index') }}" class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase {{ request()->routeIs('admin.users.*') ? 'active text-primary' : '' }}">Users</a>

                <div class="nav-item dropdown h-100 d-flex align-items-center position-relative">
                    <a class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase dropdown-toggle {{ (request()->routeIs('admin.shipping.*') || request()->routeIs('admin.dropbox.*') || request()->routeIs('admin.qbo.*')) ? 'active text-primary' : '' }}" href="#" id="configurationDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        Configuration
                    </a>
                    <ul class="dropdown-menu border-0 shadow-sm rounded-3 mt-0" aria-labelledby="configurationDropdown">
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.shipping.*') ? 'text-primary' : '' }}" href="{{ route('admin.shipping.index') }}">Shipping</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.dropbox.*') ? 'text-primary' : '' }}" href="{{ route('admin.dropbox.status') }}">Dropbox</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.qbo.*') ? 'text-primary' : '' }}" href="{{ route('admin.qbo.index') }}">QuickBooks</a></li>
                    </ul>
                </div>

                <div class="nav-item dropdown h-100 d-flex align-items-center position-relative">
                    <a class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase dropdown-toggle {{ request()->routeIs('admin.payments.stripe*') ? 'active text-primary' : '' }}" href="#" id="stripeDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        Stripe
                    </a>
                    <ul class="dropdown-menu border-0 shadow-sm rounded-3 mt-0" aria-labelledby="stripeDropdown">
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.payments.stripe') ? 'text-primary' : '' }}" href="{{ route('admin.payments.stripe') }}">Transactions</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.payments.stripe.payouts') ? 'text-primary' : '' }}" href="{{ route('admin.payments.stripe.payouts') }}">Payouts (Deposits)</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.payments.stripe.sync-logs*') ? 'text-primary' : '' }}" href="{{ route('admin.payments.stripe.sync-logs') }}">Sync Logs</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.payments.reconciliation.*') ? 'text-primary' : '' }}" href="{{ route('admin.payments.reconciliation.index') }}">Reconciliation</a></li>
                    </ul>
                </div>

                <div class="nav-item dropdown h-100 d-flex align-items-center position-relative">
                    <a class="nav-link px-3 h-100 d-flex align-items-center fs-6 fw-semibold text-sp-secondary text-uppercase dropdown-toggle {{ (request()->routeIs('admin.customnames.*') || request()->routeIs('admin.customcolors.*')) ? 'active text-primary' : '' }}" href="#" id="customizationDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                        Customization
                    </a>
                    <ul class="dropdown-menu border-0 shadow-sm rounded-3 mt-0" aria-labelledby="customizationDropdown">
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.customnames.index') ? 'text-primary' : '' }}" href="{{ route('admin.customnames.index') }}">Name & Number Config</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.customnames.fonts') ? 'text-primary' : '' }}" href="{{ route('admin.customnames.fonts') }}">Font Management</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.customnames.fontsmap') ? 'text-primary' : '' }}" href="{{ route('admin.customnames.fontsmap') }}">Font Display Names</a></li>
                        <li><a class="dropdown-item py-2 fw-semibold text-sp-secondary {{ request()->routeIs('admin.customcolors.*') ? 'text-primary' : '' }}" href="{{ route('admin.customcolors.index') }}">Custom Colors</a></li>
                    </ul>
                </div>

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
            <div class="accordion accordion-flush" id="adminMobileAccordion">
                <div class="accordion-item bg-dark border-secondary">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed bg-dark text-white py-3 fw-bold text-uppercase shadow-none" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAdminOrders">
                            Orders
                        </button>
                    </h2>
                    <div id="collapseAdminOrders" class="accordion-collapse collapse {{ (request()->routeIs('admin.orders.*')) ? 'show' : '' }}" data-bs-parent="#adminMobileAccordion">
                        <div class="accordion-body bg-dark p-0">
                            <a href="{{ route('admin.orders.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.orders.index') ? 'text-primary' : '' }}">All Orders</a>
                            <a href="{{ route('admin.orders.production') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.orders.production') ? 'text-primary' : '' }}">Production</a>
                        </div>
                    </div>
                </div>

                <div class="accordion-item bg-dark border-secondary">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed bg-dark text-white py-3 fw-bold text-uppercase shadow-none" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAdminCustomization">
                            Customization
                        </button>
                    </h2>
                    <div id="collapseAdminCustomization" class="accordion-collapse collapse {{ (request()->routeIs('admin.customnames.*') || request()->routeIs('admin.customcolors.*')) ? 'show' : '' }}" data-bs-parent="#adminMobileAccordion">
                        <div class="accordion-body bg-dark p-0">
                            <a href="{{ route('admin.customnames.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.customnames.index') ? 'text-primary' : '' }}">Name & Number Config</a>
                            <a href="{{ route('admin.customnames.fonts') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.customnames.fonts') ? 'text-primary' : '' }}">Font Management</a>
                            <a href="{{ route('admin.customnames.fontsmap') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.customnames.fontsmap') ? 'text-primary' : '' }}">Font Display Names</a>
                            <a href="{{ route('admin.customcolors.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.customcolors.*') ? 'text-primary' : '' }}">Custom Colors</a>
                        </div>
                    </div>
                </div>
                <div class="accordion-item bg-dark border-secondary">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed bg-dark text-white py-3 fw-bold text-uppercase shadow-none" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAdminConfiguration">
                            Configuration
                        </button>
                    </h2>
                    <div id="collapseAdminConfiguration" class="accordion-collapse collapse {{ (request()->routeIs('admin.shipping.*') || request()->routeIs('admin.dropbox.*') || request()->routeIs('admin.qbo.*')) ? 'show' : '' }}" data-bs-parent="#adminMobileAccordion">
                        <div class="accordion-body bg-dark p-0">
                            <a href="{{ route('admin.shipping.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.shipping.*') ? 'text-primary' : '' }}">Shipping</a>
                            <a href="{{ route('admin.dropbox.status') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.dropbox.*') ? 'text-primary' : '' }}">Dropbox</a>
                            <a href="{{ route('admin.qbo.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.qbo.*') ? 'text-primary' : '' }}">QuickBooks</a>
                        </div>
                    </div>
                </div>

                <div class="accordion-item bg-dark border-secondary">
                    <h2 class="accordion-header">
                        <button class="accordion-button collapsed bg-dark text-white py-3 fw-bold text-uppercase shadow-none" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAdminStripe">
                            Stripe
                        </button>
                    </h2>
                    <div id="collapseAdminStripe" class="accordion-collapse collapse {{ request()->routeIs('admin.payments.stripe*') ? 'show' : '' }}" data-bs-parent="#adminMobileAccordion">
                        <div class="accordion-body bg-dark p-0">
                            <a href="{{ route('admin.payments.stripe') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.payments.stripe') ? 'text-primary' : '' }}">Transactions</a>
                            <a href="{{ route('admin.payments.stripe.payouts') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.payments.stripe.payouts') ? 'text-primary' : '' }}">Payouts (Deposits)</a>
                            <a href="{{ route('admin.payments.stripe.sync-logs') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.payments.stripe.sync-logs*') ? 'text-primary' : '' }}">Sync Logs</a>
                            <a href="{{ route('admin.payments.reconciliation.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-0 ps-4 py-2 small text-uppercase {{ request()->routeIs('admin.payments.reconciliation.*') ? 'text-primary' : '' }}">Reconciliation</a>
                        </div>
                    </div>
                </div>
            </div>

            <a href="{{ route('admin.users.index') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase {{ request()->routeIs('admin.users.*') ? 'text-primary' : '' }}">Users</a>
            <a href="#" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase">Products</a>
            <a href="{{ route('home') }}" class="list-group-item list-group-item-action bg-dark text-white border-secondary py-3 fw-bold text-uppercase">View Store</a>
        </div>
    </div>
</div>
