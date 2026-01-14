<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Order Details') }} #{{ $order->id }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row g-4 mb-5">
                <div class="col-md-4">
                    <div class="card h-100 shadow-sm border-0 rounded-4">
                        <div class="card-header bg-primary text-white rounded-top-4 py-3">
                            <h5 class="mb-0">Order Summary</h5>
                        </div>
                        <div class="card-body p-4">
                            <p class="mb-2"><strong>Order ID:</strong> {{ $order->id }}</p>
                            <p class="mb-2"><strong>Order Date:</strong> {{ $order->order_date ? $order->order_date->format('F d, Y') : 'N/A' }}</p>
                            <p class="mb-2"><strong>Order Total:</strong> ${{ number_format($order->get_total(), 2) }}</p>
                            <p class="mb-0">
                                <strong>Status:</strong>
                                <span class="badge" style="background:{{ $order->orderStatus->color ?? '#6c757d' }}">
                                    {{ ucfirst($order->orderStatus->name ?? 'Unknown') }}
                                </span>
                            </p>
                        </div>
                    </div>
                </div>

                @if ($order->paymentMethod)
                <div class="col-md-4">
                    <div class="card h-100 shadow-sm border-0 rounded-4">
                        <div class="card-header bg-success text-white rounded-top-4 py-3">
                            <h5 class="mb-0">Payment Details</h5>
                        </div>
                        <div class="card-body p-4">
                            <p class="mb-0"><strong>Method:</strong> {{ $order->paymentMethod->payment_method }}</p>
                        </div>
                    </div>
                </div>
                @endif

                @if ($order->shippingMethod)
                <div class="col-md-4">
                    <div class="card h-100 shadow-sm border-0 rounded-4">
                        <div class="card-header bg-info text-white rounded-top-4 py-3">
                            <h5 class="mb-0">Shipping Details</h5>
                        </div>
                        <div class="card-body p-4">
                            <p class="mb-0"><strong>Method:</strong> {{ $order->shippingMethod->shipping_method }}</p>
                            <p class="mb-0"><strong>Cost:</strong> ${{ number_format($order->shipping_cost, 2) }}</p>
                        </div>
                    </div>
                </div>
                @endif
            </div>

            <h2 class="fw-bold mb-4">Images in This Order</h2>
            @if ($order->dtfImages->count() > 0)
            <div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4">
                @foreach ($order->dtfImages as $image)
                <div class="col">
                    <div class="card h-100 shadow-sm border-0 rounded-4 overflow-hidden">
                        <div class="card-header bg-light py-3 d-flex justify-content-between align-items-center">
                            <h6 class="mb-0 text-truncate" title="{{ $image->image_name ?? 'Image ID: '.$image->id }}">
                                {{ $image->image_name ?? 'Image ID: '.$image->id }}
                            </h6>
                            @if ($order->status == 1)
                            <button type="button" class="btn-close small" aria-label="Close"></button>
                            @endif
                        </div>
                        <div class="card-body p-4">
                            <div class="checkerboard mx-auto d-flex align-items-center justify-content-center border rounded-3 mb-3" style="background-image: linear-gradient(45deg, #f0f0f0 25%, transparent 25%), linear-gradient(-45deg, #f0f0f0 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #f0f0f0 75%), linear-gradient(-45deg, transparent 75%, #f0f0f0 75%); background-size: 20px 20px; background-position: 0 0, 0 10px, 10px -10px, -10px 0px; min-height: 200px;">
                                <img src="{{ $image->image }}" alt="Preview" class="img-fluid" style="max-height: 200px;">
                            </div>
                            <div class="row g-2 text-center small">
                                <div class="col-4 border-end"><strong>Qty</strong><br>{{ $image->quantity }}</div>
                                <div class="col-4 border-end"><strong>Width</strong><br>{{ $image->width }}"</div>
                                <div class="col-4"><strong>Height</strong><br>{{ $image->height }}"</div>
                                <div class="col-6 border-top pt-2"><strong>Price</strong><br>${{ number_format($image->price, 2) }}</div>
                                <div class="col-6 border-top pt-2"><strong>Total</strong><br>${{ number_format($image->get_total(), 2) }}</div>
                            </div>
                            @if ($image->image_notes)
                            <div class="mt-3">
                                <strong class="small text-muted">Notes:</strong>
                                <div class="p-2 bg-light rounded small mt-1" style="min-height: 40px;">{{ $image->image_notes }}</div>
                            </div>
                            @endif
                        </div>
                        <div class="card-footer bg-white py-3 d-flex justify-content-between align-items-center">
                            <small class="text-muted">{{ $image->created_at ? $image->created_at->format('m-d-Y') : '' }}</small>
                            <div class="btn-group btn-group-sm">
                                @if ($order->status == 1)
                                <button class="btn btn-outline-primary">Edit</button>
                                <button class="btn btn-outline-danger"><i class="bi bi-trash"></i></button>
                                @endif
                            </div>
                        </div>
                    </div>
                </div>
                @endforeach
            </div>
            @else
            <div class="text-center py-5">
                <i class="bi bi-images fs-1 text-muted mb-3 d-block"></i>
                <p class="text-muted">No images have been added to this order.</p>
            </div>
            @endif

            <!-- Action Buttons -->
            <div class="text-end mt-5">
                @if ($order->status == 1)
                <a href="#" class="btn btn-primary btn-lg px-4">
                    <i class="bi bi-upload"></i> Upload Image
                </a>
                <a href="{{ route('orders.place', $order->id) }}" class="btn btn-success btn-lg px-4">
                    <i class="bi bi-cart-check"></i> Place Order
                </a>
                @endif
                <a href="{{ route('orders.index') }}" class="btn btn-outline-secondary btn-lg px-4">
                    <i class="bi bi-arrow-left-circle"></i> Back to Orders
                </a>
            </div>
        </div>
    </div>
</x-app-layout>
