<x-app-layout>
    <x-slot name="header">
        <h2 class="font-semibold text-xl text-gray-800 leading-tight">
            {{ __('Your DTF Image Order') }}
        </h2>
    </x-slot>

    <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg p-6">

                <div class="d-flex align-items-center justify-content-between mb-3">
                    <h1 class="h2 m-0">Your DTF Image Order</h1>

                    <div class="d-flex align-items-center gap-2">
                        <div class="position-relative">
                            <input id="qa-search" class="form-control form-control-sm" type="search"
                                   placeholder="Search your past images…" autocomplete="off" style="min-width:260px;">
                            <div id="qa-suggest" class="dropdown-menu dropdown-menu-end w-100"></div>
                        </div>
                        <button id="qa-browse" type="button" class="btn btn-sm btn-outline-primary">
                            Saved Images
                        </button>
                    </div>
                </div>
                <p class="text-muted">Adjust quantity, width &amp; height (keeps proportions by default), name, and notes.</p>

                @if(empty($items))
                    <div id="no-images-alert" class="alert alert-info">No images found on your open order.</div>
                @endif

                <div id="img-grid" class="row g-3" data-order-id="{{ $order_id }}">
                    @foreach($items as $it)
                        @include('cart._dtfimage_card', ['it' => $it])
                    @endforeach
                </div>

                <div class="col-12 mt-2 text-end">
                    <div class="text-end mt-4">
                        <a href="{{ route('orders.place', $order_id) }}"
                           class="btn btn-success @if(empty($items)) disabled @endif"
                           @if(empty($items)) aria-disabled="true" tabindex="-1" @endif>
                            Place order
                        </a>
                        <a href="{{ route('account') }}" class="btn btn-secondary">
                            <i class="fa fa-arrow-circle-left"></i> Back to Orders
                        </a>
                    </div>
                </div>

                <div class="col-12 col-lg-10 mx-auto mt-5 font-blinker pb-5">
                    <div id="upload-card" class="card shadow-sm rounded-0">
                        <div class="card-body bg-light">
                            <div class="h4 mb-3 fs-3">Upload Your DTF Files</div>
                            <p class="text-muted fs-5 font-blinker">
                                Accepted: <span class="badge bg-success">PNG</span>,
                                <span class="badge bg-success">SVG</span>,
                                <span class="badge bg-success">PDF</span>.
                                We auto-trim whitespace, clean semi-transparent pixels, and set 300 DPI.
                            </p>

                            <div id="drop-area"
                                 class="border border-2 border-dashed rounded-3 p-5 text-center bg-white border-primary" style="border-style: dashed !important;">
                                <p class="mb-3 fs-2 font-barlow fw-semibold">Drag &amp; drop files here</p>
                                <button id="pick-btn" type="button" class="btn btn-primary">Click to Select files</button>
                                <div class="small text-muted mt-2 fs-5">You can also paste a PNG from your clipboard.</div>
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

    @push('styles')
    <style>
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
            position:absolute; inset:0; z-index:5;
            display:none; align-items:center; justify-content:center;
            background:rgba(255,255,255,.7); backdrop-filter:saturate(120%) blur(1px);
            font-weight:600;
        }
        .image-card.saving .saving-indicator{ display:flex; }
        .image-card .saving-indicator .si-box{ display:flex; align-items:center; gap:.5rem; }
    </style>
    @endpush

    @push('scripts')
    <script>
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
    <script src="{{ asset('assets/js/cart/dtfimage-cards.js') }}"></script>
    <script src="{{ asset('assets/js/cart/uploader.js') }}"></script>
    <script src="{{ asset('assets/js/cart/editor.js') }}"></script>
    <script src="{{ asset('assets/js/cart/quick-add.js') }}"></script>
    <script src="{{ asset('assets/js/cart/auto-save.js') }}"></script>
    @endpush
</x-app-layout>
