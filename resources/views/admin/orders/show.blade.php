<x-app-layout>
    @php
        $pricingFrozen = !((int)$order->status === 1 && empty($order->qbo_invoice_id));
    @endphp
    <x-slot name="header">
        <div class="d-flex align-items-center justify-content-between">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                Order Detail: #{{ $order->id }}
            </h2>
            <a href="{{ route('admin.orders.index') }}" class="btn btn-outline-secondary btn-sm fw-bold">
                <i class="bi bi-arrow-left me-1"></i> Back to Orders
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row g-4">
                <!-- Left Column: Order Items & Shipping -->
                <div class="col-lg-8">
                    <!-- Order Status & Summary -->
                    <div class="card shadow-sm border-0 rounded-4 mb-4 overflow-hidden">
                        <div class="card-header bg-dark text-white py-3 px-4">
                            <div class="d-flex justify-content-between align-items-center">
                                <h5 class="mb-0 fw-bold">Order Summary</h5>
                                <span class="badge border text-uppercase px-3 py-2" style="background-color: {{ $order->orderStatus->color ?? '#6c757d' }}22; color: #fff; border-color: {{ $order->orderStatus->color ?? '#6c757d' }};">
                                    {{ $order->orderStatus->name ?? 'Unknown' }}
                                </span>
                            </div>
                        </div>
                        <div class="card-body p-4">
                            <div class="row g-3">
                                <div class="col-md-4">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Business</label>
                                    <p class="fs-5 fw-bold mb-1">{{ $order->business->business_name }}</p>
                                    <p class="text-secondary small mb-0">{{ $order->business->contact_name }} ({{ $order->business->email }})</p>
                                </div>
                                <div class="col-md-4 text-center">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">QuickBooks Invoice</label>
                                    @if($order->qbo_invoice_number)
                                        <p class="fs-4 fw-bold text-primary mb-0">{{ $order->qbo_invoice_number }}</p>
                                        <small class="text-muted">ID: {{ $order->qbo_invoice_id }}</small>
                                    @else
                                        <p class="text-muted italic mb-0">No invoice created</p>
                                        <form action="{{ route('admin.orders.create-qbo-invoice') }}" method="POST" class="mt-2">
                                            @csrf
                                            <input type="hidden" name="order_id" value="{{ $order->id }}">
                                            <button type="submit" class="btn btn-sm btn-outline-primary fw-bold">
                                                Create QBO Invoice
                                            </button>
                                        </form>
                                    @endif
                                </div>
                                <div class="col-md-4 text-md-end">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Order Date</label>
                                    <p class="fs-5 fw-bold">{{ $order->order_date ? $order->order_date->format('M d, Y') : 'N/A' }}</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Line Items -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-white border-bottom-0 pt-4 px-4">
                            <h5 class="fw-bold mb-0">Order Items</h5>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table align-middle mb-0">
                                    <thead class="bg-light">
                                        <tr>
                                            <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">Product</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted text-center">Dimensions</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted text-center">Qty</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted text-center">Production</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Price</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        @foreach($order->dtfImages as $item)
                                            <tr>
                                                <td class="ps-4 py-3">
                                                    <div class="d-flex align-items-center">
                                                        <img src="{{ $item->image }}" class="rounded shadow-sm me-3" style="width: 50px; height: 50px; object-fit: contain; background: #f8f9fa;">
                                                        <div>
                                                            <div class="fw-bold text-dark mb-0">
                                                                {{ $item->image_name }}
                                                                @if($item->item_type === 'gang_sheet')
                                                                    <span class="badge bg-dark-subtle text-dark border ms-1">Gang Sheet</span>
                                                                @endif
                                                            </div>
                                                            @if($item->image_notes)
                                                                <div class="text-muted smaller">{{ $item->image_notes }}</div>
                                                            @endif
                                                            @if($item->item_type === 'gang_sheet')
                                                                <div class="text-muted smaller">Size: {{ strtoupper(data_get($item->item_meta, 'size_key', $item->width . 'x' . $item->height)) }}</div>
                                                                <a class="smaller text-decoration-none" href="{{ $item->image }}" target="_blank" rel="noopener">Open file</a>
                                                            @endif
                                                        </div>
                                                    </div>
                                                </td>
                                                <td class="text-center">{{ $item->width }}" x {{ $item->height }}"</td>
                                                <td class="text-center fw-bold">{{ $item->quantity }}</td>
                                                <td class="text-center">
                                                    <div class="btn-group btn-group-sm">
                                                        @if($item->item_type === 'gang_sheet')
                                                            <button class="btn btn-outline-secondary fw-bold" type="button" disabled title="Handled manually in phase 1">
                                                                Manual
                                                            </button>
                                                        @else
                                                            <button class="btn {{ $item->production ? 'btn-outline-info' : 'btn-info' }} fw-bold add-image-to-production" data-id="{{ $item->id }}">
                                                                <i class="bi {{ $item->production ? 'bi-arrow-clockwise' : 'bi-plus-circle' }} me-1"></i>
                                                                {{ $item->production ? 'Re-add' : 'Production' }}
                                                            </button>
                                                        @endif
                                                        <a href="{{ route('admin.orders.images.edit', $item->id) }}" class="btn btn-outline-primary fw-bold">
                                                            <i class="bi bi-pencil me-1"></i> Edit
                                                        </a>
                                                        <a href="{{ route('admin.orders.images.download', $item->id) }}" class="btn btn-outline-secondary fw-bold">
                                                            <i class="bi bi-download"></i>
                                                        </a>
                                                        <button
                                                            type="button"
                                                            class="btn btn-outline-dark fw-bold compare-image-btn"
                                                            data-compare-url="{{ route('admin.orders.images.compare', $item->id) }}"
                                                            data-image-name="{{ $item->image_name ?: 'Image #' . $item->id }}"
                                                        >
                                                            <i class="bi bi-layout-split me-1"></i> Compare
                                                        </button>
                                                    </div>
                                                </td>
                                                <td class="text-end pe-4">
                                                    @php
                                                        $unitPrice = ((int)($item->admin_price_locked ?? 0) === 1 && $item->admin_unit_price !== null)
                                                            ? (float)$item->admin_unit_price
                                                            : (float)$item->get_price();
                                                        $lineTotal = (float)$item->get_total();
                                                    @endphp
                                                    <div class="fw-bold">${{ number_format($lineTotal, 2) }}</div>
                                                    <div class="small text-muted">Unit: ${{ number_format($unitPrice, 4) }}</div>
                                                    <div class="d-flex justify-content-end align-items-center gap-1 mb-1">
                                                        @if((int)($item->admin_price_locked ?? 0) === 1)
                                                            <span class="badge bg-warning-subtle text-dark border">Locked</span>
                                                        @endif
                                                        <button
                                                            type="button"
                                                            class="btn btn-sm btn-outline-primary line-price-btn"
                                                            data-route="{{ route('admin.orders.images.pricing.update', [$order, $item]) }}"
                                                            data-unit-price="{{ number_format($unitPrice, 4, '.', '') }}"
                                                            data-image-name="{{ $item->image_name ?: 'Image #' . $item->id }}"
                                                            @if($pricingFrozen) disabled title="Pricing is frozen for invoiced or non-open orders." @endif
                                                        >$?</button>
                                                    </div>
                                                    @if((int)($item->admin_price_locked ?? 0) === 1 && !$pricingFrozen)
                                                        <form method="POST" action="{{ route('admin.orders.images.pricing.clear', [$order, $item]) }}" class="text-end">
                                                            @csrf
                                                            <button type="submit" class="btn btn-sm btn-outline-secondary">Unlock</button>
                                                        </form>
                                                    @endif
                                                </td>
                                            </tr>
                                        @endforeach
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- Shipping Address -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-white border-bottom-0 pt-4 px-4">
                            <div class="d-flex justify-content-between align-items-center">
                                <h5 class="fw-bold mb-0">Shipping Information</h5>
                                <a href="{{ route('admin.orders.shipping', $order) }}" class="btn btn-sm btn-primary fw-bold">
                                    <i class="bi bi-box-seam me-1"></i> Manage Shipping
                                </a>
                            </div>
                        </div>
                        <div class="card-body p-4">
                            @if($order->shippingAddress)
                                <div class="row">
                                    <div class="col-md-6">
                                        <p class="fw-bold mb-1">{{ $order->shippingAddress->name }}</p>
                                        <p class="mb-1 text-secondary">{{ $order->shippingAddress->address1 }}</p>
                                        @if($order->shippingAddress->address2)
                                            <p class="mb-1 text-secondary">{{ $order->shippingAddress->address2 }}</p>
                                        @endif
                                        <p class="mb-0 text-secondary">{{ $order->shippingAddress->city }}, {{ $order->shippingAddress->state }} {{ $order->shippingAddress->zip }}</p>
                                    </div>
                                    <div class="col-md-6 text-md-end border-start">
                                        <label class="small text-uppercase text-muted fw-bold d-block mb-1">Shipping Method</label>
                                        <p class="fw-bold mb-1">{{ $order->shipping_method ?? ($order->shippo_service_name ?? ($order->shippingMethod->method_name ?? 'Standard Shipping')) }}</p>
                                        @if($order->shippo_service_name)
                                            <p class="small text-muted mb-1">Service: {{ $order->shippo_service_name }}</p>
                                        @endif
                                        <p class="small text-muted mb-2">Weight: {{ $order->weight }} lbs</p>
                                        @if($order->shipping_cost > 0)
                                            <p class="text-primary fw-bold mb-0">${{ number_format($order->shipping_cost, 2) }}</p>
                                        @else
                                            <span class="badge bg-success-subtle text-success border border-success-subtle">FREE SHIPPING</span>
                                        @endif
                                    </div>
                                </div>
                            @else
                                <div class="alert alert-warning mb-0">No shipping address recorded for this order.</div>
                            @endif
                        </div>
                    </div>
                </div>

                <!-- Right Column: Totals & Payment -->
                <div class="col-lg-4">
                    <!-- Totals Card -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-primary text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold">Billing Details</h5>
                        </div>
                        <div class="card-body p-4">
                            @if((int)($order->admin_discount_locked ?? 0) === 1)
                                <div class="alert alert-warning py-2 mb-3">
                                    <div class="small fw-bold mb-0">Pricing locked</div>
                                    <div class="small">Discount applied: {{ number_format((float)$order->admin_discount_pct, 2) }}%</div>
                                </div>
                            @endif
                            @if($pricingFrozen)
                                <div class="alert alert-secondary py-2 mb-3">
                                    <div class="small fw-bold mb-0">Pricing Frozen</div>
                                    <div class="small">Invoiced or non-open orders cannot be repriced.</div>
                                </div>
                            @endif
                            <div class="d-flex justify-content-between mb-2">
                                <span class="text-muted">Subtotal</span>
                                <span class="fw-bold">${{ number_format($order->price, 2) }}</span>
                            </div>
                            <div class="d-flex justify-content-between mb-2">
                                <span class="text-muted">Shipping</span>
                                <span class="fw-bold">${{ number_format($order->shipping_cost, 2) }}</span>
                            </div>
                            <div class="d-flex justify-content-between mb-3 pb-3 border-bottom">
                                <span class="text-muted">Tax</span>
                                <span class="fw-bold">${{ number_format($order->sales_tax, 2) }}</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-0">
                                <span class="h5 fw-bold mb-0">Total</span>
                                <span class="h4 fw-bold mb-0 text-primary">${{ number_format($order->total_price, 2) }}</span>
                            </div>
                            <hr>
                            <form method="POST" action="{{ route('admin.orders.pricing.discount', $order) }}" class="d-flex gap-2 align-items-end">
                                @csrf
                                <div class="flex-grow-1">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Order Discount %</label>
                                    <input type="number" name="discount_pct" min="0" max="100" step="0.01" class="form-control form-control-sm" value="{{ number_format((float)($order->admin_discount_pct ?? 0), 2, '.', '') }}" required @if($pricingFrozen) disabled @endif>
                                </div>
                                <button class="btn btn-sm btn-outline-primary fw-bold" type="submit" @if($pricingFrozen) disabled title="Pricing is frozen for invoiced or non-open orders." @endif>Apply + Lock</button>
                            </form>
                            <form method="POST" action="{{ route('admin.orders.pricing.clear', $order) }}" class="mt-2">
                                @csrf
                                <button class="btn btn-sm btn-outline-secondary w-100 fw-bold" type="submit" @if($pricingFrozen) disabled title="Pricing is frozen for invoiced or non-open orders." @endif>Clear Pricing Locks</button>
                            </form>
                        </div>
                    </div>

                    <!-- Change Order Status -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-dark text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold small text-uppercase tracking-wider">Change Status</h5>
                        </div>
                        <div class="card-body p-4">
                            <form method="POST" action="{{ route('admin.orders.update-status') }}">
                                @csrf
                                <input type="hidden" name="order_id" value="{{ $order->id }}">
                                <div class="mb-3">
                                    <select class="form-select py-2" name="order_status" id="order_status">
                                        @foreach($orderStatuses as $status)
                                            <option value="{{ $status->id }}" {{ $order->status == $status->id ? 'selected' : '' }} data-color="{{ $status->color }}">
                                                {{ $status->name }}
                                            </option>
                                        @endforeach
                                    </select>
                                </div>
                                <button class="btn btn-success w-100 fw-bold text-uppercase" type="submit">
                                    <i class="bi bi-check-circle me-1"></i> Update Status
                                </button>
                            </form>
                        </div>
                    </div>

                    <!-- Payment Info -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-white border-bottom-0 pt-4 px-4">
                            <h5 class="fw-bold mb-0">Payment Info</h5>
                        </div>
                        <div class="card-body p-4">
                            <div class="mb-3">
                                <label class="small text-uppercase text-muted fw-bold d-block mb-1">Method</label>
                                <p class="fw-bold mb-0">{{ $order->paymentMethod->method_name ?? 'N/A' }}</p>
                            </div>
                            @if($order->paymentInfo)
                                <div class="mb-3">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Processor</label>
                                    <p class="mb-0">{{ $order->paymentInfo->processor }} ({{ $order->paymentInfo->status }})</p>
                                </div>
                                <div class="mb-0">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Transaction ID</label>
                                    <p class="small text-break mb-0"><code>{{ $order->paymentInfo->processor_confirm }}</code></p>
                                </div>

                                @if($order->paymentInfo && $order->paymentInfo->qbo_payment_id)
                                    <div class="mt-2 p-2 bg-info-subtle border border-info-subtle rounded-3">
                                        <div class="d-flex align-items-center text-info">
                                            <i class="bi bi-cash-coin me-2"></i>
                                            <div>
                                                <div class="fw-bold small text-uppercase">QBO Payment Recorded</div>
                                                <div class="smaller text-muted">Ref #{{ $order->paymentInfo->qbo_payment_id }}</div>
                                            </div>
                                        </div>
                                    </div>
                                @endif

                                @if($order->stripePayoutEntries->count() > 0)
                                    <div class="mt-3 p-2 bg-success-subtle border border-success-subtle rounded-3">
                                        <label class="small text-uppercase text-success fw-bold d-block mb-1">Stripe Payout (Deposit)</label>
                                        @foreach($order->stripePayoutEntries as $entry)
                                            <div class="d-flex justify-content-between align-items-center mb-1">
                                                <span class="small fw-bold">ID: {{ $entry->payout->stripe_payout_id }}</span>
                                                <a href="{{ route('admin.payments.stripe.payouts.show', $entry->stripe_payout_id) }}" class="btn btn-sm btn-link text-success p-0 fw-bold smaller text-decoration-none">
                                                    View Payout
                                                </a>
                                            </div>
                                            <div class="smaller text-muted d-flex justify-content-between">
                                                <span>Arrival: {{ $entry->payout->arrival_date->format('M d, Y') }}</span>
                                                @if($entry->payout->qbo_deposit_id)
                                                    <span class="badge bg-info text-uppercase" style="font-size: 0.6rem;">QBO Deposited</span>
                                                @endif
                                            </div>
                                        @endforeach
                                    </div>
                                @endif
                            @endif

                            @if($order->qbo_invoice_id)
                                <hr>
                                <div class="d-flex align-items-center justify-content-between text-success">
                                    <div class="d-flex align-items-center">
                                        <i class="bi bi-check-circle-fill me-2 fs-5"></i>
                                        <div>
                                            <div class="fw-bold small text-uppercase">QBO Synced</div>
                                            <div class="smaller">Invoice #{{ $order->qbo_invoice_id }}</div>
                                        </div>
                                    </div>
                                    <span class="badge bg-success-subtle text-success border border-success-subtle">LOCKED</span>
                                </div>
                            @else
                                <hr>
                                <form action="{{ route('admin.orders.create-qbo-invoice') }}" method="POST">
                                    @csrf
                                    <input type="hidden" name="order_id" value="{{ $order->id }}">
                                    <button type="submit" class="btn btn-outline-primary w-100 fw-bold text-uppercase btn-sm">
                                        <i class="bi bi-cloud-upload me-1"></i> Sync to QuickBooks
                                    </button>
                                </form>
                            @endif
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Production Progress Modal -->
    <div class="modal fade" id="productionProgressModal" data-bs-backdrop="static" data-bs-keyboard="false" tabindex="-1" aria-labelledby="productionProgressModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow rounded-4">
                <div class="modal-header bg-primary text-white py-3 px-4 border-bottom-0 rounded-top-4">
                    <h5 class="modal-title fw-bold" id="productionProgressModalLabel">Production Processing</h5>
                </div>
                <div class="modal-body p-4 text-center">
                    <div id="progressStatus" class="mb-3 fw-bold">Starting...</div>
                    <div class="progress mb-3" style="height: 25px;">
                        <div id="productionProgressBar" class="progress-bar progress-bar-striped progress-bar-animated bg-success" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                    </div>
                    <div id="progressDetails" class="small text-muted">Please wait while we process the images.</div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="compareModal" tabindex="-1" aria-labelledby="compareModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-centered">
            <div class="modal-content border-0 shadow rounded-4">
                <div class="modal-header py-3 px-4">
                    <h5 class="modal-title fw-bold" id="compareModalLabel">Image Compare</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body p-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div class="small text-muted" id="compareMeta"></div>
                        <div class="d-flex align-items-center gap-2">
                            <a id="compareDownloadProduction" href="#" class="btn btn-sm btn-outline-primary disabled" download>
                                <i class="bi bi-download me-1"></i> Download Production
                            </a>
                            <label for="compareBg" class="small text-muted mb-0">Background</label>
                            <select id="compareBg" class="form-select form-select-sm" style="width: 170px;">
                                <option value="checker">Checker</option>
                                <option value="white">White</option>
                                <option value="lightgray">Light Gray</option>
                                <option value="black">Black</option>
                                <option value="hotpink">Hot Pink</option>
                            </select>
                        </div>
                    </div>
                    <div class="row g-3">
                        <div class="col-md-6">
                            <div class="small text-uppercase text-muted fw-bold mb-2">Original</div>
                            <div class="small text-muted mb-2" id="compareOriginalMeta"></div>
                            <div class="compare-frame rounded border p-2 d-flex align-items-center justify-content-center" data-frame>
                                <div class="compare-stage position-relative" data-stage style="padding-right: 34px; padding-bottom: 30px; display: inline-block;">
                                    <img id="compareOriginalImg" src="" alt="Original" class="img-fluid d-block" style="max-height: 65vh;">
                                    <canvas class="compare-ruler position-absolute" data-ruler-bottom style="left: 0; bottom: 0; height: 30px; pointer-events: none;"></canvas>
                                    <canvas class="compare-ruler position-absolute" data-ruler-right style="right: 0; top: 0; width: 34px; pointer-events: none;"></canvas>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="small text-uppercase text-muted fw-bold mb-2">Production Output (Dropbox)</div>
                            <div class="small text-muted mb-2" id="compareProductionMeta"></div>
                            <div class="compare-frame rounded border p-2 d-flex align-items-center justify-content-center" data-frame>
                                <div class="compare-stage position-relative" data-stage style="padding-right: 34px; padding-bottom: 30px; display: inline-block;">
                                    <img id="compareProcessedImg" src="" alt="Processed" class="img-fluid d-block" style="max-height: 65vh;">
                                    <canvas class="compare-ruler position-absolute" data-ruler-bottom style="left: 0; bottom: 0; height: 30px; pointer-events: none;"></canvas>
                                    <canvas class="compare-ruler position-absolute" data-ruler-right style="right: 0; top: 0; width: 34px; pointer-events: none;"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="linePriceModal" tabindex="-1" aria-labelledby="linePriceModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow rounded-4">
                <div class="modal-header py-3 px-4">
                    <h5 class="modal-title fw-bold" id="linePriceModalLabel">Lock Line Price</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <form id="linePriceForm" method="POST" action="">
                    @csrf
                    <div class="modal-body px-4 pb-3">
                        <div class="small text-muted mb-2" id="linePriceItemName"></div>
                        <label for="linePriceInput" class="small text-uppercase text-muted fw-bold d-block mb-1">Unit Price</label>
                        <input id="linePriceInput" type="number" name="admin_unit_price" min="0" step="0.0001" class="form-control" required>
                    </div>
                    <div class="modal-footer border-0 px-4 pb-4">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-primary fw-bold">Save + Lock</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    @push('scripts')
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const progressModal = new bootstrap.Modal(document.getElementById('productionProgressModal'));
            const compareModalEl = document.getElementById('compareModal');
            const compareModal = new bootstrap.Modal(compareModalEl);
            const linePriceModalEl = document.getElementById('linePriceModal');
            const linePriceModal = new bootstrap.Modal(linePriceModalEl);
            const progressBar = document.getElementById('productionProgressBar');
            const progressStatus = document.getElementById('progressStatus');
            const progressDetails = document.getElementById('progressDetails');
            const linePriceForm = document.getElementById('linePriceForm');
            const linePriceInput = document.getElementById('linePriceInput');
            const linePriceItemName = document.getElementById('linePriceItemName');
            const compareOriginalImg = document.getElementById('compareOriginalImg');
            const compareProcessedImg = document.getElementById('compareProcessedImg');
            const compareMeta = document.getElementById('compareMeta');
            const compareOriginalMeta = document.getElementById('compareOriginalMeta');
            const compareProductionMeta = document.getElementById('compareProductionMeta');
            const compareDownloadProduction = document.getElementById('compareDownloadProduction');
            const compareBg = document.getElementById('compareBg');
            let compareOriginalWidthIn = 0;
            let compareOriginalHeightIn = 0;
            let compareProductionWidthIn = 0;
            let compareProductionHeightIn = 0;
            let compareRulerRaf = null;

            function applyCompareBackground(mode) {
                document.querySelectorAll('[data-frame]').forEach((frame) => {
                    frame.style.backgroundImage = 'none';
                    frame.style.backgroundSize = '';
                    frame.style.backgroundPosition = '';
                    frame.style.backgroundColor = '#ffffff';

                    if (mode === 'checker') {
                        frame.style.backgroundImage = 'linear-gradient(45deg, #e6e6e6 25%, transparent 25%), linear-gradient(-45deg, #e6e6e6 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #e6e6e6 75%), linear-gradient(-45deg, transparent 75%, #e6e6e6 75%)';
                        frame.style.backgroundSize = '20px 20px';
                        frame.style.backgroundPosition = '0 0, 0 10px, 10px -10px, -10px 0px';
                    } else if (mode === 'white') {
                        frame.style.backgroundColor = '#ffffff';
                    } else if (mode === 'lightgray') {
                        frame.style.backgroundColor = '#e9ecef';
                    } else if (mode === 'black') {
                        frame.style.backgroundColor = '#000000';
                    } else if (mode === 'hotpink') {
                        frame.style.backgroundColor = '#ff69b4';
                    }
                });
            }

            function isWholeNumber(value) {
                return Math.abs(value - Math.round(value)) < 0.001;
            }

            function setCanvasSize(canvas, width, height) {
                const dpr = window.devicePixelRatio || 1;
                canvas.style.width = `${width}px`;
                canvas.style.height = `${height}px`;
                canvas.width = Math.max(1, Math.round(width * dpr));
                canvas.height = Math.max(1, Math.round(height * dpr));
                const ctx = canvas.getContext('2d');
                ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
                return ctx;
            }

            function drawBottomRuler(canvas, widthPx, widthIn) {
                const heightPx = 30;
                const ctx = setCanvasSize(canvas, widthPx, heightPx);
                ctx.clearRect(0, 0, widthPx, heightPx);
                ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
                ctx.fillRect(0, 0, widthPx, heightPx);
                ctx.strokeStyle = '#1f2937';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(0, 0.5);
                ctx.lineTo(widthPx, 0.5);
                ctx.stroke();

                const stepIn = 0.25;
                const pxPerIn = widthPx / widthIn;
                ctx.font = '11px sans-serif';
                ctx.fillStyle = '#111827';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';

                for (let inch = 0; inch <= widthIn + 0.001; inch += stepIn) {
                    const x = Math.min(widthPx, Math.max(0, inch * pxPerIn));
                    const major = isWholeNumber(inch);
                    const half = isWholeNumber(inch * 2);
                    const tick = major ? 12 : (half ? 9 : 6);

                    ctx.beginPath();
                    ctx.moveTo(x + 0.5, 0);
                    ctx.lineTo(x + 0.5, tick);
                    ctx.stroke();

                    if (major) {
                        ctx.fillText(`${Math.round(inch)}"`, x, 14);
                    }
                }
            }

            function drawRightRuler(canvas, heightPx, heightIn) {
                const widthPx = 34;
                const ctx = setCanvasSize(canvas, widthPx, heightPx);
                ctx.clearRect(0, 0, widthPx, heightPx);
                ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
                ctx.fillRect(0, 0, widthPx, heightPx);
                ctx.strokeStyle = '#1f2937';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(0.5, 0);
                ctx.lineTo(0.5, heightPx);
                ctx.stroke();

                const stepIn = 0.25;
                const pxPerIn = heightPx / heightIn;
                ctx.font = '11px sans-serif';
                ctx.fillStyle = '#111827';
                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';

                for (let inch = 0; inch <= heightIn + 0.001; inch += stepIn) {
                    const y = Math.min(heightPx, Math.max(0, inch * pxPerIn));
                    const major = isWholeNumber(inch);
                    const half = isWholeNumber(inch * 2);
                    const tick = major ? 12 : (half ? 9 : 6);

                    ctx.beginPath();
                    ctx.moveTo(0, y + 0.5);
                    ctx.lineTo(tick, y + 0.5);
                    ctx.stroke();

                    if (major) {
                        ctx.fillText(`${Math.round(inch)}"`, 14, y);
                    }
                }
            }

            function drawStageRulers(stage, widthIn, heightIn) {
                if (!stage || widthIn <= 0 || heightIn <= 0) {
                    return;
                }

                const img = stage.querySelector('img');
                const bottomCanvas = stage.querySelector('[data-ruler-bottom]');
                const rightCanvas = stage.querySelector('[data-ruler-right]');

                if (!img || !bottomCanvas || !rightCanvas || !img.complete || !img.naturalWidth) {
                    return;
                }

                const widthPx = img.clientWidth;
                const heightPx = img.clientHeight;
                if (!widthPx || !heightPx) {
                    return;
                }

                bottomCanvas.style.left = `${img.offsetLeft}px`;
                bottomCanvas.style.top = `${img.offsetTop + heightPx}px`;
                rightCanvas.style.left = `${img.offsetLeft + widthPx}px`;
                rightCanvas.style.top = `${img.offsetTop}px`;

                drawBottomRuler(bottomCanvas, widthPx, widthIn);
                drawRightRuler(rightCanvas, heightPx, heightIn);
            }

            function queueCompareRulerDraw() {
                if (compareRulerRaf !== null) {
                    cancelAnimationFrame(compareRulerRaf);
                }

                compareRulerRaf = requestAnimationFrame(() => {
                    compareRulerRaf = null;
                    const stages = compareModalEl.querySelectorAll('[data-stage]');
                    if (stages[0]) {
                        drawStageRulers(stages[0], compareOriginalWidthIn, compareOriginalHeightIn);
                    }
                    if (stages[1]) {
                        drawStageRulers(stages[1], compareProductionWidthIn, compareProductionHeightIn);
                    }
                });
            }

            compareBg.addEventListener('change', function() {
                applyCompareBackground(this.value);
            });
            applyCompareBackground(compareBg.value);
            compareOriginalImg.addEventListener('load', queueCompareRulerDraw);
            compareProcessedImg.addEventListener('load', queueCompareRulerDraw);
            compareModalEl.addEventListener('shown.bs.modal', queueCompareRulerDraw);
            window.addEventListener('resize', queueCompareRulerDraw);

            async function processImage(imageId, index, total, options = {}) {
                const percent = Math.round(((index) / total) * 100);
                progressBar.style.width = percent + '%';
                progressBar.innerText = percent + '%';
                progressBar.setAttribute('aria-valuenow', percent);
                progressStatus.innerText = `Processing image ${index + 1} of ${total}...`;
                progressDetails.innerText = `Currently processing Image ID: ${imageId}`;

                try {
                    const response = await fetch("{{ route('admin.orders.add-to-production') }}", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRF-TOKEN": "{{ csrf_token() }}"
                        },
                        body: JSON.stringify({ image_id: imageId, readd: !!options.readd })
                    });

                    const data = await response.json();
                    if (data.status !== 'success') {
                        throw new Error(data.message || 'Unknown error');
                    }
                    return true;
                } catch (err) {
                    console.error(err);
                    alert(`Error processing image ${imageId}: ${err.message}`);
                    return false;
                }
            }

            document.querySelectorAll('.add-image-to-production').forEach(btn => {
                btn.addEventListener('click', async function() {
                    const id = this.dataset.id;
                    const isReadd = this.innerText.includes('Re-add');
                    const confirmMsg = isReadd ? 'Re-add this image to production? This will overwrite the existing file in Dropbox.' : 'Add this image to production?';

                    if (!confirm(confirmMsg)) return;

                    progressModal.show();

                    const success = await processImage(id, 0, 1, { readd: isReadd });

                    if (success) {
                        progressBar.style.width = '100%';
                        progressBar.innerText = '100%';
                        progressStatus.innerText = 'Completed!';
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        progressModal.hide();
                    }
                });
            });

            document.querySelectorAll('.compare-image-btn').forEach((btn) => {
                btn.addEventListener('click', async function() {
                    const compareUrl = this.dataset.compareUrl;
                    const imageName = this.dataset.imageName || 'Image Compare';

                    compareOriginalWidthIn = 0;
                    compareOriginalHeightIn = 0;
                    compareProductionWidthIn = 0;
                    compareProductionHeightIn = 0;
                    compareOriginalImg.removeAttribute('src');
                    compareProcessedImg.removeAttribute('src');
                    compareMeta.textContent = 'Preparing comparison...';
                    compareOriginalMeta.textContent = '';
                    compareProductionMeta.textContent = '';
                    compareDownloadProduction.setAttribute('href', '#');
                    compareDownloadProduction.classList.add('disabled');
                    compareDownloadProduction.removeAttribute('download');
                    compareModal.show();

                    try {
                        const response = await fetch(compareUrl, {
                            headers: { 'X-Requested-With': 'XMLHttpRequest' }
                        });
                        const data = await response.json();

                        if (!response.ok || !data.success) {
                            throw new Error(data.message || 'Failed to generate comparison.');
                        }

                        const cacheBust = `v=${Date.now()}`;
                        compareOriginalImg.src = `${data.original_url}?${cacheBust}`;
                        compareProcessedImg.src = `${data.production_url}?${cacheBust}`;
                        compareOriginalWidthIn = Number(data.original_width_in) || 0;
                        compareOriginalHeightIn = Number(data.original_height_in) || 0;
                        compareProductionWidthIn = Number(data.production_width_in) || 0;
                        compareProductionHeightIn = Number(data.production_height_in) || 0;
                        compareMeta.textContent = imageName;
                        compareOriginalMeta.textContent = `Original size: ${compareOriginalWidthIn.toFixed(2)}" x ${compareOriginalHeightIn.toFixed(2)}"`;
                        compareProductionMeta.textContent = `Production size: ${compareProductionWidthIn.toFixed(2)}" x ${compareProductionHeightIn.toFixed(2)}"`;
                        compareDownloadProduction.href = `${data.production_url}?${cacheBust}`;
                        compareDownloadProduction.setAttribute('download', `production_${imageName.replace(/[^a-z0-9_\-]+/gi, '_')}.png`);
                        compareDownloadProduction.classList.remove('disabled');
                        queueCompareRulerDraw();
                    } catch (err) {
                        compareOriginalWidthIn = 0;
                        compareOriginalHeightIn = 0;
                        compareProductionWidthIn = 0;
                        compareProductionHeightIn = 0;
                        compareMeta.textContent = '';
                        compareOriginalMeta.textContent = '';
                        compareProductionMeta.textContent = '';
                        compareDownloadProduction.setAttribute('href', '#');
                        compareDownloadProduction.classList.add('disabled');
                        compareDownloadProduction.removeAttribute('download');
                        compareOriginalImg.removeAttribute('src');
                        compareProcessedImg.removeAttribute('src');
                        alert(err.message || 'Unable to build compare preview.');
                        compareModal.hide();
                    }
                });
            });

            document.querySelectorAll('.line-price-btn').forEach((btn) => {
                btn.addEventListener('click', function() {
                    linePriceForm.setAttribute('action', this.dataset.route || '');
                    linePriceInput.value = this.dataset.unitPrice || '0.0000';
                    linePriceItemName.textContent = this.dataset.imageName || 'Line Item';
                    linePriceModal.show();
                });
            });

            // Status select styling
            const statusSelect = document.getElementById('order_status');
            if (statusSelect) {
                function updateSelectStyle() {
                    const selected = statusSelect.options[statusSelect.selectedIndex];
                    const color = selected.dataset.color;
                    if (color) {
                        statusSelect.style.borderLeft = `5px solid ${color}`;
                    }
                }
                statusSelect.addEventListener('change', updateSelectStyle);
                updateSelectStyle();
            }
        });
    </script>
    @endpush
</x-app-layout>
