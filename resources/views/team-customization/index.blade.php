<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Team Customization') }}
        </h2>
    </x-slot>

    <style>
        /* ---------- Per-block controls (Block | Mode | Colors/Controls) ---------- */
        #tc-block-rows td {
            vertical-align: middle;
        }

        #tc-block-rows .btn-group .btn {
            text-transform: capitalize;
            padding: .25rem .5rem;
            border-radius: .5rem;
        }

        #tc-block-rows .btn-group .btn:not(.active):hover {
            background: rgba(0, 0, 0, .03);
        }

        #tc-block-rows .nl-cc-cell > .btn.btn-outline-secondary.btn-sm {
            display: inline-flex;
            align-items: center;
            gap: .5rem;
            border-radius: .6rem;
            padding: .25rem .5rem;
        }

        #tc-block-rows .nl-cc-cell > .btn span:first-child {
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid #d1d5db;
        }

        #tc-block-rows .form-control.form-control-sm[type="number"] {
            max-width: 120px;
        }

        /* ---------- Color offcanvas palette (right) ---------- */
        #offcanvas-colors .offcanvas-title {
            font-size: 1rem;
        }

        #offcanvas-colors .btn-light {
            background: #fff;
        }

        #offcanvas-colors .btn-light:hover {
            box-shadow: 0 4px 14px rgba(0, 0, 0, .08);
            transform: translateY(-1px);
        }
        /* ---------- CSV offcanvas (top) ---------- */
        .csv-offcanvas .offcanvas-body {
            padding-top: .25rem;
        }

        /* Sticky header for the preview table */
        #csv-preview-table thead th {
            position: sticky;
            top: 0;
            background: var(--bs-body-bg);
            z-index: 1;
            box-shadow: inset 0 -1px 0 rgba(0, 0, 0, .06);
        }

        #csv-preview-table thead th:first-child,
        #csv-preview-table tbody td:first-child {
            text-align: center;
            width: 46px;
            vertical-align: middle;
        }

        /* Readability */
        #csv-preview-table tbody tr:nth-child(odd) {
            background: rgba(0, 0, 0, .02);
        }

        #csv-preview-table tbody tr:hover {
            background: rgba(0, 0, 0, .05);
        }

        /* Mapping table spacing (above preview) */
        #csv-map-wrap table td:first-child {
            white-space: nowrap;
            width: 220px;
        }

        #csv-map-wrap select.form-select-sm {
            max-width: 340px;
        }

        /* Tiny SVG preview frame (static svg blocks) */
        .svg-preview, .svg-preview img {
            border-radius: .5rem;
        }
        .tc-tpl-card { cursor:pointer; transition:.15s ease; border-radius:.75rem; }
        .tc-tpl-card:hover { transform:translateY(-1px); box-shadow:0 .5rem 1rem rgba(0,0,0,.08); }
        .tc-tpl-card.selected { border-color:var(--bs-primary)!important; box-shadow:0 0 0 .25rem rgba(var(--bs-primary-rgb), .15); }
        .tc-tpl-img { background:#f8f9fa; display:flex; align-items:center; justify-content:center; border-bottom:1px solid rgba(0,0,0,.06); }
        .tc-tpl-img img { max-width:100%; max-height:100%; object-fit:contain; }
        .tc-tpl-name { font-weight:600; }
        .tc-tpl-desc { min-height:2.6em; }
    </style>

    <div class="container my-4 pb-5">
        <div class="d-flex align-items-center justify-content-between mb-3">
            <div class="font-blinker fs-1 fw-semibold mb-0">Team Customization</div>
        </div>

        <div class="card mb-3 font-blinker">
            <div class="card-body">
                <!-- Top controls -->
                <div class="row g-3 align-items-end">
                    <div class="col-12">
                        <label class="form-label">Template</label>

                        <div id="tc-templates-grid" class="row row-cols-1 row-cols-sm-2 row-cols-md-4 row-cols-xl-6 g-3">
                            @if(isset($templates) && $templates->count() > 0)
                                @foreach($templates as $t)
                                    @php
                                        $tpl_id = $t->id;
                                        $tpl_name = $t->public_name ?: ($t->name ?: "Template #{$t->id}");
                                        $tpl_desc = $t->description ?: '';
                                        $tpl_img = $t->preview_url ?: ($t->preview ?: ($t->preview_image ?: ($t->thumb ?: '')));
                                    @endphp

                                    <div class="col">
                                        <div class="card h-100 border tc-tpl-card {{ request('tpl') == $tpl_id ? 'selected' : '' }}"
                                             data-id="{{ $tpl_id }}" tabindex="0" role="button" aria-label="Choose {{ $tpl_name }}">
                                            <div class="tc-tpl-img ratio ratio-4x3">
                                                @if($tpl_img != '')
                                                    <img src="{{ $tpl_img }}" alt="{{ $tpl_name }}">
                                                @else
                                                    <div class="text-muted small d-flex align-items-center justify-content-center">No preview</div>
                                                @endif
                                            </div>
                                            <div class="card-body">
                                                <div class="tc-tpl-name text-truncate">{{ $tpl_name }}</div>
                                                @if($tpl_desc != '')<p class="tc-tpl-desc small text-muted mb-0">{{ $tpl_desc }}</p>@endif
                                            </div>
                                        </div>
                                    </div>
                                @endforeach
                            @else
                                <div class="col"><div class="text-muted">No templates available.</div></div>
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

                        <div class="form-text">Click a card to select a template.</div>
                    </div>
                </div>

                <!-- Per-Block Customization -->
                <div class="row g-3 mt-3">
                    <div class="col-12">
                        <div class="card" id="tc-quick" style="">
                            <div class="card-header font-blinker fs-3 fw-semibold">Block Customization</div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-sm align-middle mb-0">
                                        <thead>
                                        <tr>
                                            <th style="width:200px;">Block</th>
                                            <th style="width:260px;">Outline Type</th>
                                            <th>Colors</th>
                                        </tr>
                                        </thead>
                                        <tbody id="tc-block-rows">
                                        </tbody>
                                    </table>
                                </div>
                                <div class="form-text mt-2">
                                    Modes: <strong>Fill</strong> (just fill), <strong>Outline</strong> (fill + outline),
                                    <strong>Outline 2</strong> (fill + outline + outline2), <strong>Ring</strong> (fill +
                                    ring; outlines disabled).
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Fonts per block -->
                <div class="row g-3 mt-3">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header font-blinker fs-3 fw-semibold">Block Fonts</div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-sm align-middle mb-0">
                                        <thead>
                                        <tr>
                                            <th style="width:200px;">Block</th>
                                            <th>Font</th>
                                        </tr>
                                        </thead>
                                        <tbody id="tc-font-rows">
                                        </tbody>
                                    </table>
                                </div>
                                <div class="form-text">Defaults come from the template; override per block as needed.</div>
                            </div>
                        </div>
                    </div>
                </div>

            </div> <!-- /.card-body -->
        </div> <!-- /.card -->

        <div class="card mb-3">
            <div class="card-header font-blinker fs-3 fw-semibold"> Customization Data</div>
            <div class="card-body">
                <div id="tc-grid-empty" class="text-muted">Choose a template to generate placeholder columns.</div>
                <div id="tc-grid" class="table-responsive" style="display:none;">
                    <table class="table table-sm align-middle">
                        <thead id="tc-grid-head"></thead>
                        <tbody id="tc-grid-body"></tbody>
                    </table>
                </div>
                <div class="text-end mt-4">
                    <button type="button" id="tc-add-row-inline" class="btn btn-outline-primary" disabled>
                        <i class="bi bi-database-add fs-4"></i> Add row
                    </button>
                    <button id="tc-import-csv"
                            class="btn btn-outline-primary"
                            data-bs-toggle="offcanvas"
                            data-bs-target="#offcanvas-csv"
                            aria-controls="offcanvas-csv"
                            disabled>
                        <i class="bi bi-filetype-csv fs-4"></i> Import CSV
                    </button>
                    <button type="button" id="tc-delete-all" class="btn btn-outline-danger" disabled>
                        <i class="bi bi-trash fs-4"></i> Delete all
                    </button>
                </div>
            </div>
        </div>


        <div class="card">
            <div class="card-header font-blinker fs-3 fw-semibold">Progress</div>
            <div class="card-body">
                <div class="progress mb-2">
                    <div class="progress-bar" id="tc-progress" style="width:0%;">0%</div>
                </div>
                <ul id="tc-log" class="list-group small"></ul>
            </div>
            <div class="card-footer text-end">
                <button id="tc-preview" class="btn btn-outline-secondary" disabled>
                    <i class="bi bi-easel fs-4"></i> Preview Selected
                </button>
                <button id="tc-run" class="btn btn-primary" disabled>
                    <i class="bi bi-file-earmark-play fs-4"></i> Run Batch
                </button>
            </div>
        </div>

        {{-- Offcanvas: CSV Import (from top) --}}
        <div class="offcanvas offcanvas-top csv-offcanvas"
             tabindex="-1"
             id="offcanvas-csv"
             aria-labelledby="offcanvasCsvLabel"
             style="--bs-offcanvas-height: 100vh;">
            <div class="offcanvas-header">
                <h5 class="offcanvas-title" id="offcanvasCsvLabel">CSV Import</h5>
                <button type="button" class="btn-close text-reset" data-bs-dismiss="offcanvas" aria-label="Close"></button>
            </div>

            <div class="offcanvas-body overflow-auto">
                <div class="row g-3 align-items-center mb-2">
                    <div class="col-auto">
                        <label for="csv-file" class="col-form-label">Upload CSV</label>
                    </div>
                    <div class="col-auto">
                        <input class="form-control" type="file" id="csv-file" accept=".csv,text/csv">
                    </div>
                    <div class="col-auto d-flex gap-2">
                        <button class="btn btn-outline-secondary" id="csv-sample" type="button">Sample</button>
                        <button class="btn btn-success" id="csv-add-selected" type="button">Add Selected</button>
                    </div>
                </div>

                <div id="csv-map-wrap" class="mb-3" style="display:none;">
                    <h6 class="mb-2">Map CSV columns to placeholders</h6>
                    <div class="table-responsive">
                        <table class="table table-sm align-middle mb-0">
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

                <div class="table-responsive">
                    <table class="table table-sm table-bordered align-middle mb-0" id="csv-preview-table">
                        <thead></thead>
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
        <script src="{{ asset('assets/js/teamcustomizations/index.js') }}"></script>
    @endpush
</x-app-layout>
