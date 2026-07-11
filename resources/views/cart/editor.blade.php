<x-app-layout>
    <div class="py-12">
        <div class="max-w-7xl mx-auto sm:px-6 lg:px-8">
            <div class="bg-white overflow-hidden shadow-sm sm:rounded-lg p-6">
                <div class="d-flex justify-content-between align-items-center mb-6">
                    <h2 class="font-semibold text-xl text-gray-800 leading-tight mb-0">
                        Image Editor: {{ $image->image_name }}
                    </h2>
                    <a href="{{ route('cart.index') }}" class="btn btn-secondary">
                        <i class="bi bi-arrow-left"></i> Back to Cart
                    </a>
                </div>

                <div class="row">
                    <div class="col-md-4">
                        <div class="card shadow-sm border-0 rounded-4 mb-4">
                            <div class="card-body">
                                <h5 class="card-title fw-bold mb-4">Editing Tools</h5>

                                <!-- Background Remover -->
                                <div class="mb-4 pb-4 border-bottom">
                                    <label class="form-label fw-bold small text-uppercase text-muted">Background Remover</label>
                                    <div class="d-flex align-items-center gap-2 mb-3">
                                        <div class="flex-grow-1">
                                            <label class="small text-muted mb-1 d-block">Color to remove</label>
                                            <div class="input-group">
                                                <button id="pick-bg-btn" class="btn btn-outline-secondary" type="button" title="Use Eye Dropper">
                                                    <i class="bi bi-eyedropper"></i>
                                                </button>
                                                <input type="color" id="bg-color" class="form-control form-control-color w-100" value="#ffffff" title="Choose color" style="height: 38px; width: 38px; flex: none; padding: 0; border-radius: 4px;">
                                                <input type="text" id="bg-color-hex" class="form-control form-control-sm" value="#ffffff">
                                            </div>
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="small text-muted mb-1 d-block">Sensitivity (Fuzz): <span id="bg-fuzz-val">10%</span></label>
                                        <input type="range" id="bg-fuzz" class="form-range" min="0" max="100" value="10">
                                    </div>
                                    <button onclick="applyAction('remove_background')" class="btn btn-primary w-100 fw-bold">
                                        Remove Background
                                    </button>
                                </div>

                                <!-- Color Changer -->
                                <div class="mb-4 pb-4 border-bottom">
                                    <label class="form-label fw-bold small text-uppercase text-muted">Color Changer</label>
                                    <div class="row g-2 mb-3">
                                        <div class="col-6">
                                            <label class="small text-muted mb-1 d-block">From Color</label>
                                            <div class="input-group">
                                                <button id="pick-from-btn" class="btn btn-outline-secondary" type="button" title="Use Eye Dropper">
                                                    <i class="bi bi-eyedropper"></i>
                                                </button>
                                                <input type="color" id="color-from" class="form-control form-control-color" value="#000000" style="height: 38px; width: 38px; flex: none; padding: 0; border-radius: 4px;">
                                            </div>
                                        </div>
                                        <div class="col-6">
                                            <label class="small text-muted mb-1 d-block">To Color</label>
                                            <input type="color" id="color-to" class="form-control form-control-color w-100" value="#ff0000" style="height: 38px; width: 38px; flex: none; padding: 0; border-radius: 4px;">
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="small text-muted mb-1 d-block">Sensitivity (Fuzz): <span id="color-fuzz-val">10%</span></label>
                                        <input type="range" id="color-fuzz" class="form-range" min="0" max="100" value="10">
                                    </div>
                                    <button onclick="applyAction('change_color')" class="btn btn-primary w-100 fw-bold">
                                        Change Color
                                    </button>
                                </div>

                                <!-- Fill Area (Mask) -->
                                <div class="mb-4 pb-4 border-bottom">
                                    <label class="form-label fw-bold small text-uppercase text-muted">Fill Area (Mask)</label>
                                    <div class="mb-3">
                                        <label class="small text-muted mb-1 d-block">Fill Color</label>
                                        <input type="color" id="mask-to-color" class="form-control form-control-color w-100" value="#0000ff" style="height: 38px; width: 38px; flex: none; padding: 0; border-radius: 4px;">
                                    </div>
                                    <div class="mb-3">
                                        <label class="small text-muted mb-1 d-block">Sensitivity (Fuzz): <span id="mask-fuzz-val">10%</span></label>
                                        <input type="range" id="mask-fuzz" class="form-range" min="0" max="100" value="10">
                                    </div>
                                    <button id="mask-mode-btn" class="btn btn-outline-primary w-100 fw-bold mb-2">
                                        Enable Area Select
                                    </button>
                                    <p id="mask-hint" class="small text-info d-none">
                                        <i class="bi bi-info-circle"></i> Click on a specific area (like a letter) in the image to fill it.
                                    </p>
                                </div>

                                <!-- Color Reducer -->
                                <div class="mb-4">
                                    <label class="form-label fw-bold small text-uppercase text-muted">Color Reducer</label>
                                    <div class="mb-3">
                                        <label class="small text-muted mb-1 d-block">Number of Colors: <span id="reducer-colors-val">8</span></label>
                                        <input type="range" id="reducer-colors" class="form-range" min="2" max="64" value="8">
                                    </div>
                                    <button onclick="applyAction('reduce_colors')" class="btn btn-primary w-100 fw-bold">
                                        Reduce Colors
                                    </button>
                                </div>

                                <hr>

                                <button onclick="applyAction('revert')" class="btn btn-outline-danger w-100 fw-bold mt-2">
                                    <i class="bi bi-arrow-counterclockwise"></i> Revert to Original
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="col-md-8">
                        <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                            <div class="card-header bg-light border-0 py-3">
                                <h6 class="mb-0 fw-bold text-muted">Preview</h6>
                            </div>
                            <div class="card-body p-0 bg-secondary bg-opacity-10 d-flex align-items-center justify-content-center overflow-auto" style="min-height: 500px; position: relative;">
                                <div id="image-container" class="p-4 checkerboard">
                                    <img id="editing-image" src="{{ $image->image }}" class="img-fluid shadow-sm" style="cursor: crosshair;" crossorigin="anonymous">
                                </div>

                                <div id="processing-loader" class="position-absolute top-50 start-50 translate-middle d-none text-center bg-white bg-opacity-75 p-4 rounded-4 shadow" style="z-index: 1000;">
                                    <div class="spinner-border text-primary mb-2" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                    <p class="mb-0 fw-bold">Processing image...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    @push('styles')
    <style>
        .checkerboard {
            background-color: #eee;
            background-image: linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%, #ccc),
                              linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%, #ccc);
            background-size: 20px 20px;
            background-position: 0 0, 10px 10px;
        }
    </style>
    @endpush

    @push('scripts')
    <script>
        document.getElementById('bg-fuzz').oninput = function() {
            document.getElementById('bg-fuzz-val').innerText = this.value + '%';
        }
        document.getElementById('color-fuzz').oninput = function() {
            document.getElementById('color-fuzz-val').innerText = this.value + '%';
        }
        document.getElementById('reducer-colors').oninput = function() {
            document.getElementById('reducer-colors-val').innerText = this.value;
        }
        document.getElementById('mask-fuzz').oninput = function() {
            document.getElementById('mask-fuzz-val').innerText = this.value + '%';
        }

        document.getElementById('bg-color').oninput = function() {
            document.getElementById('bg-color-hex').value = this.value;
        }
        document.getElementById('bg-color-hex').oninput = function() {
            document.getElementById('bg-color').value = this.value;
        }

        const imgElement = document.getElementById('editing-image');
        let pickTarget = null;

        document.getElementById('mask-mode-btn').onclick = function() {
            const isActive = this.classList.contains('btn-primary');
            if (isActive) {
                this.classList.remove('btn-primary');
                this.classList.add('btn-outline-primary');
                this.innerText = 'Enable Area Select';
                document.getElementById('mask-hint').classList.add('d-none');
                pickTarget = null;
            } else {
                this.classList.add('btn-primary');
                this.classList.remove('btn-outline-primary');
                this.innerText = 'Area Select Mode ON';
                document.getElementById('mask-hint').classList.remove('d-none');
                pickTarget = 'mask';
                // Disable others
                document.getElementById('pick-bg-btn').classList.remove('btn-primary');
                document.getElementById('pick-bg-btn').classList.add('btn-outline-secondary');
                document.getElementById('pick-from-btn').classList.remove('btn-primary');
                document.getElementById('pick-from-btn').classList.add('btn-outline-secondary');
            }
        }

        document.getElementById('pick-bg-btn').onclick = function() {
            pickTarget = 'bg';
            this.classList.toggle('btn-primary');
            this.classList.toggle('btn-outline-secondary');
            document.getElementById('pick-from-btn').classList.remove('btn-primary');
            document.getElementById('pick-from-btn').classList.add('btn-outline-secondary');
            document.getElementById('mask-mode-btn').classList.remove('btn-primary');
            document.getElementById('mask-mode-btn').classList.add('btn-outline-primary');
            document.getElementById('mask-mode-btn').innerText = 'Enable Area Select';
            document.getElementById('mask-hint').classList.add('d-none');
            if (!this.classList.contains('btn-primary')) pickTarget = null;
        }

        document.getElementById('pick-from-btn').onclick = function() {
            pickTarget = 'from';
            this.classList.toggle('btn-primary');
            this.classList.toggle('btn-outline-secondary');
            document.getElementById('pick-bg-btn').classList.remove('btn-primary');
            document.getElementById('pick-bg-btn').classList.add('btn-outline-secondary');
            document.getElementById('mask-mode-btn').classList.remove('btn-primary');
            document.getElementById('mask-mode-btn').classList.add('btn-outline-primary');
            document.getElementById('mask-mode-btn').innerText = 'Enable Area Select';
            document.getElementById('mask-hint').classList.add('d-none');
            if (!this.classList.contains('btn-primary')) pickTarget = null;
        }

        imgElement.onclick = function(e) {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            canvas.width = imgElement.naturalWidth;
            canvas.height = imgElement.naturalHeight;
            ctx.drawImage(imgElement, 0, 0);

            const rect = imgElement.getBoundingClientRect();
            const x = Math.floor((e.clientX - rect.left) * (imgElement.naturalWidth / rect.width));
            const y = Math.floor((e.clientY - rect.top) * (imgElement.naturalHeight / rect.height));

            if (x < 0 || y < 0 || x >= imgElement.naturalWidth || y >= imgElement.naturalHeight) return;

            const pixel = ctx.getImageData(x, y, 1, 1).data;
            const hex = "#" + ("000000" + ((pixel[0] << 16) | (pixel[1] << 8) | pixel[2]).toString(16)).slice(-6);

            if (pickTarget === 'mask') {
                applyAction('mask_color', { x, y });
                return;
            }

            if (pickTarget === 'bg') {
                document.getElementById('bg-color').value = hex;
                document.getElementById('bg-color-hex').value = hex;
                document.getElementById('pick-bg-btn').classList.remove('btn-primary');
                document.getElementById('pick-bg-btn').classList.add('btn-outline-secondary');
                pickTarget = null;
            } else if (pickTarget === 'from') {
                document.getElementById('color-from').value = hex;
                document.getElementById('pick-from-btn').classList.remove('btn-primary');
                document.getElementById('pick-from-btn').classList.add('btn-outline-secondary');
                pickTarget = null;
            } else {
                // Default: just set the colors to whatever was clicked if no mode active
                document.getElementById('bg-color').value = hex;
                document.getElementById('bg-color-hex').value = hex;
                document.getElementById('color-from').value = hex;
            }
        }

        async function applyAction(action, extraData = {}) {
            const loader = document.getElementById('processing-loader');
            const img = document.getElementById('editing-image');

            if (action === 'revert') {
                if (!confirm('Are you sure you want to revert all changes to this image?')) return;
            }

            loader.classList.remove('d-none');
            img.style.opacity = '0.5';

            let data = {
                _token: '{{ csrf_token() }}',
                action: action,
                ...extraData
            };

            if (action === 'remove_background') {
                data.color = document.getElementById('bg-color').value;
                data.fuzz = document.getElementById('bg-fuzz').value;
            } else if (action === 'change_color') {
                data.from_color = document.getElementById('color-from').value;
                data.to_color = document.getElementById('color-to').value;
                data.fuzz = document.getElementById('color-fuzz').value;
            } else if (action === 'mask_color') {
                data.to_color = document.getElementById('mask-to-color').value;
                data.fuzz = document.getElementById('mask-fuzz').value;
            } else if (action === 'reduce_colors') {
                data.colors = document.getElementById('reducer-colors').value;
            }

            try {
                const response = await fetch('{{ route("cart.editor.process", $image->id) }}', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                    },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (result.success) {
                    const newImg = new Image();
                    newImg.onload = () => {
                        img.src = result.image_url;
                        img.style.opacity = '1';
                        loader.classList.add('d-none');
                        if (result.reverted) {
                            alert('Image reverted to original version.');
                        }
                    };
                    newImg.onerror = () => {
                        img.style.opacity = '1';
                        loader.classList.add('d-none');
                    };
                    newImg.src = result.image_url;
                } else {
                    alert('Error: ' + result.message);
                    loader.classList.add('d-none');
                    img.style.opacity = '1';
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An error occurred while processing the image.');
                loader.classList.add('d-none');
                img.style.opacity = '1';
            }
        }
    </script>
    @endpush
</x-app-layout>
