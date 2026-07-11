<div class="col-12 col-md-6 col-lg-4">
    <div class="card h-100 image-card shadow-sm border rounded-4 overflow-hidden" data-id="{{ $it['id'] }}" data-ratio="{{ $it['ratio'] }}">
        <div class="card-body d-flex flex-column p-3">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div class="d-flex align-items-center gap-2">
                    <h5 class="card-title m-0 text-truncate fw-bold fs-6" title="{{ $it['name'] }}">{{ $it['name'] }}</h5>
                    @if(($it['item_type'] ?? 'standard') === 'gang_sheet')
                        <span class="badge bg-dark-subtle text-dark border">Gang Sheet</span>
                    @endif
                </div>

                <div class="d-flex gap-2">
                    <!-- Duplicate (POST) -->
                    <form class="form-duplicate d-inline" method="post"
                          action="{{ route('cart.duplicate', $it['id']) }}">
                        @csrf
                        <button type="submit" class="btn btn-xs btn-outline-secondary px-2" title="Duplicate">
                            <i class="bi bi-files me-1"></i> Duplicate
                        </button>
                    </form>

                    <!-- Delete -->
                    <form class="form-delete d-inline" method="post" action="{{ route('cart.delete', $it['id']) }}">
                        @csrf
                        <button type="submit" class="btn btn-xs btn-outline-danger px-2" title="Delete">
                            <i class="bi bi-trash me-1"></i> Delete
                        </button>
                    </form>

                </div>
            </div>

            {{-- --- Price badges --- --}}
            <div class="mb-3 p-2 bg-light rounded-3">
                @if(isset($it['price']) && $it['price'] !== null)
                    <div class="row g-0 font-barlow fw-bold">
                        <div class="col-6 small text-muted">
                            Each: <span class="text-dark" data-price-each>&dollar;{{ number_format($it['price'], 2) }}</span>
                        </div>
                        <div class="col-6 text-end small text-muted">
                            Total: <span class="text-primary fs-6" data-total>&dollar;{{ number_format($it['extended'], 2) }}</span>
                        </div>
                    </div>
                @elseif($it['price_error'])
                    <span class="badge bg-danger w-100" title="{{ $it['price_error'] }}">
                        Price unavailable
                    </span>
                @else
                    <span class="badge bg-light text-muted w-100">Price pending</span>
                @endif
            </div>

            <div class="text-center mb-4 px-2">
                <div class="image-box shadow-sm rounded-3">
                    <img
                            class="img-fluid"
                            src="{{ $it['thumbnail'] ?? $it['image'] }}"
                            alt="{{ $it['name'] }}"
                            loading="lazy"
                    >
                </div>
            </div>

            {{-- UPDATE form --}}
            <form class="form-update mt-auto" method="post" action="{{ route('cart.update', $it['id']) }}"
                  novalidate>
                @csrf
                <div class="row g-2 mb-3">
                    <div class="col-4">
                        <label class="form-label small fw-semibold text-muted mb-1">Qty</label>
                        <input class="form-control form-control-sm border-0 bg-light" type="number" name="quantity" min="1"
                               value="{{ $it['qty'] }}">
                    </div>
                    @if(($it['item_type'] ?? 'standard') === 'gang_sheet')
                        <div class="col-8">
                            <label class="form-label small fw-semibold text-muted mb-1">Sheet Size</label>
                            <input class="form-control form-control-sm border-0 bg-light" type="text" readonly
                                   value="{{ strtoupper((data_get($it, 'item_meta.size_key') ?? (number_format($it['width'], 2, '.', '') . 'x' . number_format($it['height'], 2, '.', '')))) }}">
                        </div>
                    @else
                        <div class="col-4">
                            <label class="form-label small fw-semibold text-muted mb-1">Width (in)</label>
                            <input class="form-control form-control-sm input-width border-0 bg-light" type="number" step="0.25" min="0.25"
                                   name="width"
                                   value="{{ number_format($it['width'], 2, '.', '') }}">
                        </div>
                        <div class="col-4">
                            <label class="form-label small fw-semibold text-muted mb-1">Height (in)</label>
                            <input class="form-control form-control-sm input-height border-0 bg-light" type="number" step="0.25" min="0.25"
                                   name="height"
                                   value="{{ number_format($it['height'], 2, '.', '') }}">
                        </div>
                    @endif
                </div>

                @if(($it['item_type'] ?? 'standard') !== 'gang_sheet')
                    <div class="form-check form-switch mb-3">
                        <input class="form-check-input input-lock" type="checkbox" id="lock-{{ $it['id'] }}"
                               name="lock" value="1" checked>
                        <label class="form-check-label small text-muted" for="lock-{{ $it['id'] }}">Lock proportions</label>
                    </div>
                @endif

                <div class="mb-3">
                    <label class="form-label small fw-semibold text-muted mb-1">Image Name</label>
                    <input class="form-control form-control-sm border-0 bg-light" type="text" name="image_name" value="{{ $it['name'] }}">
                </div>

                @if(($it['item_type'] ?? 'standard') !== 'gang_sheet' && isset($it['other_sizes']) && count($it['other_sizes']) > 0)
                    @php
                        $isDisabled = count($it['other_sizes']) < 2;
                    @endphp
                    <div class="mb-3 p-2 border-0 rounded-3 bg-light {{ $isDisabled ? 'opacity-75' : '' }}">
                        <label class="form-label x-small d-block fw-bold {{ $isDisabled ? 'text-muted' : 'text-primary' }} mb-1 text-uppercase letter-spacing-1">
                            <i class="bi bi-clock-history me-1"></i>Re-use size:
                        </label>
                        <select class="form-select form-select-sm {{ $isDisabled ? 'border-0' : 'border-primary' }} bg-white" style="font-size: 0.85rem; height: 38px; font-weight: 500;"
                                {{ $isDisabled ? 'disabled' : '' }}
                                onchange="if(this.value) {
                                    const [wVal, hVal] = this.value.split('|');
                                    const f=this.closest('form');
                                    const wInp=f.querySelector('.input-width');
                                    const hInp=f.querySelector('.input-height');
                                    const card=f.closest('.image-card');
                                    if(card && parseFloat(hVal)>0){
                                        card.dataset.ratio=String(parseFloat(wVal)/parseFloat(hVal));
                                    }
                                    wInp.dispatchEvent(new Event('focusin', {bubbles:true}));
                                    hInp.dispatchEvent(new Event('focusin', {bubbles:true}));
                                    wInp.value=wVal;
                                    hInp.value=hVal;
                                    wInp.dispatchEvent(new Event('input', {bubbles:true}));
                                    hInp.dispatchEvent(new Event('input', {bubbles:true}));
                                    wInp.dispatchEvent(new Event('focusout', {bubbles:true}));
                                    hInp.dispatchEvent(new Event('focusout', {bubbles:true}));
                                }">
                            <option value="">Select previous size...</option>
                            @foreach($it['other_sizes'] as $os)
                                @php
                                    $isSelected = (abs($os->width - $it['width']) <= 0.10 && abs($os->height - $it['height']) <= 0.10);
                                @endphp
                                <option value="{{ number_format($os->width, 2, '.', '') }}|{{ number_format($os->height, 2, '.', '') }}" {{ $isSelected ? 'selected' : '' }}>
                                    {{ number_format($os->width, 2) }} x {{ number_format($os->height, 2) }} {{ $isSelected ? '(current)' : '' }}
                                </option>
                            @endforeach
                        </select>
                    </div>
                @endif

                <div class="mb-3">
                    <label class="form-label small fw-semibold text-muted mb-1">Notes</label>
                    <textarea class="form-control form-control-sm border-0 bg-light" name="image_notes" rows="2" placeholder="Special instructions...">{{ $it['notes'] }}</textarea>
                </div>

                @if(($it['item_type'] ?? 'standard') === 'gang_sheet')
                    <div class="mb-3">
                        <a class="small fw-semibold text-decoration-none" href="{{ $it['image'] }}" target="_blank" rel="noopener">
                            <i class="bi bi-file-earmark-image me-1"></i>Open uploaded sheet
                        </a>
                    </div>
                @endif

                <div class="d-flex justify-content-between align-items-center mt-3 pt-2 border-top">
                    <div class="text-muted x-small">
                        <i class="bi bi-calendar3 me-1"></i>{{ optional($it['uploaded'])->format('M j, Y') }}
                    </div>
                    <div class="d-flex gap-2">
                        @if(!$it['saved'])
                            <button class="btn btn-xs btn-outline-danger save_image" type='button'
                                    data-id="{{ $it['id'] }}" title="Add to My Images">
                                <i class="bi bi-heart fs-5"></i>
                            </button>
                        @endif
                        <button type="submit" class="btn btn-sm btn-primary px-3 fw-bold btn-save">Update</button>
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
