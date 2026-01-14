<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Orders for') }} {{ $business->business_name }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Action Buttons -->
            <div class="text-end mb-4">
                @if (!$business->open_order())
                <a href="{{ route('orders.new') }}" class="btn btn-primary btn-lg">
                    <i class="bi bi-plus-circle"></i> Start New Order
                </a>
                @else
                <a href="{{ route('orders.show', $business->open_order()->id) }}" class="btn btn-primary btn-lg">
                    <i class="bi bi-plus-circle"></i> Add to Order
                </a>
                @endif
            </div>

            <!-- Orders Table -->
            @if ($orders->count() > 0)
            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="bg-light">
                            <tr>
                                <th>Action</th>
                                <th class="text-center">Order Date</th>
                                <th class="text-center">Status</th>
                                <th class="text-center">Images</th>
                                <th class="text-center">Total Images</th>
                                <th class="text-center">Shipped</th>
                                <th class="text-end">Total Price</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach ($orders as $order)
                            <tr>
                                <td>
                                    <a href="{{ route('orders.show', $order->id) }}" class="btn btn-sm btn-success">
                                        <i class="bi bi-eye"></i> View
                                    </a>
                                </td>
                                <td class="text-center">
                                    {{ $order->order_date ? $order->order_date->format('m-d-Y') : 'N/A' }}
                                </td>
                                <td class="text-center">
                                    <span class="badge" style="background:{{ $order->orderStatus->color ?? '#6c757d' }}">
                                        {{ ucfirst($order->orderStatus->name ?? 'Unknown') }}
                                    </span>
                                </td>
                                <td class="text-center">{{ $order->get_image_count() }}</td>
                                <td class="text-center">{{ $order->get_total_image_count() }}</td>
                                <td class="text-center">
                                    @if ($order->shippingMethod && $order->status != 1)
                                        <span class="text-muted small">{{ $order->shippingMethod->shipping_method }}</span>
                                    @endif
                                </td>
                                <td class="text-end fw-bold">
                                    ${{ number_format($order->total_price + $order->sales_tax + $order->shipping_cost, 2) }}
                                </td>
                            </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
            @else
            <!-- No Orders Message -->
            <div class="text-center py-5">
                <i class="bi bi-info-circle fs-1 text-muted mb-3 d-block"></i>
                <p class="text-muted">No orders found for your business. Start by creating a new order.</p>
            </div>
            @endif
        </div>
    </div>
</x-app-layout>
