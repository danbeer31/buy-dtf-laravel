<x-app-layout>
    <x-slot name="header">
        <div class="d-flex align-items-center justify-content-between">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                Production Order #{{ $order->id }}
            </h2>
            <a href="{{ route('admin.orders.production') }}" class="btn btn-outline-secondary btn-sm fw-bold">
                <i class="bi bi-arrow-left me-1"></i> Back to Production
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            @if(session('success'))
                <div class="alert alert-success border-0 shadow-sm rounded-4 mb-4">
                    {{ session('success') }}
                </div>
            @endif

            <!-- Order Header Status -->
            <div class="text-center mb-5">
                <h1 class="display-5 fw-bold font-ubuntu mb-2">Production Order #{{ $order->id }}</h1>
                <div class="d-flex justify-content-center align-items-center gap-2">
                    <span class="badge fs-5 px-4 py-2" style="background-color: {{ $order->orderStatus->color ?? '#6c757d' }}22; color: {{ $order->orderStatus->color ?? '#6c757d' }}; border: 1px solid {{ $order->orderStatus->color ?? '#6c757d' }}44;">
                        {{ $order->orderStatus->name ?? 'Unknown' }}
                    </span>
                    @if($order->isPaid())
                        <span class="badge bg-success fs-5 px-4 py-2">PAID</span>
                    @else
                        <span class="badge bg-danger fs-5 px-4 py-2">UNPAID</span>
                    @endif
                </div>
            </div>

            <!-- Summary Cards -->
            <div class="row g-4 mb-5">
                <!-- Customer Details -->
                <div class="col-md-4">
                    <div class="card h-100 border-0 shadow-sm rounded-4">
                        <div class="card-header bg-primary text-white py-3 px-4 border-bottom-0 rounded-top-4">
                            <h5 class="fw-bold mb-0 small text-uppercase tracking-wider">Customer Detail</h5>
                        </div>
                        <div class="card-body p-4">
                            <div class="mb-3">
                                <label class="small text-muted text-uppercase fw-bold d-block">Business Name</label>
                                <p class="mb-0 fw-bold">{{ $order->business->business_name }}</p>
                            </div>
                            <div class="mb-3">
                                <label class="small text-muted text-uppercase fw-bold d-block">Contact Name</label>
                                <p class="mb-0">{{ $order->business->contact_name }}</p>
                            </div>
                            <div class="mb-3">
                                <label class="small text-muted text-uppercase fw-bold d-block">Email</label>
                                <p class="mb-0 small"><a href="mailto:{{ $order->business->email }}" class="text-decoration-none">{{ $order->business->email }}</a></p>
                            </div>
                            <div class="mb-3">
                                <label class="small text-muted text-uppercase fw-bold d-block">Phone</label>
                                <p class="mb-0 small">{{ $order->business->phone }}</p>
                            </div>
                            <div>
                                <label class="small text-muted text-uppercase fw-bold d-block">Address</label>
                                <p class="mb-0 small">
                                    {{ $order->business->address }}<br>
                                    {{ $order->business->city }}, {{ $order->business->state }} {{ $order->business->zip }}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Order Summary -->
                <div class="col-md-4">
                    <div class="card h-100 border-0 shadow-sm rounded-4">
                        <div class="card-header bg-primary text-white py-3 px-4 border-bottom-0 rounded-top-4">
                            <h5 class="fw-bold mb-0 small text-uppercase tracking-wider">Order Summary</h5>
                        </div>
                        <div class="card-body p-4">
                            <div class="mb-3">
                                <label class="small text-muted text-uppercase fw-bold d-block">Order ID</label>
                                <p class="mb-0 fw-bold">#{{ $order->id }}</p>
                            </div>
                            <div class="mb-3">
                                <label class="small text-muted text-uppercase fw-bold d-block">Order Date</label>
                                <p class="mb-0">{{ $order->order_date ? $order->order_date->format('F d, Y') : 'N/A' }}</p>
                            </div>
                            <div class="mb-3">
                                <label class="small text-muted text-uppercase fw-bold d-block">Order Total</label>
                                <p class="mb-0 fw-bold text-primary">${{ number_format($order->get_total(), 2) }}</p>
                            </div>
                            <div class="mb-3">
                                <label class="small text-muted text-uppercase fw-bold d-block">Payment Method</label>
                                <p class="mb-0 small">{{ $order->paymentMethod->method_name ?? 'N/A' }}</p>
                            </div>
                            <div>
                                <label class="small text-muted text-uppercase fw-bold d-block">Metrics (L / S)</label>
                                <p class="mb-0 fw-bold">{{ $order->linear_inches }} in / {{ $order->square_inches }} sq in</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Shipping Details -->
                <div class="col-md-4">
                    <div class="card h-100 border-0 shadow-sm rounded-4">
                        <div class="card-header bg-primary text-white py-3 px-4 border-bottom-0 rounded-top-4">
                            <h5 class="fw-bold mb-0 small text-uppercase tracking-wider">Shipping Details</h5>
                        </div>
                        <div class="card-body p-4">
                            @if($order->shippingAddress)
                                <div class="mb-3">
                                    <label class="small text-muted text-uppercase fw-bold d-block">Ship To</label>
                                    <p class="mb-0 fw-bold">{{ $order->shippingAddress->name }}</p>
                                    <p class="mb-0 small">
                                        {{ $order->shippingAddress->address1 }}<br>
                                        @if($order->shippingAddress->address2){{ $order->shippingAddress->address2 }}<br>@endif
                                        {{ $order->shippingAddress->city }}, {{ $order->shippingAddress->state }} {{ $order->shippingAddress->zip }}
                                    </p>
                                </div>
                            @endif
                            @if($order->paymentMethod)
                                <div class="mt-3 pt-3 border-top">
                                    <label class="small text-muted text-uppercase fw-bold d-block">Shipping Cost</label>
                                    <p class="mb-0 fw-bold text-primary">${{ number_format($order->shipping_cost, 2) }}</p>
                                </div>
                            @endif
                        </div>
                    </div>
                </div>
            </div>

            <!-- Items in Order -->
            <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-5">
                <div class="card-header bg-white py-3 px-4 border-bottom-0">
                    <h4 class="fw-bold mb-0 font-ubuntu">Items in this Order</h4>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table align-middle mb-0">
                            <thead class="bg-light">
                                <tr>
                                    <th class="ps-4 py-3 text-uppercase small fw-bold text-muted text-center" style="width: 100px;">Image</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Image Name</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-center">Quantity</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-center">Width</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-center">Height</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-center">Status</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($order->dtfImages as $img)
                                    <tr>
                                        <td class="ps-4 py-3 text-center">
                                            @if($img->image)
                                                <img src="{{ $img->image }}" class="img-thumbnail shadow-sm" style="max-width: 70px; max-height: 70px;">
                                            @endif
                                        </td>
                                        <td class="py-3">
                                            <div class="fw-bold text-dark">
                                                {{ $img->image_name }}
                                                @if($img->item_type === 'gang_sheet')
                                                    <span class="badge bg-dark-subtle text-dark border ms-1">Gang Sheet</span>
                                                @endif
                                            </div>
                                            <div class="text-muted smaller">Uploaded: {{ $img->date_uploaded ? $img->date_uploaded->format('m-d-Y') : 'N/A' }}</div>
                                            @if($img->item_type === 'gang_sheet')
                                                <div class="text-muted smaller">Size: {{ strtoupper(data_get($img->item_meta, 'size_key', $img->width . 'x' . $img->height)) }}</div>
                                                <a class="smaller text-decoration-none" href="{{ $img->image }}" target="_blank" rel="noopener">Open file</a>
                                            @endif
                                        </td>
                                        <td class="py-3 text-center fw-bold">{{ $img->quantity }}</td>
                                        <td class="py-3 text-center">{{ $img->width }}"</td>
                                        <td class="py-3 text-center">{{ $img->height }}"</td>
                                        <td class="py-3 text-center">
                                            @if($img->production)
                                                <span class="text-success fs-4" title="In Production"><i class="bi bi-check-circle-fill"></i></span>
                                            @else
                                                <span class="text-danger fs-4" title="Not in Production"><i class="bi bi-x-circle-fill"></i></span>
                                            @endif
                                        </td>
                                        <td class="py-3 text-end pe-4">
                                            @if($img->item_type === 'gang_sheet')
                                                <button class="btn btn-sm btn-outline-secondary fw-bold" type="button" disabled title="Handled manually in phase 1">
                                                    Manual
                                                </button>
                                            @else
                                                <button class="btn btn-sm {{ $img->production ? 'btn-outline-info' : 'btn-info' }} fw-bold add-image-to-production" data-id="{{ $img->id }}">
                                                    <i class="bi {{ $img->production ? 'bi-arrow-clockwise' : 'bi-plus-circle' }} me-1"></i>
                                                    {{ $img->production ? 'Re-add' : 'Production' }}
                                                </button>
                                            @endif
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="7" class="text-center py-5 text-muted small">
                                            <i class="bi bi-info-circle me-1"></i> No items found for this order.
                                        </td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="row g-4 mb-5">
                <!-- Change Order Status -->
                <div class="col-md-4 ms-auto">
                    <div class="card border-0 shadow-sm rounded-4 overflow-hidden">
                        <div class="card-header bg-primary text-white py-3 px-4 border-bottom-0">
                            <h5 class="fw-bold mb-0 small text-uppercase tracking-wider">Change Order Status</h5>
                        </div>
                        <div class="card-body p-4">
                            <form method="POST" action="{{ route('admin.orders.update-status') }}">
                                @csrf
                                <input type="hidden" name="order_id" value="{{ $order->id }}">
                                <div class="mb-4">
                                    <label for="order_status" class="form-label fw-bold small text-muted text-uppercase">New Status</label>
                                    <select class="form-select custom-select py-2" name="order_status" id="order_status">
                                        @foreach($orderStatuses as $status)
                                            <option value="{{ $status->id }}" {{ $order->status == $status->id ? 'selected' : '' }} data-color="{{ $status->color }}">
                                                {{ $status->name }}
                                            </option>
                                        @endforeach
                                    </select>
                                </div>
                                <button class="btn btn-success w-100 py-3 fw-bold text-uppercase shadow-sm" type="submit">
                                    <i class="bi bi-check-circle me-1"></i> Update Status
                                </button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Global Action Buttons -->
            <div class="text-end d-flex justify-content-end gap-2 flex-wrap pb-5">
                <a href="{{ route('admin.orders.production') }}" class="btn btn-secondary btn-lg px-4 fw-bold rounded-3 shadow-sm">
                    <i class="bi bi-arrow-left me-1"></i> Back to Production
                </a>

                @php
                    $eligibleImages = $order->dtfImages->filter(fn($img) => $img->item_type !== 'gang_sheet');
                    $pendingImages = $eligibleImages->where('production', 0);
                    $allImages = $eligibleImages;
                @endphp

                @if($pendingImages->count() > 0)
                    <button class="btn btn-info btn-lg px-4 fw-bold rounded-3 shadow-sm add-order-to-production"
                            data-id="{{ $order->id }}"
                            data-mode="new"
                            data-images="{{ json_encode($pendingImages->pluck('id')->toArray()) }}">
                        <i class="bi bi-plus-circle me-1"></i> Production ({{ $pendingImages->count() }} New)
                    </button>
                @endif

                <button class="btn btn-outline-info btn-lg px-4 fw-bold rounded-3 shadow-sm add-order-to-production"
                        data-id="{{ $order->id }}"
                        data-mode="all"
                        data-images="{{ json_encode($allImages->pluck('id')->toArray()) }}">
                    <i class="bi bi-arrow-clockwise me-1"></i> Production (All)
                </button>

                @if(!$order->qbo_invoice_id)
                    <form method="POST" action="{{ route('admin.orders.create-qbo-invoice') }}" class="d-inline qbo-invoice-form">
                        @csrf
                        <input type="hidden" name="order_id" value="{{ $order->id }}">
                        <button type="submit" class="btn btn-primary btn-lg px-4 fw-bold rounded-3 shadow-sm qbo-invoice-btn">
                            <i class="bi bi-receipt me-1"></i> Create QBO Invoice
                        </button>
                    </form>
                @endif
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
                    <div id="progressDetails" class="small text-muted">Please wait while we process your images.</div>
                </div>
            </div>
        </div>
    </div>

    @push('scripts')
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const progressModal = new bootstrap.Modal(document.getElementById('productionProgressModal'));
            const progressBar = document.getElementById('productionProgressBar');
            const progressStatus = document.getElementById('progressStatus');
            const progressDetails = document.getElementById('progressDetails');

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

            // Production actions
            async function processOrder(orderId, imageCount, mode) {
                progressBar.style.width = '5%';
                progressBar.innerText = '5%';
                progressBar.setAttribute('aria-valuenow', '5');
                progressStatus.innerText = 'Processing order...';
                progressDetails.innerText = `Consolidating duplicate images before Dropbox upload.`;

                try {
                    const response = await fetch("{{ route('admin.orders.add-to-production') }}", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRF-TOKEN": "{{ csrf_token() }}"
                        },
                        body: JSON.stringify({ order_id: orderId, production_mode: mode || 'new' })
                    });

                    const data = await response.json();
                    if (data.status !== 'success') {
                        throw new Error(data.message || 'Unknown error');
                    }

                    progressDetails.innerText = `Uploaded ${data.groups_processed || 0} production groups from ${data.images_processed || imageCount} image rows.`;
                    return true;
                } catch (err) {
                    console.error(err);
                    alert(`Error processing order ${orderId}: ${err.message}`);
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

            document.querySelectorAll('.add-order-to-production').forEach(btn => {
                btn.addEventListener('click', async function() {
                    const imageIds = JSON.parse(this.dataset.images || '[]');
                    const orderId = this.dataset.id;
                    const mode = this.dataset.mode || 'new';

                    if (imageIds.length === 0) {
                        alert('No images to process.');
                        return;
                    }

                    const message = imageIds.length > 1
                        ? `Add ${imageIds.length} images to production?`
                        : 'Add this image to production?';

                    if (!confirm(message)) return;

                    progressModal.show();

                    const success = await processOrder(orderId, imageIds.length, mode);

                    if (success) {
                        progressBar.style.width = '100%';
                        progressBar.innerText = '100%';
                        progressStatus.innerText = 'Order processing completed!';

                        // After all images are done, if it was an order-level action,
                        // we should probably refresh to see updated status.
                        setTimeout(() => window.location.reload(), 800);
                    } else {
                        progressStatus.innerText = 'Processing finished with errors.';
                        progressDetails.innerText = 'Please check the errors and try again.';
                        // Add a close button or just let them reload
                        setTimeout(() => window.location.reload(), 3000);
                    }
                });
            });

            // Status select styling (mimicking legacy color hints)
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
