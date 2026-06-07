<x-app-layout>
    <x-slot name="header">
        <div class="d-flex align-items-center justify-content-between">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                Shipping Management: #{{ $order->id }}
            </h2>
            <a href="{{ route('admin.orders.show', $order) }}" class="btn btn-outline-secondary btn-sm fw-bold">
                <i class="bi bi-arrow-left me-1"></i> Back to Order
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row g-4">
                <div class="col-lg-8">
                    @if($isPickup)
                        <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4 border-start border-warning border-5">
                            <div class="card-body p-4">
                                <div class="d-flex align-items-center">
                                    <div class="flex-shrink-0 bg-warning-subtle text-warning p-3 rounded-3 me-3">
                                        <i class="bi bi-geo-alt-fill fs-3"></i>
                                    </div>
                                    <div>
                                        <h5 class="fw-bold mb-1">Local Pickup Order</h5>
                                        <p class="text-muted mb-3">This order is marked for local pickup. No shipping label is required.</p>

                                        @if($order->status == 14)
                                            <div class="alert alert-success d-inline-block py-2 px-3 mb-0">
                                                <i class="bi bi-check-circle-fill me-2"></i> Order has been picked up (Pickup Complete)
                                            </div>
                                        @elseif($order->status == 5)
                                            <form action="{{ route('admin.orders.mark-picked-up', $order) }}" method="POST">
                                                @csrf
                                                <button type="submit" class="btn btn-success fw-bold">
                                                    Mark Picked Up
                                                </button>
                                            </form>
                                        @else
                                            <form action="{{ route('admin.orders.ready-for-pickup', $order) }}" method="POST">
                                                @csrf
                                                <button type="submit" class="btn btn-warning fw-bold">
                                                    Mark as Ready for Pickup
                                                </button>
                                            </form>
                                        @endif
                                    </div>
                                </div>
                            </div>
                        </div>
                    @endif

                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-dark text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold">Shipping Details</h5>
                        </div>
                        <div class="card-body p-4">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6 class="text-uppercase small text-muted fw-bold mb-3">Ship To:</h6>
                                    @if($order->shippingAddress)
                                        <p class="fw-bold mb-1">{{ $order->shippingAddress->name }}</p>
                                        <p class="mb-1 text-secondary">{{ $order->shippingAddress->address1 }}</p>
                                        @if($order->shippingAddress->address2)
                                            <p class="mb-1 text-secondary">{{ $order->shippingAddress->address2 }}</p>
                                        @endif
                                        <p class="mb-0 text-secondary">{{ $order->shippingAddress->city }}, {{ $order->shippingAddress->state }} {{ $order->shippingAddress->zip }}</p>
                                    @else
                                        <p class="text-danger">No shipping address provided.</p>
                                    @endif
                                </div>
                                <div class="col-md-6 border-start">
                                    <h6 class="text-uppercase small text-muted fw-bold mb-3">Selected Method:</h6>
                                    <p class="fw-bold mb-1">{{ $order->shipping_method ?? 'None' }}</p>
                                    <p class="text-primary fw-bold mb-0">Cost: ${{ number_format($order->shipping_cost, 2) }}</p>

                                    <hr class="my-3">

                                    <h6 class="text-uppercase small text-muted fw-bold mb-2">Package Weight:</h6>
                                    <div class="input-group input-group-sm" style="max-width: 150px;">
                                        <input type="number" step="0.1" class="form-control" id="package_weight" value="{{ $order->weight ?: 1 }}">
                                        <span class="input-group-text">lbs</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    @if(!$isPickup)
                        <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                            <div class="card-header bg-white border-bottom py-3 px-4">
                                <div class="d-flex justify-content-between align-items-center">
                                    <h5 class="mb-0 fw-bold">Shippo Rates</h5>
                                    <button id="btn-fetch-rates" class="btn btn-sm btn-outline-primary fw-bold">
                                        <i class="bi bi-arrow-clockwise me-1"></i> Get Live Rates
                                    </button>
                                </div>
                            </div>
                            <div class="card-body p-0">
                                <div id="rates-loading" class="p-4 text-center d-none">
                                    <div class="spinner-border text-primary mb-2" role="status"></div>
                                    <p class="text-muted mb-0">Fetching live rates from Shippo...</p>
                                </div>
                                <div id="rates-error" class="p-4 text-center d-none">
                                    <div class="alert alert-danger mb-0"></div>
                                </div>
                                <div class="table-responsive">
                                    <table class="table align-middle mb-0 d-none" id="rates-table">
                                        <thead class="bg-light">
                                            <tr>
                                                <th class="ps-4 py-3">Carrier / Service</th>
                                                <th class="py-3 text-center">Delivery Time</th>
                                                <th class="py-3 text-end">Price</th>
                                                <th class="pe-4 py-3 text-end">Action</th>
                                            </tr>
                                        </thead>
                                        <tbody></tbody>
                                    </table>
                                </div>
                                <div id="no-rates" class="p-5 text-center">
                                    <p class="text-muted mb-0">Click "Get Live Rates" to see available shipping options.</p>
                                </div>
                            </div>
                        </div>
                    @endif
                </div>

                <div class="col-lg-4">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-success text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold">Shipment Status</h5>
                        </div>
                        <div class="card-body p-4">
                            @if($order->tracking_number)
                                <div class="mb-4">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Tracking Number</label>
                                    <p class="fs-5 fw-bold mb-1">{{ $order->tracking_number }}</p>
                                    <a href="https://www.ups.com/track?tracknum={{ $order->tracking_number }}" target="_blank" class="small text-decoration-none">
                                        <i class="bi bi-box-arrow-up-right me-1"></i> Track on UPS
                                    </a>
                                </div>
                                @if($order->label_url)
                                    <div class="d-grid">
                                        <a href="{{ $order->label_url }}" target="_blank" class="btn btn-primary fw-bold">
                                            <i class="bi bi-printer me-1"></i> Print Label
                                        </a>
                                    </div>
                                @endif
                            @else
                                <div class="text-center py-3">
                                    <i class="bi bi-truck text-muted fs-1 mb-3 d-block"></i>
                                    <p class="text-muted">No label created yet.</p>
                                </div>
                            @endif
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    @push('scripts')
    <script>
        document.getElementById('btn-fetch-rates')?.addEventListener('click', function() {
            const table = document.getElementById('rates-table');
            const loading = document.getElementById('rates-loading');
            const errorDiv = document.getElementById('rates-error');
            const noRates = document.getElementById('no-rates');
            const tbody = table.querySelector('tbody');
            const weight = document.getElementById('package_weight').value;

            loading.classList.remove('d-none');
            table.classList.add('d-none');
            errorDiv.classList.add('d-none');
            noRates.classList.add('d-none');
            tbody.innerHTML = '';

            fetch(`{{ route('admin.orders.shipping.rates', $order) }}?weight=${weight}`)
                .then(response => response.json())
                .then(data => {
                    loading.classList.add('d-none');
                    if (data.error) {
                        errorDiv.classList.remove('d-none');
                        errorDiv.querySelector('.alert').textContent = data.error;
                    } else if (data.rates && data.rates.length > 0) {
                        table.classList.remove('d-none');
                        data.rates.forEach(rate => {
                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td class="ps-4">
                                    <div class="d-flex align-items-center">
                                        <img src="${rate.provider_image_75}" style="width: 40px;" class="me-3">
                                        <div>
                                            <div class="fw-bold">${rate.provider} ${rate.servicelevel.name}</div>
                                            <div class="text-muted smaller">${rate.servicelevel.token}</div>
                                        </div>
                                    </div>
                                </td>
                                <td class="text-center">${rate.duration_terms || 'N/A'}</td>
                                <td class="text-end fw-bold text-primary">$${rate.amount}</td>
                                <td class="pe-4 text-end">
                                    <button class="btn btn-sm btn-success fw-bold btn-create-label" data-rate-id="${rate.object_id}">
                                        Buy Label
                                    </button>
                                </td>
                            `;
                            tbody.appendChild(tr);
                        });

                        attachLabelEvents();
                    } else {
                        noRates.classList.remove('d-none');
                        noRates.querySelector('p').textContent = 'No rates available for this weight/address.';
                    }
                })
                .catch(err => {
                    loading.classList.add('d-none');
                    errorDiv.classList.remove('d-none');
                    errorDiv.querySelector('.alert').textContent = 'An error occurred while fetching rates.';
                    console.error(err);
                });
        });

        function attachLabelEvents() {
            document.querySelectorAll('.btn-create-label').forEach(btn => {
                btn.addEventListener('click', function() {
                    if (!confirm('Are you sure you want to purchase this label?')) return;

                    const rateId = this.getAttribute('data-rate-id');
                    this.disabled = true;
                    this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Buying...';

                    fetch(`{{ route('admin.orders.shipping.label', $order) }}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRF-TOKEN': '{{ csrf_token() }}'
                        },
                        body: JSON.stringify({ rate_id: rateId })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            window.location.reload();
                        } else {
                            alert('Error: ' + (data.message || 'Failed to create label.'));
                            this.disabled = false;
                            this.innerHTML = 'Buy Label';
                        }
                    })
                    .catch(err => {
                        alert('An unexpected error occurred.');
                        this.disabled = false;
                        this.innerHTML = 'Buy Label';
                        console.error(err);
                    });
                });
            });
        }
    </script>
    @endpush
</x-app-layout>
