<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Font Management') }}
        </h2>
    </x-slot>

    <div class="container py-4">
        <div class="d-flex align-items-center mb-3 gap-2">
            <h3 class="mb-0"><i class="bi bi-type me-2"></i> Fonts</h3>
            <a href="{{ route('admin.customnames.fontsmap') }}" class="btn btn-sm btn-outline-primary ms-auto">
                <i class="bi bi-map me-1"></i> Manage Display Names
            </a>
        </div>

        <div class="card shadow-sm border-0 rounded-3 mb-4">
            <div class="card-body">
                <form id="font-upload-form" enctype="multipart/form-data">
                    <div class="row g-3 align-items-end">
                        <div class="col-md-6">
                            <label class="form-label fw-semibold">Upload Font File</label>
                            <input class="form-control" type="file" name="font" id="font-file" accept=".ttf,.otf,.woff,.woff2" required />
                            <div class="form-text">Allowed formats: .ttf, .otf, .woff, .woff2</div>
                        </div>
                        <div class="col-md-6 d-flex gap-2">
                            <button type="submit" class="btn btn-primary px-4">
                                <i class="bi bi-upload me-1"></i> Upload
                            </button>
                            <button type="button" id="btn-reload-fonts" class="btn btn-outline-secondary">
                                <i class="bi bi-arrow-repeat me-1"></i> Reload on Node
                            </button>
                            <button type="button" id="btn-refresh-list" class="btn btn-outline-primary">
                                <i class="bi bi-arrow-clockwise me-1"></i> Refresh List
                            </button>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <div class="card shadow-sm border-0 rounded-3">
            <div class="card-body">
                <div id="fonts-table">
                    <div class="text-center py-5">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading fonts…</span>
                        </div>
                        <p class="mt-2 text-muted">Loading fonts…</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    @push('scripts')
    <script>
        const API_URLS = {
            list: '{{ route('admin.customnames.fonts.list') }}',
            upload: '{{ route('admin.customnames.fonts.upload') }}',
            reload: '{{ route('admin.customnames.fonts.reload') }}'
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
    <script src="{{ asset('assets/js/admin/customnames/fonts.js') }}"></script>
    @endpush
</x-app-layout>
