<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Font Display Names') }}
        </h2>
    </x-slot>

    <style>
        #fm-rows input.form-control { min-width: 240px; }
        #fm-rows .fm-ppi { max-width: 120px; }
        .d-none { display: none !important; }
    </style>

    <section class="container my-4" id="fonts-map">
        <div class="d-flex align-items-center mb-3 gap-2">
            <h3 class="mb-0"><i class="bi bi-map me-2"></i> Font Display Names</h3>
            <div class="ms-auto d-flex gap-2">
                <button id="btn-reload" class="btn btn-outline-secondary">
                    <i class="bi bi-arrow-repeat me-1"></i> Reload Fonts
                </button>
                <button id="btn-save-all" class="btn btn-primary">
                    <i class="bi bi-save me-1"></i> Save All
                </button>
            </div>
        </div>

        <div id="fm-alert" class="alert d-none" role="alert"></div>

        <div class="card shadow-sm border-0 rounded-3">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="bg-light">
                    <tr>
                        <th>Slug</th>
                        <th>Family</th>
                        <th>PPI</th>
                        <th style="width:100px">T M(px)</th>
                        <th>Format</th>
                        <th>Filename</th>
                        <th class="text-end">Actions</th>
                    </tr>
                    </thead>
                    <tbody id="fm-rows">
                        <tr>
                            <td colspan="7" class="text-center py-5">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="visually-hidden">Loading map…</span>
                                </div>
                                <p class="mt-2 text-muted">Loading map…</p>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </section>

    @push('scripts')
    <script>
        window.__FM_URLS = {
            fonts:   '{{ route('admin.customnames.fonts.list') }}',
            getMap:  '{{ route('admin.customnames.fontsmap.get') }}',
            saveMap: '{{ route('admin.customnames.fontsmap.save') }}',
            setOne:  '{{ route('admin.customnames.fonts.set') }}',
            reload:  '{{ route('admin.customnames.fonts.reload') }}'
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
    <script src="{{ asset('assets/js/admin/customnames/fontsmap.js') }}"></script>
    @endpush
</x-app-layout>
