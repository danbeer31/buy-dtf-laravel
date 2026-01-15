<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Add Custom Color') }}
        </h2>
    </x-slot>

    <div class="container py-4">
        <div class="row justify-content-center">
            <div class="col-lg-8">
                <div class="d-flex align-items-center mb-4">
                    <a href="{{ route('admin.customcolors.index') }}" class="btn btn-outline-secondary btn-sm me-3">
                        <i class="bi bi-arrow-left"></i>
                    </a>
                    <h3 class="mb-0 fw-bold">Add Custom Color</h3>
                </div>

                @if($errors->any())
                    <div class="alert alert-danger border-0 shadow-sm rounded-3 mb-4">
                        <ul class="mb-0">
                            @foreach($errors->all() as $error)
                                <li>{{ $error }}</li>
                            @endforeach
                        </ul>
                    </div>
                @endif

                @if(session('error'))
                    <div class="alert alert-danger border-0 shadow-sm rounded-3 mb-4">
                        {{ session('error') }}
                    </div>
                @endif

                <form method="POST" action="{{ route('admin.customcolors.store') }}">
                    @csrf
                    <div class="card shadow-sm border-0 rounded-3">
                        <div class="card-body p-4">
                            <div class="mb-4">
                                <label class="form-label fw-semibold">Name</label>
                                <input type="text" name="name" class="form-control @error('name') is-invalid @enderror"
                                       required value="{{ old('name') }}" placeholder="e.g., Athletic Gold">
                                @error('name')
                                    <div class="invalid-feedback">{{ $message }}</div>
                                @enderror
                            </div>

                            <div class="mb-4">
                                <label class="form-label fw-semibold">Hex (#RRGGBB)</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light"><i class="bi bi-hash"></i></span>
                                    <input type="text" name="hex" id="hex-input"
                                           class="form-control @error('hex') is-invalid @enderror"
                                           required value="{{ old('hex') }}" placeholder="FF6E0E">
                                </div>
                                <div class="form-text mt-2 small text-muted">Include the leading “#” or it will be added automatically. Example: #FF6E0E</div>
                                @error('hex')
                                    <div class="text-danger small mt-1">{{ $message }}</div>
                                @enderror
                            </div>

                            <div class="mb-4">
                                <label class="form-label fw-semibold d-block">Preview</label>
                                <div id="color-preview" class="rounded shadow-sm border" style="width:100px;height:50px;background:{{ old('hex', '#CCCCCC') }};"></div>
                            </div>

                            <div class="mb-3 form-check form-switch">
                                <input class="form-check-input" type="checkbox" id="activeCheck" name="active" value="1"
                                       {{ old('active', 1) ? 'checked' : '' }}>
                                <label class="form-check-label fw-semibold" for="activeCheck">Active</label>
                            </div>
                        </div>
                        <div class="card-footer bg-light p-4 d-flex justify-content-between">
                            <a href="{{ route('admin.customcolors.index') }}" class="btn btn-secondary px-4">Cancel</a>
                            <button type="submit" class="btn btn-primary px-4">Save Color</button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    </div>

    @push('scripts')
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const hexInput = document.getElementById('hex-input');
            const preview = document.getElementById('color-preview');

            hexInput.addEventListener('input', function() {
                let val = this.value.trim();
                if (val && !val.startsWith('#')) {
                    val = '#' + val;
                }
                if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
                    preview.style.background = val;
                }
            });
        });
    </script>
    @endpush
</x-app-layout>
