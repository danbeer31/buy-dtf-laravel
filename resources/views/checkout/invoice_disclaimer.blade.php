<x-app-layout>
    <x-slot name="header">
        <div class="container">
            <div class="d-flex align-items-center justify-content-between">
                <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                    {{ __('Invoice Confirmation') }}
                </h2>
                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb mb-0">
                        <li class="breadcrumb-item"><a href="{{ route('cart.index') }}" class="text-decoration-none">Cart</a></li>
                        <li class="breadcrumb-item"><a href="{{ route('checkout.index') }}" class="text-decoration-none">Checkout</a></li>
                        <li class="breadcrumb-item active" aria-current="page">Confirmation</li>
                    </ol>
                </nav>
            </div>
        </div>
    </x-slot>

    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-xl-10">
                <!-- Welcome/Status Header -->
                <div class="text-center mb-5">
                    <div class="mb-3">
                        <span class="badge bg-primary-subtle text-primary px-3 py-2 rounded-pill text-uppercase tracking-wider fw-bold">Step 2 of 2: Final Review</span>
                    </div>
                    <h1 class="display-5 fw-bold font-ubuntu mb-3">Review & Complete Order</h1>
                    <p class="lead text-muted mx-auto" style="max-width: 600px;">
                        Please review your order details below. By completing this step, a Quickbooks Invoice will be generated and sent to your email.
                    </p>
                </div>

                <div class="row g-4">
                    <!-- Left Column: Details -->
                    <div class="col-lg-7">
                        <!-- Addresses Grid -->
                        <div class="row g-4 mb-4">
                            <div class="col-md-6">
                                <div class="card h-100 border-0 shadow-sm rounded-4">
                                    <div class="card-body p-4">
                                        <div class="d-flex align-items-center mb-3">
                                            <div class="bg-primary-subtle text-primary p-2 rounded-3 me-3">
                                                <i class="bi bi-person-badge fs-5"></i>
                                            </div>
                                            <h5 class="fw-bold mb-0 font-ubuntu">Bill To</h5>
                                        </div>
                                        <div class="text-secondary">
                                            <p class="fw-bold mb-1 text-dark">{{ $business->business_name }}</p>
                                            <p class="mb-1">{{ $business->contact_name }}</p>
                                            <p class="mb-0 small"><i class="bi bi-envelope me-2"></i>{{ $business->email }}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card h-100 border-0 shadow-sm rounded-4">
                                    <div class="card-body p-4">
                                        <div class="d-flex align-items-center mb-3">
                                            <div class="bg-success-subtle text-success p-2 rounded-3 me-3">
                                                <i class="bi bi-truck fs-5"></i>
                                            </div>
                                            <h5 class="fw-bold mb-0 font-ubuntu">Shipping To</h5>
                                        </div>
                                        <div class="text-secondary small">
                                            @if($order->shippingAddress)
                                                <p class="mb-1 fw-bold text-dark">{{ $order->shippingAddress->name }}</p>
                                                <p class="mb-1">{{ $order->shippingAddress->address1 }}</p>
                                                @if($order->shippingAddress->address2)<p class="mb-1">{{ $order->shippingAddress->address2 }}</p>@endif
                                                <p class="mb-0">{{ $order->shippingAddress->city }}, {{ $order->shippingAddress->state }} {{ $order->shippingAddress->zip }}</p>
                                            @else
                                                <p class="text-muted italic">No shipping address set.</p>
                                            @endif
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Order Items Card -->
                        <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-4">
                            <div class="card-header bg-white py-3 border-bottom-0 px-4">
                                <div class="d-flex justify-content-between align-items-center">
                                    <h5 class="fw-bold mb-0 font-ubuntu">Itemized Summary</h5>
                                    <span class="badge bg-light text-dark">{{ $order->dtfImages->count() }} Items</span>
                                </div>
                            </div>
                            <div class="card-body p-0">
                                <div class="table-responsive">
                                    <table class="table align-middle mb-0">
                                        <thead class="bg-light">
                                            <tr>
                                                <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">Product</th>
                                                <th class="py-3 text-uppercase small fw-bold text-muted text-center">Qty</th>
                                                <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Price</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            @foreach($order->dtfImages as $item)
                                                <tr>
                                                    <td class="ps-4 py-3">
                                                        <div class="d-flex align-items-center">
                                                            @if($item->image)
                                                                <img src="{{ $item->image }}" class="rounded shadow-sm me-3" style="width: 45px; height: 45px; object-fit: contain; background: #f8f9fa;">
                                                            @endif
                                                            <div>
                                                                <div class="fw-bold text-dark mb-0">
                                                                    {{ $item->image_name }}
                                                                    @if($item->item_type === 'gang_sheet')
                                                                        <span class="badge bg-dark-subtle text-dark border ms-1">Gang Sheet</span>
                                                                    @endif
                                                                </div>
                                                                <div class="text-muted smaller">
                                                                    @if($item->item_type === 'gang_sheet')
                                                                        {{ strtoupper(data_get($item->item_meta, 'size_key', $item->width . 'x' . $item->height)) }}
                                                                    @else
                                                                        {{ $item->width }}" x {{ $item->height }}"
                                                                    @endif
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td class="text-center fw-semibold text-dark">{{ $item->quantity }}</td>
                                                    <td class="text-end pe-4 fw-bold text-dark">${{ number_format($item->get_price() * $item->quantity, 2) }}</td>
                                                </tr>
                                            @endforeach
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Right Column: Totals & Action -->
                    <div class="col-lg-5">
                        <div class="sticky-top" style="top: 100px; z-index: 10;">
                            <!-- Payment Terms Card -->
                            <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-4">
                                <div class="card-header bg-info text-white py-3 border-bottom-0 px-4">
                                    <div class="d-flex align-items-center">
                                        <i class="bi bi-shield-check fs-4 me-2"></i>
                                        <h5 class="fw-bold mb-0 font-ubuntu">Payment Terms</h5>
                                    </div>
                                </div>
                                <div class="card-body p-4">
                                    <div class="p-3 bg-info-subtle rounded-3 border border-info-subtle mb-4">
                                        <div class="d-flex">
                                            <i class="bi bi-info-circle-fill text-info fs-4 me-3"></i>
                                            <div class="small">
                                                <p class="mb-0 fw-bold text-info-emphasis">Quickbooks Invoice</p>
                                                <p class="mb-0 text-secondary">You will be invoiced via email and payment is due within 10 days.</p>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="mb-4">
                                        <h6 class="fw-bold text-dark mb-3">Agreement Details:</h6>
                                        <ul class="list-unstyled mb-0">
                                            <li class="d-flex mb-2 small">
                                                <i class="bi bi-check2-circle text-success me-2 fs-5"></i>
                                                <span>I agree to pay the invoice sent via QuickBooks Online.</span>
                                            </li>
                                            <li class="d-flex mb-2 small">
                                                <i class="bi bi-check2-circle text-success me-2 fs-5"></i>
                                                <span>I understand the net terms are <strong>10 days</strong> from issuance.</span>
                                            </li>
                                            <li class="d-flex small text-danger">
                                                <i class="bi bi-exclamation-circle me-2 fs-5"></i>
                                                <span>Late payments may affect future credit terms.</span>
                                            </li>
                                        </ul>
                                    </div>

                                    <div class="bg-light p-4 rounded-4 mb-4">
                                        <div class="d-flex justify-content-between mb-2">
                                            <span class="text-muted small">Items Subtotal</span>
                                            <span class="fw-bold text-dark">${{ number_format($order->price, 2) }}</span>
                                        </div>
                                        <div class="d-flex justify-content-between mb-2">
                                            <span class="text-muted small">Shipping & Handling</span>
                                            <span class="fw-bold text-dark">${{ number_format($order->shipping_cost, 2) }}</span>
                                        </div>
                                        <div class="d-flex justify-content-between mb-3 pb-3 border-bottom">
                                            <span class="text-muted small">Estimated Tax</span>
                                            <span class="fw-bold text-dark">$0.00</span>
                                        </div>
                                        <div class="d-flex justify-content-between align-items-center">
                                            <span class="fw-bold text-dark h5 mb-0 font-ubuntu">Order Total</span>
                                            <span class="fw-bold text-primary h4 mb-0 font-ubuntu">${{ number_format($order->total_price, 2) }}</span>
                                        </div>
                                    </div>

                                    <form action="{{ route('checkout.invoice.complete', $order->id) }}" method="POST" id="completeOrderForm">
                                        @csrf
                                        <div class="d-grid">
                                            <button type="button" id="showConfirmModal" class="btn btn-success btn-lg fw-bold py-3 shadow-sm text-uppercase tracking-wider rounded-3">
                                                Complete My Order <i class="bi bi-arrow-right-short ms-1"></i>
                                            </button>
                                        </div>
                                        <div class="text-center mt-3">
                                            <a href="{{ route('checkout.index') }}" class="text-muted small text-decoration-none hover-text-primary">
                                                <i class="bi bi-arrow-left me-1"></i> Back to Payment Options
                                            </a>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Confirmation Modal -->
    <div class="modal fade" id="confirmOrderModal" tabindex="-1" aria-labelledby="confirmOrderModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow-lg rounded-4">
                <div class="modal-header border-0 pt-4 px-4 pb-0">
                    <h5 class="modal-title fw-bold font-ubuntu" id="confirmOrderModalLabel">Confirm Your Order</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body p-4">
                    <div class="d-flex align-items-center mb-3">
                        <div class="bg-success-subtle text-success p-3 rounded-circle me-3">
                            <i class="bi bi-check2-square fs-3"></i>
                        </div>
                        <p class="mb-0 text-dark fw-medium">
                            Are you ready to finalize your order?
                        </p>
                    </div>
                    <p class="text-secondary small mb-0">
                        By confirming, you agree to the payment terms and a QuickBooks Invoice will be issued for <strong>${{ number_format($order->total_price, 2) }}</strong>.
                    </p>
                </div>
                <div class="modal-footer border-0 pb-4 px-4 pt-0">
                    <button type="button" class="btn btn-light fw-bold px-4 rounded-3" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" id="confirmSubmit" class="btn btn-success fw-bold px-4 rounded-3 shadow-sm">
                        Yes, Complete Order
                    </button>
                </div>
            </div>
        </div>
    </div>

    @push('scripts')
    <script>
        $(document).ready(function() {
            const $form = $('#completeOrderForm');
            const $modal = new bootstrap.Modal(document.getElementById('confirmOrderModal'));
            const $showBtn = $('#showConfirmModal');
            const $confirmBtn = $('#confirmSubmit');

            $showBtn.on('click', function() {
                $modal.show();
            });

            $confirmBtn.on('click', function() {
                // Disable buttons and show loading state
                $confirmBtn.prop('disabled', true);
                $confirmBtn.html('<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Processing...');

                $showBtn.prop('disabled', true);
                $showBtn.html('<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Processing Order...');

                // Submit the form
                $form.submit();
            });
        });
    </script>
    @endpush
</x-app-layout>
