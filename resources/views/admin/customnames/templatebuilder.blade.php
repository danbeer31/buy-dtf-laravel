<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Template Builder') }}
        </h2>
    </x-slot>

    <style>
        /* Widen the block table selects */
        .blocks-table select.form-select { min-width: 140px; }
        .blocks-table .b-slot,
        .blocks-table .b-type,
        .blocks-table .b-align { min-width: 160px !important; }

        .pv-box{
            position:relative; background:#f1f3f5; border:1px dashed #cbd3da;
            min-height:240px; display:flex; align-items:center; justify-content:center;
            overflow:hidden; border-radius:.25rem;
        }
        .pv-box.loading{ filter:grayscale(.6); }
        .pv-placeholder{ color:#6c757d; font-size:.95rem; }
        .pv-spinner{
            position:absolute; width:48px; height:48px; border:4px solid rgba(0,0,0,.1);
            border-top-color:rgba(0,0,0,.45); border-radius:50%;
            animation: pvspin 1s linear infinite;
        }
        @keyframes pvspin { to { transform: rotate(360deg); } }
        .d-none{ display:none !important; }

        /* Data panel basics (JS will inject rows) */
        #data-rows .row { margin-bottom: 6px; }
        .data-key { width: 40%; }
        .data-val { width: 60%; }
        .data-actions { white-space: nowrap; }
        .help-hint { color:#6c757d; font-size: .95rem; }
    </style>

    <section class="container my-4" id="tpl-builder">
        <div id="tb-alert" class="alert d-none" role="alert"></div>

        {{-- --- Top row: JSON (left) + Fields & Preview (right) --- --}}
        <div class="row g-3">
            {{-- Left: JSON editor --}}
            <div class="col-md-6">
                <div class="card shadow-sm">
                    <div class="card-header d-flex align-items-center justify-content-between bg-white py-3">
                        <div class="d-flex align-items-center">
                            <label for="tb-slug" class="form-label mb-0 me-2 fw-semibold">Slug</label>
                            <input type="text" id="tb-slug" class="form-control form-control-sm d-inline-block"
                                   style="width:260px" value="{{ $initialSlug }}">
                        </div>
                        <div class="ms-auto">
                            <button id="tb-load" class="btn btn-sm btn-outline-secondary me-1">Load</button>
                            <button id="tb-save" class="btn btn-sm btn-primary me-1">Save</button>
                            <button id="tb-saveas" class="btn btn-sm btn-outline-primary me-1">Save As</button>
                            <button id="tb-delete" class="btn btn-sm btn-outline-danger">Delete</button>
                        </div>
                    </div>
                    <div class="card-body p-0">
                        <textarea id="tb-json" class="form-control border-0 rounded-0"
                                  style="min-height:520px;font-family:monospace;"></textarea>
                    </div>
                </div>
            </div>

            {{-- Right: Fields + Preview --}}
            <div class="col-md-6">
                <div class="card mb-3 shadow-sm border-0">
                    <div class="card-header bg-white fw-bold">General Fields</div>
                    <div class="card-body">
                        <div class="row g-2">
                            <div class="col-4">
                                <label class="form-label small text-muted">Width (in)</label>
                                <input type="number" step="0.01" id="f-widthIn" class="form-control form-control-sm">
                            </div>
                            <div class="col-4">
                                <label class="form-label small text-muted">Height (in)</label>
                                <input type="number" step="0.01" id="f-heightIn" class="form-control form-control-sm">
                            </div>
                            <div class="col-4">
                                <label class="form-label small text-muted">DPI</label>
                                <input type="number" id="f-dpi" class="form-control form-control-sm">
                            </div>
                        </div>

                        <hr>

                        <div class="row g-2">
                            <div class="col-6">
                                <label class="form-label small text-muted">Scaling (name, number)</label>
                                <div class="input-group input-group-sm">
                                    <input type="number" step="0.01" id="f-scale-name" class="form-control"
                                           placeholder="name">
                                    <input type="number" step="0.01" id="f-scale-number" class="form-control"
                                           placeholder="number">
                                </div>
                                <div class="form-check mt-1">
                                    <input class="form-check-input" type="checkbox" id="f-scale-stroke" checked>
                                    <label class="form-check-label small" for="f-scale-stroke">Scale Stroke</label>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {{-- Preview --}}
                <div class="card shadow-sm border-0">
                    <div class="card-header d-flex align-items-center justify-content-between bg-white fw-bold">
                        <span>Preview</span>
                        <div>
                            <button id="pv-run" class="btn btn-sm btn-outline-primary">Run Preview</button>
                        </div>
                    </div>
                    <div class="card-body">
                        <div id="pv-wrap" class="pv-box text-center">
                            <div class="pv-placeholder">No preview yet</div>
                            <div class="pv-spinner d-none" aria-label="Loading"></div>
                            <img id="pv-img" alt="preview" class="d-none" style="max-width:100%;height:auto;">
                        </div>
                        <div class="form-check mt-2">
                            <input class="form-check-input" type="checkbox" id="debug">
                            <label class="form-check-label small" for="debug">
                                Debug (show squeeze details)
                            </label>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        {{-- Full-width row: Blocks --}}
        <div class="row g-3 mt-1">
            <div class="col-12">
                <div class="card shadow-sm border-0">
                    <div class="card-header d-flex align-items-center justify-content-between bg-white fw-bold">
                        <span>Blocks</span>
                        <button class="btn btn-sm btn-outline-secondary" id="f-add-block">Add Block</button>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-sm blocks-table align-middle">
                                <thead>
                                <tr>
                                    <th style="width:22%">Slot</th>
                                    <th style="width:12%">Type</th>
                                    <th style="width:20%">Value</th>
                                    <th style="width:16%">Pos</th>
                                    <th style="width:12%">Size</th>
                                    <th style="width:12%">More / Fit</th>
                                    <th style="width:6%"></th>
                                </tr>
                                </thead>
                                <tbody id="f-block-rows"></tbody>
                            </table>
                            <div class="help-hint mt-2">
                                For <em>label</em> blocks, <code>fitWidthPx</code> or <code>fitBox.leftPx/rightPx</code> already affect rendering.
                                For <em>text</em> blocks, the fields will be saved now and take effect after we add the small server patch.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    @push('scripts')
    <script>
        window.__TB_URLS = {
            get: '{{ $ajaxGetUrl }}',
            save: '{{ $ajaxSaveUrl }}',
            create: '{{ $ajaxCreateUrl }}',
            del: '{{ $ajaxDeleteUrl }}',
            reload: '{{ $ajaxReloadUrl }}',
            fonts: '{{ $ajaxFontsUrl }}',
            preview: '{{ $ajaxPreviewUrl }}'
        };
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        // Wrap fetch to include CSRF token
        const originalFetch = window.fetch;
        window.fetch = function() {
            let [resource, config] = arguments;
            if (config && (config.method === 'POST' || config.method === 'PUT' || config.method === 'DELETE' || config.method === 'PATCH')) {
                config = config || {};
                config.headers = config.headers || {};
                if (!(config.body instanceof FormData)) {
                    config.headers['Content-Type'] = config.headers['Content-Type'] || 'application/json';
                }
                config.headers['X-CSRF-TOKEN'] = csrfToken;
                config.headers['Accept'] = 'application/json';
            }
            return originalFetch(resource, config);
        };
    </script>
    <script src="{{ asset('assets/js/admin/customnames/templatebuilder.js') }}"></script>
    @endpush
</x-app-layout>
