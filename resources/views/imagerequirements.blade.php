<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Image Requirements') }}
        </h2>
    </x-slot>

    <div class="container py-5">
        <div class="text-center mb-5">
            <h1 class="display-4 text-primary fw-bold mb-3">Image Requirements</h1>
            <p class="text-muted fs-5 mx-auto" style="max-width: 700px;">
                To ensure the highest quality prints, please follow these guidelines when preparing your artwork.
            </p>
        </div>

        <div class="row g-4">
            <!-- File Formats -->
            <div class="col-lg-12">
                <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-4">
                    <div class="card-header bg-white py-3 border-bottom">
                        <h4 class="mb-0 fw-bold text-dark"><i class="bi bi-file-earmark-check me-2 text-primary"></i>Accepted File Formats</h4>
                    </div>
                    <div class="card-body p-4">
                        <div class="row g-4">
                            <div class="col-md-3">
                                <div class="p-3 bg-light rounded-3 text-center h-100">
                                    <div class="fs-1 text-primary mb-2">.PNG</div>
                                    <div class="fw-bold mb-1">Recommended</div>
                                    <p class="small text-muted mb-0">Transparent background, at least 300 DPI.</p>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="p-3 bg-light rounded-3 text-center h-100">
                                    <div class="fs-1 text-secondary mb-2">.PDF</div>
                                    <div class="fw-bold mb-1">High Resolution</div>
                                    <p class="small text-muted mb-0">Portable Document Format with transparent backgrounds.</p>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="p-3 bg-light rounded-3 text-center h-100">
                                    <div class="fs-1 text-secondary mb-2">.PSD</div>
                                    <div class="fw-bold mb-1">Adobe Photoshop</div>
                                    <p class="small text-muted mb-0">Single-layer file with a transparent background.</p>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="p-3 bg-light rounded-3 text-center h-100">
                                    <div class="fs-1 text-secondary mb-2">.CDR</div>
                                    <div class="fw-bold mb-1">CorelDRAW</div>
                                    <p class="small text-muted mb-0">Ensure all text is converted to curves.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Detailed Requirements -->
            <div class="col-md-6">
                <div class="card border-0 shadow-sm rounded-4 h-100">
                    <div class="card-body p-4">
                        <div class="d-flex mb-4">
                            <div class="bg-primary-subtle p-3 rounded-3 me-3">
                                <i class="bi bi-aspect-ratio fs-3 text-primary"></i>
                            </div>
                            <div>
                                <h4 class="fw-bold text-dark mb-1">Resolution & Size</h4>
                                <p class="text-muted">Ensure your image is at least <strong>300 DPI</strong> (dots per inch). Low-resolution images may appear pixelated. It is recommended to upload images close to the final print size.</p>
                            </div>
                        </div>

                        <div class="d-flex mb-4">
                            <div class="bg-warning-subtle p-3 rounded-3 me-3">
                                <i class="bi bi-palette fs-3 text-warning"></i>
                            </div>
                            <div>
                                <h4 class="fw-bold text-dark mb-1">Color Accuracy</h4>
                                <p class="text-muted">Printed colors may vary slightly from how they appear on your screen due to differences in monitor settings.</p>
                            </div>
                        </div>

                        <div class="d-flex">
                            <div class="bg-info-subtle p-3 rounded-3 me-3">
                                <i class="bi bi-type fs-3 text-info"></i>
                            </div>
                            <div>
                                <h4 class="fw-bold text-dark mb-1">Text & Lines</h4>
                                <p class="text-muted">Avoid using very small text or thin lines, as they may not print clearly during the transfer process.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card border-0 shadow-sm rounded-4 h-100">
                    <div class="card-body p-4">
                        <div class="d-flex mb-4">
                            <div class="bg-danger-subtle p-3 rounded-3 me-3">
                                <i class="bi bi-exclamation-octagon fs-3 text-danger"></i>
                            </div>
                            <div>
                                <h4 class="fw-bold text-dark mb-1">Low-Quality Warning</h4>
                                <p class="text-muted">Images uploaded in low quality will print in low quality. We are not responsible for prints resulting from poor quality source files.</p>
                            </div>
                        </div>

                        <div class="d-flex mb-4">
                            <div class="bg-success-subtle p-3 rounded-3 me-3">
                                <i class="bi bi-arrows-fullscreen fs-3 text-success"></i>
                            </div>
                            <div>
                                <h4 class="fw-bold text-dark mb-1">Supported Dimensions</h4>
                                <p class="text-muted">Maximum file size: <strong>15 MB</strong>. Maximum dimensions: <strong>6000x6000 pixels</strong>.</p>
                            </div>
                        </div>

                        <div class="d-flex">
                            <div class="bg-secondary-subtle p-3 rounded-3 me-3">
                                <i class="bi bi-cursor fs-3 text-secondary"></i>
                            </div>
                            <div>
                                <h4 class="fw-bold text-dark mb-1">File Naming</h4>
                                <p class="text-muted">Use descriptive file names without special characters to make identification easier during the order process.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="alert alert-warning border-0 shadow-sm rounded-4 p-4 mt-5">
            <div class="d-flex">
                <i class="bi bi-exclamation-triangle-fill fs-3 text-warning me-3"></i>
                <div>
                    <h5 class="fw-bold text-dark mb-2">Important Notice</h5>
                    <p class="mb-0">To ensure high-quality prints, all files should be at least 300 DPI resolution and properly sized to match the intended print dimensions. We do not edit your files; they are printed as uploaded.</p>
                </div>
            </div>
        </div>

        <div class="text-center mt-5">
            <a href="{{ route('orders.new') }}" class="btn btn-primary btn-lg px-5 py-3 rounded-pill fw-bold shadow">
                <i class="bi bi-upload me-2"></i> Start Your Order Now
            </a>
        </div>
    </div>
</x-app-layout>
