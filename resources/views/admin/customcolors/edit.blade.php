<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ $can_edit ? __('Edit Custom Color') : __('View Custom Color') }}
        </h2>
    </x-slot>

    <div class="container py-4">
        <div class="row justify-content-center">
            <div class="col-lg-8">
                <div class="d-flex align-items-center mb-4">
                    <a href="{{ route('admin.customcolors.index') }}" class="btn btn-outline-secondary btn-sm me-3">
                        <i class="bi bi-arrow-left"></i>
                    </a>
                    <h3 class="mb-0 fw-bold">{{ $can_edit ? 'Edit' : 'View' }} Custom Color</h3>
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

                <div class="card shadow-sm border-0 rounded-3 mb-4">
                    <div class="card-body p-4">
                        <div class="d-flex align-items-center">
                            <div class="rounded shadow-sm border" style="width:100px;height:50px;background:{{ $color->hex }};"></div>
                            <div class="ms-4">
                                <h4 class="mb-1 fw-bold">{{ $color->name }}</h4>
                                <div class="d-flex gap-2">
                                    <code>{{ $color->hex }}</code>
                                    @if($is_global)
                                        <span class="badge bg-secondary small text-uppercase">Global</span>
                                    @endif
                                    @if($color->active)
                                        <span class="badge bg-success small text-uppercase">Active</span>
                                    @else
                                        <span class="badge bg-secondary small text-uppercase">Inactive</span>
                                    @endif
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                @if($can_edit)
                    <form method="POST" action="{{ route('admin.customcolors.update', $color->id) }}">
                        @csrf
                        <div class="card shadow-sm border-0 rounded-3">
                            <div class="card-body p-4">
                                <div class="mb-4">
                                    <label class="form-label fw-semibold">Name</label>
                                    <input type="text" name="name" class="form-control @error('name') is-invalid @enderror"
                                           required value="{{ old('name', $color->name) }}" placeholder="e.g., Athletic Gold">
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
                                               required value="{{ old('hex', $color->hex) }}" placeholder="FF6E0E">
                                    </div>
                                    <div class="form-text mt-2 small text-muted">Include the leading “#” or it will be added automatically. Example: #FF6E0E</div>
                                    @error('hex')
                                        <div class="text-danger small mt-1">{{ $message }}</div>
                                    @enderror
                                </div>

                                <div class="mb-4">
                                    <label class="form-label fw-semibold d-block">Preview</label>
                                    <div id="color-preview" class="rounded shadow-sm border" style="width:100px;height:50px;background:{{ old('hex', $color->hex) }};"></div>
                                </div>

                                <div class="mb-3 form-check form-switch">
                                    <input class="form-check-input" type="checkbox" id="activeCheck" name="active" value="1"
                                           {{ old('active', $color->active) ? 'checked' : '' }}>
                                    <label class="form-check-label fw-semibold" for="activeCheck">Active</label>
                                </div>
                            </div>
                            <div class="card-footer bg-light p-4 d-flex justify-content-between">
                                <a href="{{ route('admin.customcolors.index') }}" class="btn btn-secondary px-4">Cancel</a>
                                <button type="submit" class="btn btn-primary px-4">Save Changes</button>
                            </div>
                        </div>
                    </form>
                @else
                    <div class="alert alert-info border-0 shadow-sm rounded-3">
                        <i class="bi bi-info-circle me-2"></i>
                        Global colors are view-only. To adjust availability for this shop, create a shop color with the same name/hex under your shop.
                    </div>
                    <div class="mt-4 text-center">
                        <a href="{{ route('admin.customcolors.index') }}" class="btn btn-secondary px-5">Back to List</a>
                    </div>
                @endif
            </div>
        </div>
    </div>

    @push('scripts')
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const hexInput = document.getElementById('hex-input');
            const preview = document.getElementById('color-preview');

            if (hexInput) {
                hexInput.addEventListener('input', function() {
                    let val = this.value.trim();
                    if (val && !val.startsWith('#')) {
                        val = '#' + val;
                    }
                    if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
                        preview.style.background = val;
                    }
                });
            }
        });
    </script>
    @endpush
</x-app-layout>
