<div class="col-12 col-md-6 col-lg-4">
    <div class="card h-100 image-card shadow-sm" data-id="{{ $it['id'] }}" data-ratio="{{ $it['ratio'] }}">
        <div class="card-body d-flex flex-column">
            <div class="d-flex justify-content-between align-items-start mb-2">
                <h5 class="card-title m-0">{{ $it['name'] }}</h5>

                <div class="d-flex justify-content-end gap-2">
                    <!-- Duplicate (POST) -->
                    <form class="form-duplicate d-inline" method="post"
                          action="{{ route('cart.duplicate', $it['id']) }}">
                        @csrf
                        <button type="submit" class="btn btn-sm btn-outline-secondary">Duplicate
                        </button>
                    </form>

                    <!-- Delete -->
                    <form class="form-delete d-inline" method="post" action="{{ route('cart.delete', $it['id']) }}">
                        @csrf
                        <button type="submit" class="btn btn-sm btn-outline-danger">Delete</button>
                    </form>
                </div>
            </div>
            <hr>
            {{-- --- Price badges --- --}}
            <div class="mb-2">
                @if(isset($it['price']) && $it['price'] !== null)
                    <div class="row font-barlow fw-semibold fs-5">
                        <div class="col-6">
                            Price Each: <span data-price-each>&dollar;{{ number_format($it['price'], 2) }}</span>
                        </div>
                        <div class="col-6 text-end">
                            Total: <span data-total>&dollar;{{ number_format($it['extended'], 2) }}</span>
                        </div>
                    </div>
                @elseif($it['price_error'])
                    <span class="badge bg-danger" title="{{ $it['price_error'] }}">
                        Price unavailable
                    </span>
                @else
                    <span class="badge bg-light text-muted">Price pending</span>
                @endif
            </div>

            <div class="text-center mb-3">
                <div class="image-box">
                    <img
                            class="img-fluid rounded"
                            src="{{ $it['image'] }}"
                            alt="{{ $it['name'] }}"
                    >
                </div>
            </div>

            {{-- UPDATE form --}}
            <form class="form-update mt-auto" method="post" action="{{ route('cart.update', $it['id']) }}"
                  novalidate>
                @csrf
                <div class="row g-2">
                    <div class="col-4">
                        <label class="form-label small">Qty</label>
                        <input class="form-control" type="number" name="quantity" min="1"
                               value="{{ $it['qty'] }}">
                    </div>
                    <div class="col-4">
                        <label class="form-label small">Width (in)</label>
                        <input class="form-control input-width" type="number" step="0.25" min="0.25"
                               name="width"
                               value="{{ number_format($it['width'], 2, '.', '') }}">
                    </div>
                    <div class="col-4">
                        <label class="form-label small">Height (in)</label>
                        <input class="form-control input-height" type="number" step="0.25" min="0.25"
                               name="height"
                               value="{{ number_format($it['height'], 2, '.', '') }}">
                    </div>
                </div>

                <div class="form-check my-2">
                    <input class="form-check-input input-lock" type="checkbox" id="lock-{{ $it['id'] }}"
                           name="lock" value="1" checked>
                    <label class="form-check-label small" for="lock-{{ $it['id'] }}">Lock proportions</label>
                </div>

                <label class="form-label small mt-2">Image Name</label>
                <input class="form-control" type="text" name="image_name" value="{{ $it['name'] }}">

                <label class="form-label small mt-2">Notes</label>
                <textarea class="form-control" name="image_notes" rows="2">{{ $it['notes'] }}</textarea>

                <div class="d-flex justify-content-between align-items-center mt-3">
                    <div class="text-muted small">Uploaded: {{ optional($it['uploaded'])->format('M j, Y') }}</div>
                    <div>
                        @if(!$it['saved'])
                            <button class="btn btn-sm btn btn-danger save_image" type='button'
                                    data-id="{{ $it['id'] }}">
                                Add to My Images
                            </button>
                        @endif
                        <button type="submit" class="btn btn-sm btn-primary btn-save">Update</button>
                    </div>
                </div>
            </form>
            <div class="saving-indicator">
                <div class="si-box">
                    <div class="spinner-border spinner-border-sm text-primary"></div>
                    <span>Saving...</span>
                </div>
            </div>
        </div>
    </div>
</div>
