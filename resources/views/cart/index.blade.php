<x-app-layout>

    <div class="py-12 position-relative main-content-container">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg p-5">

                <div class="alert alert-info border-0 shadow-sm rounded-4 d-flex align-items-center bg-primary bg-opacity-10 text-primary-emphasis mb-4" role="alert">
                    <i class="bi bi-info-circle-fill fs-4 me-3"></i>
                    <div>
                        Need custom names and numbers? <a href="{{ route('teamcustomization.index') }}" class="fw-bold text-primary">Click here!</a>
                    </div>
                </div>

                <div class="d-flex align-items-center justify-content-end mb-4 bg-light p-3 rounded-4 shadow-sm">
                    <div class="d-flex align-items-center gap-2">
                        <div class="position-relative">
                            <div class="input-group input-group-sm">
                                <span class="input-group-text bg-white border-end-0"><i class="bi bi-search text-muted"></i></span>
                                <input id="qa-search" class="form-control border-start-0 ps-0" type="search"
                                       placeholder="Search past images…" autocomplete="off" style="min-width:220px;">
                            </div>
                            <div id="qa-suggest" class="dropdown-menu dropdown-menu-end w-100 shadow border-0"></div>
                        </div>
                        <button id="qa-browse" type="button" class="btn btn-sm btn-primary px-3 rounded-pill fw-semibold">
                            <i class="bi bi-images me-1"></i> Saved Images
                        </button>
                    </div>
                </div>

                @if(!empty($items))
                    <div id="img-grid" class="row g-3" data-order-id="{{ $order_id }}">
                        @foreach($items as $it)
                            @include('cart._dtfimage_card', ['it' => $it])
                        @endforeach
                    </div>
                @else
                    <div id="empty-cart-state" class="text-center py-5 bg-light rounded-4 mb-4 border border-dashed">
                        <i class="bi bi-cart-x fs-1 text-muted opacity-25"></i>
                        <p class="mt-3 text-muted fw-semibold">Your order is currently empty.</p>
                        <p class="small text-muted">Upload designs below or select from your saved images to get started.</p>
                    </div>
                @endif


                <div class="col-12 col-lg-10 mx-auto mt-5 font-blinker overflow-visible" style="position: relative; z-index: 1;">
                    <div id="upload-card" class="card shadow border-0 rounded-4 overflow-hidden">
                        <div class="card-body p-4 bg-white">
                            <div class="d-flex align-items-center mb-3">
                                <div class="bg-primary bg-opacity-10 p-2 rounded-3 me-3">
                                    <i class="bi bi-cloud-upload fs-3 text-primary"></i>
                                </div>
                                <div>
                                    <h4 class="mb-0 fw-bold">Upload Your DTF Files</h4>
                                    <div class="text-muted small">Quickly upload new designs to your order</div>
                                </div>
                            </div>

                            <p class="text-muted mb-4">
                                <span class="badge bg-light text-dark border fw-medium me-1">PNG</span>
                                <span class="badge bg-light text-dark border fw-medium me-1">SVG</span>
                                <span class="badge bg-light text-dark border fw-medium me-1">PDF</span>
                                <span class="ms-2 x-small text-secondary">Auto-trim, 300 DPI, transparent pixels cleaned.</span>
                            </p>

                            <div id="drop-area"
                                 class="border border-2 border-dashed rounded-4 p-5 text-center bg-light border-primary transition-all hover-bg-white cursor-pointer" style="border-style: dashed !important;">
                                <div class="mb-3">
                                    <i class="bi bi-plus-circle-dotted fs-1 text-primary opacity-50"></i>
                                </div>
                                <p class="mb-3 fs-4 fw-bold text-dark">Drag &amp; drop files here</p>
                                <button id="pick-btn" type="button" class="btn btn-primary px-4 py-2 rounded-pill fw-bold shadow-sm">
                                    <i class="bi bi-file-earmark-arrow-up me-1"></i> Choose Files
                                </button>
                                <div class="x-small text-muted mt-3">Supports clipboard pasting (Ctrl+V) for images.</div>
                                <input
                                        id="file-input"
                                        type="file"
                                        class="d-none"
                                        multiple
                                        accept=".png,.svg,.pdf,image/png,image/svg+xml,application/pdf">
                            </div>

                            <div id="queue" class="mt-4">
                                <!-- file cards will appear here -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    {{-- Modal for Saved Images --}}
    <div class="modal fade" id="qa-modal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-scrollable">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Your Saved Images</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="d-flex gap-2 mb-3">
                        <input id="qa-modal-search" class="form-control" placeholder="Search by name…">
                        <button id="qa-modal-refresh" class="btn btn-outline-secondary">Refresh</button>
                    </div>

                    <div id="qa-grid" class="row g-3"></div>

                    <div id="qa-more" class="text-center mt-3 d-none">
                        <button class="btn btn-light">Load more</button>
                    </div>

                    <div id="qa-empty" class="text-center text-muted py-4 d-none">
                        No results.
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Sticky Footer -->
    <div class="cart-sticky-footer d-md-block d-none shadow-lg">
        <div class="container d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
                <a href="{{ route('account') }}" class="btn btn-link text-decoration-none text-muted fw-semibold p-0">
                    <i class="bi bi-arrow-left me-1"></i> Back to Orders
                </a>
            </div>
            <div class="d-flex gap-2">
                <button type="button" class="btn btn-outline-primary btn-lg px-4 rounded-pill fw-bold" onclick="scrollToUpload()">
                    <i class="bi bi-cloud-upload me-1"></i> Upload More
                </button>
                <a href="{{ route('checkout.index') }}"
                   class="btn btn-success btn-lg px-5 rounded-pill fw-bold @if(empty($items)) disabled @endif"
                   @if(empty($items)) aria-disabled="true" tabindex="-1" @endif>
                    Proceed to Checkout <i class="bi bi-arrow-right ms-1"></i>
                </a>
            </div>
        </div>
    </div>

    <!-- Sticky Footer Mobile -->
    <div class="cart-sticky-footer d-md-none d-block shadow-lg">
        <div class="container d-flex flex-column gap-2">
            <div class="d-flex justify-content-between align-items-center mb-1">
                <a href="{{ route('account') }}" class="btn btn-link text-decoration-none text-muted fw-semibold p-0 small">
                    <i class="bi bi-arrow-left me-1"></i> Orders
                </a>
            </div>
            <div class="d-flex gap-2 w-100">
                <button type="button" class="btn btn-outline-primary btn-lg flex-grow-1 rounded-pill fw-bold" onclick="scrollToUpload()">
                    <i class="bi bi-cloud-upload"></i> Upload
                </button>
                <a href="{{ route('checkout.index') }}"
                   class="btn btn-success btn-lg flex-grow-1 rounded-pill fw-bold @if(empty($items)) disabled @endif"
                   @if(empty($items)) aria-disabled="true" tabindex="-1" @endif>
                    Checkout <i class="bi bi-arrow-right"></i>
                </a>
            </div>
        </div>
    </div>
</div>

    @push('styles')
    <style>
        .cart-sticky-footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: rgba(255, 255, 255, 1);
            border-top: 1px solid #dee2e6;
            padding: 1.25rem 0;
            z-index: 9999;
            box-shadow: 0 -8px 30px rgba(0,0,0,0.2);
            transition: opacity 0.3s ease-out;
        }

        .cart-sticky-footer.at-bottom {
            position: static !important;
            box-shadow: none;
            border-top: 1px solid #dee2e6;
            margin-bottom: 0;
            transform: none;
        }

        .main-content-container {
            padding-bottom: 50px !important;
            overflow: visible;
        }

        @media (max-width: 767.98px) {
            .main-content-container {
                padding-bottom: 20px !important;
                overflow: visible;
            }
            .cart-sticky-footer {
                padding: 1rem 0;
            }
        }

        .image-box {
            width: 100%;                  /* responsive to card width */
            aspect-ratio: 1 / 1;          /* always square */
            background:
                    linear-gradient(45deg,#eee 25%,transparent 25%),
                    linear-gradient(-45deg,#eee 25%,transparent 25%),
                    linear-gradient(45deg,transparent 75%,#eee 75%),
                    linear-gradient(-45deg,transparent 75%,#eee 75%);
            background-size:16px 16px;
            background-position:0 0,0 8px,8px -8px,-8px 0px;
            background-color: #f8f9fa;

            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;             /* crop oversized images */
            border-radius: .25rem;        /* same as Bootstrap rounded */
            border: 1px solid #dee2e6;    /* Bootstrap border color */
        }

        .image-box img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;          /* scale without cropping */
            image-rendering: -webkit-optimize-contrast; /* improved sharpness */
            transition: transform 0.3s ease;
        }

        .image-card:hover .image-box img {
            transform: scale(1.05);
        }

        .hover-bg-white:hover {
            background-color: #fff !important;
        }

        .cursor-pointer {
            cursor: pointer;
        }

        .transition-all {
            transition: all 0.3s ease;
        }

        #qa-search {
            max-width: 350px;
            height: 44px;
            font-size: 16px;
        }

        #qa-suggest.dropdown-menu {
            min-width: 350px!important;            /* make the menu wider */
            max-height: 60vh;            /* scroll if long */
            overflow-y: auto;
            padding: 8px;
            box-shadow: 0 8px 24px rgba(0,0,0,.2);
            border-radius: 10px;
        }

        .qa-s-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 10px;
            border-radius: 8px;
            line-height: 1.25;
            white-space: normal;         /* allow wrapping */
        }
        .qa-s-item:hover { background: rgba(13,110,253,.08); }

        .qa-thumb {
            width: 64px;
            height: 64px;
            object-fit: contain;
            background: #f8f9fa;
            border: 1px solid rgba(0,0,0,.06);
            border-radius: 8px;
            flex: 0 0 auto;
        }

        .qa-meta { flex: 1 1 auto; min-width: 0; }
        .qa-name { font-weight: 600; }
        .qa-sub  { font-size: 12px; color: #6c757d; margin-top: 2px; }

        .image-card .saving-indicator{
            position:absolute; inset:0; z-index:10;
            display:none; align-items:center; justify-content:center;
            background:rgba(255,255,255,.8); backdrop-filter: blur(2px);
            font-weight:600;
            transition: all 0.3s ease;
        }
        .image-card.saving .saving-indicator{ display:flex; }
        .image-card .saving-indicator .si-box{
            display:flex;
            align-items:center;
            gap:.5rem;
            background: white;
            padding: 10px 20px;
            border-radius: 50px;
            shadow: 0 4px 15px rgba(0,0,0,0.1);
        }

        .btn-xs {
            padding: .125rem .25rem;
            font-size: .75rem;
            line-height: 1.5;
            border-radius: .2rem;
        }

        .x-small {
            font-size: 0.75rem;
        }

        .letter-spacing-1 {
            letter-spacing: 1px;
        }
    </style>
    @endpush

    @push('scripts')
    <script>
        function scrollToUpload() {
            const uploadCard = document.getElementById('upload-card');
            if (uploadCard) {
                uploadCard.scrollIntoView({ behavior: 'smooth' });
            }
        }

        $(window).on('scroll', function() {
            const $stickies = $('.cart-sticky-footer');
            const $footer = $('footer');
            if (!$stickies.length || !$footer.length) return;

            const footerTop = $footer.offset().top;
            const windowBottom = $(window).scrollTop() + $(window).height();

            // Calculate the distance from the bottom of the viewport to the top of the footer
            const distanceToFooter = footerTop - windowBottom;

            // Trigger the transition when the footer starts becoming visible
            if (distanceToFooter <= 0) {
                $stickies.addClass('at-bottom');
            } else {
                $stickies.removeClass('at-bottom');
            }
        }).trigger('scroll');

        window.CART_CFG = {
            csrf_token: '{{ csrf_token() }}',
            csrf_token_name: '_token',
            order_id: '{{ $order_id }}',
            list_selector: '#img-grid',
            preflight_url: '{{ route('cart.preflight') }}',
            put_url: '/cart/put',
            status_url: '{{ route('cart.status') }}',
            my_images_url: '{{ route('cart.my_images') }}',
            use_saved_url: '{{ route('cart.use_saved') }}',
            save_image_url: '/cart/save',
            dupe_check_url: '{{ route('cart.dupe_check') }}',
            dupe_check_hash_url: '{{ route('cart.dupe_check_hash') }}',
            use_existing_url: '{{ route('cart.use_existing') }}'
        };
        window.UP_CFG = window.CART_CFG;
    </script>
    <script src="{{ asset('assets/js/cart/dtfimage-cards.js') }}?v={{ filemtime(public_path('assets/js/cart/dtfimage-cards.js')) }}&nocache={{ time() }}"></script>
    <script src="{{ asset('assets/js/cart/uploader.js') }}?v={{ filemtime(public_path('assets/js/cart/uploader.js')) }}"></script>
    <script src="{{ asset('assets/js/cart/editor.js') }}?v={{ filemtime(public_path('assets/js/cart/editor.js')) }}"></script>
    <script src="{{ asset('assets/js/cart/quick-add.js') }}?v={{ filemtime(public_path('assets/js/cart/quick-add.js')) }}"></script>
    <script src="{{ asset('assets/js/cart/auto-save.js') }}?v={{ filemtime(public_path('assets/js/cart/auto-save.js')) }}"></script>
    <script>
        (function () {
            const MIN = 0.25;
            const MAX = 60;

            const toNum = (v, d = 0) => {
                const n = parseFloat(v);
                return Number.isFinite(n) ? n : d;
            };
            const clamp = (n) => Math.min(MAX, Math.max(MIN, n));
            const fmt = (n) => String(clamp(Math.round(n * 1000) / 1000)).replace(/\.?0+$/, '');

            function getCard(el) {
                return el?.closest?.('.image-card') || null;
            }

            function getRatio(card) {
                const saved = parseFloat(card.dataset.lockRatio || '');
                if (Number.isFinite(saved) && saved > 0) return saved;

                const w = card.querySelector('.input-width');
                const h = card.querySelector('.input-height');
                const W = toNum(w?.value, 0);
                const H = toNum(h?.value, 0);
                if (H > 0) {
                    if (Math.abs(W - H) <= 0.001) return 1;
                    return W / H;
                }

                const dataRatio = parseFloat(card.dataset.ratio || '');
                return (Number.isFinite(dataRatio) && dataRatio > 0) ? dataRatio : 1;
            }

            function freezeRatio(card) {
                const w = card.querySelector('.input-width');
                const h = card.querySelector('.input-height');
                const W = toNum(w?.value, 0);
                const H = toNum(h?.value, 0);
                if (H > 0) {
                    const r = (Math.abs(W - H) <= 0.001) ? 1 : (W / H);
                    card.dataset.lockRatio = String(r);
                    card.dataset.ratio = String(r);
                }
            }

            // Lock toggle: set baseline ratio from current values.
            document.addEventListener('change', (e) => {
                const t = e.target;
                if (!(t instanceof HTMLInputElement) || !t.classList.contains('input-lock')) return;
                const card = getCard(t);
                if (!card) return;
                if (t.checked) freezeRatio(card);
            }, true);

            // Capture input before any other handler; trusted typing only.
            document.addEventListener('input', (e) => {
                const t = e.target;
                if (!(t instanceof HTMLInputElement)) return;
                if (!e.isTrusted) return;

                const isW = t.classList.contains('input-width');
                const isH = t.classList.contains('input-height');
                if (!isW && !isH) return;

                const card = getCard(t);
                if (!card) return;
                const lock = card.querySelector('.input-lock');
                const w = card.querySelector('.input-width');
                const h = card.querySelector('.input-height');
                if (!lock || !w || !h || !lock.checked) return;

                const ratio = getRatio(card);
                if (!(ratio > 0)) return;

                if (isW) {
                    const W = toNum(w.value, MIN);
                    h.value = fmt(W / ratio);
                } else {
                    const H = toNum(h.value, MIN);
                    w.value = fmt(H * ratio);
                }

                // Prevent conflicting listeners from overwriting this result.
                e.stopImmediatePropagation();
            }, true);

            // Initialize lock baseline for existing and newly added cards.
            function initLockBaselines(root = document) {
                root.querySelectorAll('.image-card').forEach((card) => {
                    const lock = card.querySelector('.input-lock');
                    if (lock && lock.checked) freezeRatio(card);
                });
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => initLockBaselines());
            } else {
                initLockBaselines();
            }

            window.addEventListener('dtfimage:card-added', (ev) => {
                const card = ev?.detail?.el?.querySelector?.('.image-card') || ev?.detail?.el;
                if (!card || !(card instanceof HTMLElement)) return;
                initLockBaselines(card.parentElement || card);
            });
        })();
    </script>
    @endpush
</x-app-layout>
