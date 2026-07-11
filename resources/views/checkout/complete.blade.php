<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Order Complete') }}
        </h2>
    </x-slot>

    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-8 text-center">
                <div class="mb-4">
                    <i class="bi bi-check-circle-fill text-success" style="font-size: 5rem;"></i>
                </div>
                <h1 class="display-4 fw-bold mb-3">Thank You!</h1>
                <p class="lead text-muted mb-5">Your order <strong>#{{ $order->id }}</strong> has been placed successfully and is now being processed.</p>

                @if($order->paymentMethod && $order->paymentMethod->payment_controller === 'invoice')
                    @include('checkout.partials.invoice_info')
                @endif

                <div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-5 text-start">
                    <div class="card-header bg-dark text-white py-3">
                        <h5 class="mb-0">Order Details</h5>
                    </div>
                    <div class="card-body p-4">
                        <div class="row g-4">
                            <div class="col-sm-6">
                                <h6 class="text-muted text-uppercase small fw-bold mb-2">Order Date</h6>
                                <p class="fw-bold mb-0">{{ $order->order_date ? $order->order_date->format('M j, Y') : ($order->created_at ? $order->created_at->format('M j, Y') : 'N/A') }}</p>
                            </div>
                            <div class="col-sm-6">
                                <h6 class="text-muted text-uppercase small fw-bold mb-2">Total Amount</h6>
                                <p class="fw-bold mb-0 text-primary fs-5">${{ number_format($order->total_price, 2) }}</p>
                            </div>
                            <div class="col-sm-6">
                                <h6 class="text-muted text-uppercase small fw-bold mb-2">Shipping To</h6>
                                <p class="small mb-0">
                                    {{ $order->shippingAddress->name ?? 'N/A' }}<br>
                                    {{ $order->shippingAddress->address1 ?? ($order->shippingAddress->address ?? 'N/A') }}<br>
                                    @if($order->shippingAddress && $order->shippingAddress->address2) {{ $order->shippingAddress->address2 }}<br> @endif
                                    @if($order->shippingAddress)
                                        {{ $order->shippingAddress->city }}, {{ $order->shippingAddress->state }} {{ $order->shippingAddress->zip }}
                                    @endif
                                </p>
                            </div>
                            <div class="col-sm-6">
                                <h6 class="text-muted text-uppercase small fw-bold mb-2">Status</h6>
                                <span class="badge bg-success-subtle text-success border border-success-subtle px-3 py-2 text-uppercase">
                                    {{ $order->orderStatus->name ?? 'Paid' }}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="d-flex flex-column flex-sm-row justify-content-center gap-3">
                    <a href="{{ route('account') }}" class="btn btn-outline-dark btn-lg px-5 fw-bold rounded-3">
                        View My Orders
                    </a>
                    <a href="{{ route('home') }}" class="btn btn-primary btn-lg px-5 fw-bold rounded-3 shadow-sm">
                        Back to Home
                    </a>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
