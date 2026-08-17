<x-app-layout>
    <div class="container my-5 pb-5">
        <div class="mb-5 text-center">
            <h1 class="font-blinker display-5 fw-bold text-dark mb-2">Team Customization</h1>
            <p class="text-muted lead">Personalize jerseys, kits, and gear with custom names and numbers in bulk.</p>
        </div>

        <style>
            .tc-section-card {
                border: none;
                border-radius: 1rem;
                box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
                transition: box-shadow 0.3s ease;
                margin-bottom: 1.5rem;
            }

            .tc-section-card:hover {
                box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.1);
            }

            .tc-section-header {
                background-color: #fff;
                border-bottom: 1px solid #e9ecef;
                padding: 1.25rem 1.5rem;
                border-top-left-radius: 1rem !important;
                border-top-right-radius: 1rem !important;
            }

            .tc-section-header h3 {
                margin-bottom: 0;
                font-weight: 700;
                color: #212529;
                font-size: 1.25rem;
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }

            .tc-section-body {
                padding: 1.5rem;
            }

            /* Template Grid Improvements */
            .tc-tpl-card {
                cursor: pointer;
                transition: all 0.2s ease-in-out;
                border-radius: 0.75rem;
                border: 2px solid transparent;
                overflow: hidden;
                height: 100%;
                position: relative;
            }

            .tc-tpl-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
            }

            .tc-tpl-card.selected {
                border-color: #0d6efd;
                background-color: rgba(13, 110, 253, 0.02);
            }

            .tc-tpl-card.selected::after {
                content: "\F26A";
                font-family: "bootstrap-icons";
                position: absolute;
                top: 10px;
                right: 10px;
                background: #0d6efd;
                color: #fff;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.8rem;
                z-index: 2;
            }

            .tc-tpl-img-container {
                position: relative;
                background: #f1f3f5;
                padding: 1rem;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .tc-tpl-card.selected .tc-tpl-img-container {
                background: rgba(13, 110, 253, 0.05);
            }

            .tc-tpl-name {
                font-weight: 700;
                font-size: 0.95rem;
                color: #343a40;
                margin-bottom: 0.25rem;
            }

            .tc-tpl-desc {
                font-size: 0.85rem;
                color: #6c757d;
                line-height: 1.4;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
                height: 2.8em;
            }

            /* Table Modernization */
            .tc-modern-table {
                border-collapse: separate;
                border-spacing: 0 0.5rem;
            }

            .tc-modern-table thead th {
                border: none;
                color: #6c757d;
                text-transform: uppercase;
                font-size: 0.75rem;
                font-weight: 700;
                letter-spacing: 0.05em;
                padding: 0.75rem 1rem;
            }

            .tc-modern-table tbody tr {
                background: #fff;
                box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.05);
                transition: all 0.2s ease;
            }

            .tc-modern-table tbody tr:hover {
                transform: scale(1.005);
                box-shadow: 0 0.25rem 0.5rem rgba(0, 0, 0, 0.08);
            }

            .tc-modern-table td {
                padding: 1rem;
                border: none;
            }

            .tc-modern-table td:first-child { border-top-left-radius: 0.5rem; border-bottom-left-radius: 0.5rem; }
            .tc-modern-table td:last-child { border-top-right-radius: 0.5rem; border-bottom-right-radius: 0.5rem; }

            /* Block Controls */
            #tc-block-rows td { vertical-align: middle; }
            .btn-group-modern {
                background: #f8f9fa;
                padding: 0.25rem;
                border-radius: 0.75rem;
                display: inline-flex;
            }

            .btn-group-modern .btn {
                border: none;
                padding: 0.375rem 0.75rem;
                font-size: 0.875rem;
                font-weight: 600;
                border-radius: 0.5rem !important;
                color: #6c757d;
                transition: all 0.2s ease;
            }

            .btn-group-modern .btn.active {
                background: #fff;
                color: #0d6efd;
                box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.1);
            }

            /* Color Swatch Button */
            .nl-cc-btn {
                display: inline-flex;
                align-items: center;
                gap: 0.75rem;
                padding: 0.5rem 1rem;
                border-radius: 0.75rem;
                border: 1px solid #e9ecef;
                background: #fff;
                transition: all 0.2s ease;
                font-weight: 600;
                font-size: 0.875rem;
                color: #495057;
            }

            .nl-cc-btn:hover {
                border-color: #0d6efd;
                background: #f8f9fa;
            }

            .nl-cc-swatch {
                width: 20px;
                height: 20px;
                border-radius: 6px;
                border: 1px solid rgba(0,0,0,0.1);
            }

            /* Progress Area */
            .tc-progress-container {
                background: #fff;
                padding: 1.5rem;
                border-radius: 1rem;
                border: 1px solid #e9ecef;
            }

            .progress-modern {
                height: 0.75rem;
                border-radius: 1rem;
                background: #f8f9fa;
                overflow: hidden;
            }

            .progress-bar-modern {
                background: linear-gradient(90deg, #0d6efd, #0dcaf0);
                transition: width 0.4s ease;
            }

            /* Helper Classes */
            .font-blinker { font-family: 'Blinker', sans-serif; }
        </style>

        {{-- Step 1: Select Template --}}
        <div class="tc-section-card card">
            <div class="tc-section-header card-header">
                <h3><i class="bi bi-layout-three-columns text-primary"></i> 1. Choose a Template</h3>
            </div>
            <div class="tc-section-body card-body">
                <div id="tc-templates-grid" class="row row-cols-2 row-cols-md-3 row-cols-lg-4 row-cols-xl-6 g-3">
                    @if(isset($templates) && $templates->count() > 0)
                        @foreach($templates as $t)
                            @php
                                $tpl_id = $t->id;
                                $tpl_name = $t->public_name ?: ($t->name ?: "Template #{$t->id}");
                                $tpl_desc = $t->description ?: '';
                                $tpl_img = $t->preview_url ?: ($t->preview ?: ($t->preview_image ?: ($t->thumb ?: '')));
                            @endphp

                            <div class="col">
                                <div class="tc-tpl-card card {{ request('tpl') == $tpl_id ? 'selected' : '' }}"
                                     data-id="{{ $tpl_id }}" tabindex="0" role="button">
                                    <div class="tc-tpl-img-container ratio ratio-4x3">
                                        @if($tpl_img != '')
                                            <img src="{{ $tpl_img }}" alt="{{ $tpl_name }}" class="img-fluid object-fit-contain">
                                        @else
                                            <div class="text-muted small d-flex flex-column align-items-center">
                                                <i class="bi bi-image fs-2 mb-1"></i>
                                                <span>No preview</span>
                                            </div>
                                        @endif
                                    </div>
                                    <div class="card-body p-3">
                                        <div class="tc-tpl-name text-truncate">{{ $tpl_name }}</div>
                                        @if($tpl_desc != '')
                                            <p class="tc-tpl-desc text-muted mb-0 text-truncate-2">{{ $tpl_desc }}</p>
                                        @endif
                                    </div>
                                </div>
                            </div>
                        @endforeach
                    @else
                        <div class="col-12"><div class="alert alert-light border shadow-none text-center py-4">No templates available.</div></div>
                    @endif
                </div>
                <select id="tc-template" class="form-select d-none" aria-hidden="true">
                    <option value="">Select a template…</option>
                    @foreach($templates as $t)
                        <option value="{{ $t->id }}" {{ request('tpl') == $t->id ? 'selected' : '' }}>
                            {{ $t->public_name ?: ($t->name ?: "Template #{$t->id}") }}
                        </option>
                    @endforeach
                </select>
            </div>
        </div>

        <div class="row g-4 mb-5">
            {{-- Step 2: Customization --}}
            <div class="col-lg-12">
                <div class="tc-section-card card h-100">
                    <div class="tc-section-header card-header">
                        <h3><i class="bi bi-palette text-primary"></i> 2. Style Options</h3>
                    </div>
                    <div class="tc-section-body card-body">
                        <!-- Per-Block Customization -->
                        <div class="mb-4">
                            <h5 class="fw-bold mb-3 small text-uppercase text-muted tracking-wide">Colors & Modes</h5>
                            <div class="table-responsive">
                                <table class="table tc-modern-table align-middle">
                                    <thead>
                                        <tr>
                                            <th>Block</th>
                                            <th>Outline Mode</th>
                                            <th>Colors</th>
                                        </tr>
                                    </thead>
                                    <tbody id="tc-block-rows">
                                        {{-- Populated by JS --}}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- Fonts per block -->
                        <div>
                            <h5 class="fw-bold mb-3 small text-uppercase text-muted tracking-wide">Typography</h5>
                            <div class="table-responsive">
                                <table class="table tc-modern-table align-middle">
                                    <thead>
                                        <tr>
                                            <th style="width:150px;">Block</th>
                                            <th>Font Selection</th>
                                        </tr>
                                    </thead>
                                    <tbody id="tc-font-rows">
                                        {{-- Populated by JS --}}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        {{-- Step 3: Data Entry (renamed to 3) --}}
        <div class="tc-section-card card mb-5">
            <div class="tc-section-header card-header d-flex justify-content-between align-items-center">
                <h3><i class="bi bi-database text-primary"></i> 3. Customization Data</h3>
                <div class="d-flex gap-2">
                    <button type="button" id="tc-add-row-inline" class="btn btn-sm btn-outline-primary" disabled>
                        <i class="bi bi-plus-lg me-1"></i> Add Row
                    </button>
                    <button id="tc-import-csv" class="btn btn-sm btn-outline-primary" data-bs-toggle="offcanvas" data-bs-target="#offcanvas-csv" disabled>
                        <i class="bi bi-file-earmark-arrow-up me-1"></i> Import CSV
                    </button>
                    <button type="button" id="tc-delete-all" class="btn btn-sm btn-outline-danger" disabled>
                        <i class="bi bi-trash3 me-1"></i> Clear All
                    </button>
                </div>
            </div>
            <div class="tc-section-body card-body">
                <div id="tc-grid-empty" class="text-center py-5">
                    <div class="text-muted mb-3">
                        <i class="bi bi-table fs-1 opacity-25"></i>
                    </div>
                    <p class="text-muted mb-0">Select a template above to generate the data entry grid.</p>
                </div>
                <div id="tc-grid" class="table-responsive" style="display:none;">
                    <table class="table table-hover align-middle">
                        <thead id="tc-grid-head" class="table-light text-uppercase small fw-bold tracking-wider text-muted"></thead>
                        <tbody id="tc-grid-body"></tbody>
                    </table>
                </div>
            </div>
        </div>

        {{-- Step 4: Summary & Batch (renamed to 4) --}}
        <div class="tc-section-card card mb-5">
            <div class="tc-section-header card-header">
                <h3><i class="bi bi-rocket-takeoff text-primary"></i> 4. Batch Action</h3>
            </div>
            <div class="tc-section-body card-body">
                <div class="row align-items-center">
                    <div class="col-md-6">
                        <div class="tc-progress-container mb-3 mb-md-0">
                            <label class="form-label fw-bold mb-2 small text-muted text-uppercase">Batch Progress</label>
                            <div class="progress progress-modern mb-2">
                                <div class="progress-bar progress-bar-modern" id="tc-progress" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span class="small text-muted" id="tc-progress-text">0% complete</span>
                                <span class="small text-primary fw-bold" id="tc-status-badge">Idle</span>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="d-grid gap-2 d-md-flex justify-content-md-end align-items-center">
                            <div class="text-md-end me-md-3 mb-2 mb-md-0">
                                <span class="small text-muted d-block">Finished items will be</span>
                                <span class="small fw-bold text-dark">added to your cart automatically.</span>
                            </div>
                            <button id="tc-preview" class="btn btn-outline-primary btn-lg fw-bold px-4" disabled>
                                <i class="bi bi-eye me-2"></i> Preview Selected
                            </button>
                            <button id="tc-run" class="btn btn-primary btn-lg fw-bold px-5" disabled>
                                <i class="bi bi-cart-plus me-2"></i> Add Batch to Cart
                            </button>
                        </div>
                    </div>
                </div>

                <div class="mt-4 overflow-auto" style="max-height: 200px; border-top: 1px solid #eee;">
                    <ul id="tc-log" class="list-group list-group-flush small"></ul>
                </div>
            </div>
        </div>

        {{-- Step 5: CSV Import (Hidden by default) --}}
        <div class="offcanvas offcanvas-top csv-offcanvas"
             tabindex="-1"
             id="offcanvas-csv"
             aria-labelledby="offcanvasCsvLabel"
             style="--bs-offcanvas-height: 100vh;">
            <div class="offcanvas-header">
                <h5 class="offcanvas-title fw-bold" id="offcanvasCsvLabel"><i class="bi bi-filetype-csv me-2 text-primary"></i>CSV Import & Mapping</h5>
                <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
            </div>

            <div class="offcanvas-body overflow-auto">
                <div class="card border-0 bg-light mb-4">
                    <div class="card-body">
                        <div class="row g-3 align-items-center">
                            <div class="col-md-auto">
                                <label for="csv-file" class="form-label fw-bold small text-muted text-uppercase mb-0">Upload CSV File</label>
                            </div>
                            <div class="col-md-4">
                                <input class="form-control" type="file" id="csv-file" accept=".csv,text/csv">
                            </div>
                            <div class="col-md-auto d-flex gap-2">
                                <button class="btn btn-outline-secondary" id="csv-sample" type="button">
                                    <i class="bi bi-file-earmark-spreadsheet me-1"></i> Download Sample
                                </button>
                                <button class="btn btn-success px-4" id="csv-add-selected" type="button">
                                    <i class="bi bi-plus-circle me-1"></i> Import Selected Rows
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div id="csv-map-wrap" class="mb-4" style="display:none;">
                    <h6 class="fw-bold mb-3"><i class="bi bi-arrow-left-right me-2 text-primary"></i>Map CSV columns to placeholders</h6>
                    <div class="table-responsive">
                        <table class="table table-sm tc-modern-table align-middle mb-0">
                            <thead>
                            <tr>
                                <th>Placeholder</th>
                                <th>CSV Column</th>
                            </tr>
                            </thead>
                            <tbody id="csv-map-body"></tbody>
                        </table>
                    </div>
                </div>

                <div class="table-responsive rounded-3 border">
                    <table class="table table-hover align-middle mb-0" id="csv-preview-table">
                        <thead class="table-light"></thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
        </div>

        {{-- Offcanvas: Color Picker (right/end) --}}
        <div class="offcanvas offcanvas-end"
             tabindex="-1"
             id="offcanvas-colors"
             aria-labelledby="offcanvasColorsLabel"
             style="--bs-offcanvas-width: 50vw;">
            <div class="offcanvas-header">
                <h5 class="offcanvas-title" id="offcanvasColorsLabel">Choose Color</h5>
                <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
            </div>
            <div class="offcanvas-body">
                <div id="nl-cc-offcanvas-container"></div>
            </div>
        </div>
    </div>

    @push('scripts')
        <script>
            window.__TCFG = {
                urls: {
                    progress: '{{ route('teamcustomization.progress') }}',
                    templates: '{{ route('teamcustomization.templates') }}',
                    template: '{{ route('teamcustomization.template', ['id' => 'PLACEHOLDER']) }}'.replace('PLACEHOLDER', ''),
                    fonts: '{{ route('teamcustomization.fonts') }}',
                    preview: '{{ route('teamcustomization.preview') }}',
                    runOne: '{{ route('teamcustomization.run_one') }}',
                    validateCsv: '{{ route('teamcustomization.validate_csv') }}',
                    colors: '{{ route('teamcustomization.colors') }}'
                }
            };
        </script>
        <script src="{{ asset('assets/js/teamcustomizations/colors.js') }}"></script>
        <script src="{{ asset('assets/js/teamcustomizations/templatecards.js') }}"></script>
        <script src="{{ asset('assets/js/teamcustomizations/index.js') }}?v={{ filemtime(public_path('assets/js/teamcustomizations/index.js')) }}"></script>
    @endpush
</x-app-layout>
