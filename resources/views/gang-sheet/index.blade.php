<x-app-layout>
    <x-slot name="header">
        <div class="d-flex align-items-center justify-content-between">
            <h2 class="fw-bold fs-4 text-dark mb-0">Gang Sheet Uploader (Internal)</h2>
            <a href="{{ route('cart.index') }}" class="btn btn-outline-secondary btn-sm fw-bold">
                <i class="bi bi-arrow-left me-1"></i> Back to Cart
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container" style="max-width: 880px;">
            <div class="alert alert-warning border-0 shadow-sm rounded-4">
                <div class="fw-bold mb-1">Internal testing page</div>
                This page is dark-launched. Upload print-ready PNG or PDF gang sheets only.
            </div>

            <div class="card border-0 shadow-sm rounded-4">
                <div class="card-body p-4 p-md-5">
                    <form method="POST" action="{{ route('gang-sheet.store') }}" enctype="multipart/form-data">
                        @csrf

                        <div class="mb-4">
                            <label class="form-label fw-bold">Sheet File</label>
                            <input type="file" name="file" class="form-control @error('file') is-invalid @enderror" accept=".png,.pdf,image/png,application/pdf" required>
                            <div class="form-text">Allowed: PNG, PDF. Max 50MB.</div>
                            @error('file')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>

                        <div class="row g-3">
                            <div class="col-md-6">
                                <label class="form-label fw-bold">Sheet Size</label>
                                <select name="sheet_size" class="form-select @error('sheet_size') is-invalid @enderror" required>
                                    <option value="">Select a size</option>
                                    @foreach($sizes as $key => $size)
                                        <option value="{{ $key }}" {{ old('sheet_size') === $key ? 'selected' : '' }}>
                                            {{ strtoupper($key) }} - ${{ number_format($size['base_price'], 2) }}
                                        </option>
                                    @endforeach
                                </select>
                                @error('sheet_size')<div class="invalid-feedback">{{ $message }}</div>@enderror
                                <div class="form-text">22x96 has qty-tier pricing.</div>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold">Quantity</label>
                                <input type="number" name="quantity" min="1" max="500" value="{{ old('quantity', 1) }}" class="form-control @error('quantity') is-invalid @enderror" required>
                                @error('quantity')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            </div>
                        </div>

                        <div class="mt-4">
                            <label class="form-label fw-bold">Notes (Optional)</label>
                            <textarea name="notes" rows="3" maxlength="1000" class="form-control @error('notes') is-invalid @enderror" placeholder="Add special instructions">{{ old('notes') }}</textarea>
                            @error('notes')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>

                        <div class="d-flex justify-content-end mt-4">
                            <button type="submit" class="btn btn-primary fw-bold px-4">
                                <i class="bi bi-cart-plus me-1"></i> Add to Cart
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>

