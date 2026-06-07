<x-app-layout>
    <x-slot name="header">
        <div class="d-flex align-items-center justify-content-between">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                Edit Image: {{ $image->image_name }}
            </h2>
            <a href="{{ route('admin.orders.show', $order) }}" class="btn btn-outline-secondary btn-sm fw-bold">
                <i class="bi bi-arrow-left me-1"></i> Back to Order #{{ $order->id }}
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row g-4">
                <!-- Left Column: Image Preview & Probe Info -->
                <div class="col-lg-7">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-dark text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold">Artwork Preview</h5>
                        </div>
                        <div class="card-body p-4 text-center">
                            <div class="checkerboard d-flex align-items-center justify-content-center border rounded-3 mb-4 p-3" style="min-height: 400px; background-image: linear-gradient(45deg, #f0f0f0 25%, transparent 25%), linear-gradient(-45deg, #f0f0f0 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #f0f0f0 75%), linear-gradient(-45deg, transparent 75%, #f0f0f0 75%); background-size: 20px 20px; background-position: 0 0, 0 10px, 10px -10px, -10px 0px;">
                                <img src="{{ $image->image }}?v={{ time() }}" alt="Preview" class="img-fluid" style="max-height: 500px; filter: drop-shadow(0 0 10px rgba(0,0,0,0.1));">
                            </div>

                            <div class="row g-3 text-start">
                                <div class="col-md-6">
                                    <div class="p-3 bg-light rounded-3">
                                        <h6 class="fw-bold mb-2 small text-uppercase text-muted">File Information</h6>
                                        <ul class="list-unstyled mb-0 small">
                                            <li><strong>Name:</strong> {{ basename($image->image) }}</li>
                                            <li><strong>Type:</strong> {{ strtoupper(pathinfo($image->image, PATHINFO_EXTENSION)) }}</li>
                                            <li><strong>Size:</strong> {{ number_format($image->file_size / 1024, 2) }} KB</li>
                                        </ul>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="p-3 bg-light rounded-3">
                                        <h6 class="fw-bold mb-2 small text-uppercase text-muted">Technical Data (Imagick)</h6>
                                        <ul class="list-unstyled mb-0 small">
                                            <li><strong>Resolution:</strong> {{ $probe['px_w'] }} x {{ $probe['px_h'] }} px</li>
                                            <li><strong>DPI:</strong> {{ $probe['dpi_x'] ?? '?' }} x {{ $probe['dpi_y'] ?? '?' }} ({{ $probe['units_label'] }})</li>
                                            @if($probe['size300_w'])
                                                <li><strong>Print Size @ 300dpi:</strong> {{ $probe['size300_w'] }}" x {{ $probe['size300_h'] }}"</li>
                                            @endif
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Column: Actions -->
                <div class="col-lg-5">
                    @if(session('success'))
                        <div class="alert alert-success border-0 shadow-sm rounded-4 mb-4">
                            <i class="bi bi-check-circle-fill me-2"></i> {{ session('success') }}
                        </div>
                    @endif

                    @if(session('error'))
                        <div class="alert alert-danger border-0 shadow-sm rounded-4 mb-4">
                            <i class="bi bi-exclamation-triangle-fill me-2"></i> {{ session('error') }}
                        </div>
                    @endif

                    <!-- Resize Action -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-primary text-white py-3 px-4 d-flex justify-content-between align-items-center">
                            <h5 class="mb-0 fw-bold small text-uppercase tracking-wider">Update Dimensions (Inches)</h5>
                            <div class="d-flex align-items-center gap-3">
                                <button type="button" id="resetToActual" class="btn btn-sm btn-light fw-bold">
                                    <i class="bi bi-arrow-counterclockwise"></i> Reset
                                </button>
                                <div class="form-check form-switch mb-0">
                                    <input class="form-check-input" type="checkbox" id="lockRatio" checked>
                                    <label class="form-check-label small fw-bold text-white" for="lockRatio"><i class="bi bi-lock-fill"></i> Lock</label>
                                </div>
                            </div>
                        </div>
                        <div class="card-body p-4">
                            <form action="{{ route('admin.orders.images.update', $image) }}" method="POST">
                                @csrf
                                <div class="row g-3 mb-3">
                                    <div class="col-6">
                                        <label class="form-label small fw-bold">Width (in)</label>
                                        <input type="number" step="0.01" name="width" id="img_width" class="form-control" value="{{ $image->width }}">
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label small fw-bold">Height (in)</label>
                                        <input type="number" step="0.01" name="height" id="img_height" class="form-control" value="{{ $image->height }}">
                                    </div>
                                </div>
                                <button type="submit" class="btn btn-primary w-100 fw-bold">
                                    <i class="bi bi-save me-1"></i> Update Size & Metadata
                                </button>
                                <p class="small text-muted mt-2 mb-0">
                                    <i class="bi bi-info-circle me-1"></i> This updates the DB record and re-writes the pHYs (DPI) chunk in the PNG file.
                                </p>
                            </form>
                        </div>
                    </div>

                    <!-- Replace Artwork Action -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-dark text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold small text-uppercase tracking-wider">Replace Artwork</h5>
                        </div>
                        <div class="card-body p-4">
                            <form action="{{ route('admin.orders.images.replace', $image) }}" method="POST" enctype="multipart/form-data">
                                @csrf
                                <div class="mb-3">
                                    <label class="form-label small fw-bold">Upload New File</label>
                                    <input type="file" name="file" class="form-control">
                                </div>
                                <button type="submit" class="btn btn-dark w-100 fw-bold" onclick="return confirm('Are you sure you want to replace this artwork?')">
                                    <i class="bi bi-cloud-upload me-1"></i> Replace Artwork
                                </button>
                                <p class="small text-muted mt-2 mb-0">
                                    <i class="bi bi-info-circle me-1"></i> Replaces the file on disk (with versioning) and updates the record.
                                </p>
                            </form>
                        </div>
                    </div>

                    <!-- Alpha Threshold Cleanup -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-warning py-3 px-4">
                            <h5 class="mb-0 fw-bold small text-uppercase tracking-wider text-dark">Alpha Cleanup (Translucency)</h5>
                        </div>
                        <div class="card-body p-4">
                            <form action="{{ route('admin.orders.images.alpha', $image) }}" method="POST">
                                @csrf
                                <div class="mb-3">
                                    <label class="form-label small fw-bold">Alpha Threshold (0-255)</label>
                                    <input type="range" name="threshold" class="form-range" min="0" max="255" value="128" oninput="this.nextElementSibling.value = this.value">
                                    <output class="fw-bold">128</output>
                                </div>
                                <button type="submit" class="btn btn-warning w-100 fw-bold text-dark" onclick="return confirm('This will process the image to remove semi-transparent pixels. Continue?')">
                                    <i class="bi bi-magic me-1"></i> Apply Alpha Threshold
                                </button>
                                <p class="small text-muted mt-2 mb-0">
                                    <i class="bi bi-info-circle me-1"></i> Makes pixels either fully opaque or fully transparent based on the threshold. Essential for DTF RIPs.
                                </p>
                            </form>
                        </div>
                    </div>

                    <div class="d-grid gap-2">
                        <a href="{{ route('admin.orders.show', $order) }}" class="btn btn-outline-secondary py-3 fw-bold rounded-4 shadow-sm">
                            <i class="bi bi-arrow-left-circle me-2"></i> Return to Order #{{ $order->id }}
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    @push('scripts')
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const widthInput = document.getElementById('img_width');
            const heightInput = document.getElementById('img_height');
            const lockSwitch = document.getElementById('lockRatio');
            const resetButton = document.getElementById('resetToActual');

            let ratio = {{ $image->width_ratio ?: ($image->width / max(0.01, $image->height)) }};

            const actualW = {{ $probe['size300_w'] ?? 'null' }};
            const actualH = {{ $probe['size300_h'] ?? 'null' }};

            resetButton.addEventListener('click', function() {
                if (actualW && actualH) {
                    widthInput.value = actualW;
                    heightInput.value = actualH;
                    // Update ratio based on actual values
                    ratio = actualW / actualH;
                }
            });

            widthInput.addEventListener('input', function() {
                if (lockSwitch.checked && ratio > 0) {
                    heightInput.value = (parseFloat(this.value) / ratio).toFixed(2);
                }
            });

            heightInput.addEventListener('input', function() {
                if (lockSwitch.checked && ratio > 0) {
                    widthInput.value = (parseFloat(this.value) * ratio).toFixed(2);
                }
            });

            // Update ratio if lock is unchecked then re-checked
            lockSwitch.addEventListener('change', function() {
                if (this.checked) {
                    const w = parseFloat(widthInput.value);
                    const h = parseFloat(heightInput.value);
                    if (w > 0 && h > 0) {
                        ratio = w / h;
                    }
                }
            });
        });
    </script>
    @endpush
</x-app-layout>
