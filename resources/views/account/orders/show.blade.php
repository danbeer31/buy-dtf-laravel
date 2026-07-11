<x-app-layout>
    <x-slot name="header">
        <div class="d-flex justify-content-between align-items-center">
            <h2 class="fw-bold fs-4 text-dark mb-0">Order #{{ $order->id }}</h2>
            <a href="{{ route('account') }}" class="btn btn-outline-secondary btn-sm">
                <i class="bi bi-arrow-left me-1"></i>Back to Account
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row g-4 mb-4">
                <div class="col-md-3">
                    <div class="card shadow-sm border-0 rounded-4 h-100">
                        <div class="card-body p-4">
                            <div class="small text-uppercase text-muted fw-bold mb-1">Order Date</div>
                            <div class="fw-semibold">{{ $order->order_date ? $order->order_date->format('m/d/Y') : 'N/A' }}</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card shadow-sm border-0 rounded-4 h-100">
                        <div class="card-body p-4">
                            <div class="small text-uppercase text-muted fw-bold mb-1">Status</div>
                            <span class="badge" style="background-color: {{ $order->orderStatus->color ?? '#6c757d' }};">
                                {{ ucfirst($order->orderStatus->name ?? 'Unknown') }}
                            </span>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card shadow-sm border-0 rounded-4 h-100">
                        <div class="card-body p-4">
                            <div class="small text-uppercase text-muted fw-bold mb-1">Payment</div>
                            @if($order->isPaid())
                                <span class="badge bg-success">Paid</span>
                            @elseif($order->paymentInfo && $order->paymentInfo->processor === 'QB Invoice')
                                <span class="badge bg-warning text-dark">Open Invoice</span>
                            @else
                                <span class="badge bg-secondary">Pending</span>
                            @endif
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card shadow-sm border-0 rounded-4 h-100">
                        <div class="card-body p-4">
                            <div class="small text-uppercase text-muted fw-bold mb-1">Total</div>
                            <div class="fw-bold fs-5">${{ number_format((float) $order->total_price, 2) }}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-header bg-white border-0 pt-4 px-4">
                    <h5 class="fw-bold mb-0">DTF Images Ordered</h5>
                </div>
                <div class="card-body p-0">
                    @if($order->dtfImages->count() > 0)
                        <div class="table-responsive">
                            <table class="table align-middle mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th class="ps-4">Image</th>
                                        <th>Name</th>
                                        <th class="text-center">Size</th>
                                        <th class="text-center">Qty</th>
                                        <th class="text-end pe-4">Price</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    @foreach($order->dtfImages as $img)
                                        <tr>
                                            <td class="ps-4">
                                                <img src="{{ $img->thumbnail ?: $img->image }}" alt="{{ $img->image_name ?: 'DTF Image' }}" class="rounded border" style="width: 72px; height: 72px; object-fit: contain; background: #fff;">
                                            </td>
                                            <td>
                                                <div class="fw-semibold">{{ $img->image_name ?: 'Customer Upload' }}</div>
                                                @if($img->image_notes)
                                                    <div class="small text-muted">{{ $img->image_notes }}</div>
                                                @endif
                                            </td>
                                            <td class="text-center">{{ number_format((float)$img->width, 2) }}" × {{ number_format((float)$img->height, 2) }}"</td>
                                            <td class="text-center">{{ (int)$img->quantity }}</td>
                                            <td class="text-end pe-4">${{ number_format((float)$img->get_total(), 2) }}</td>
                                        </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    @else
                        <div class="p-4 text-muted">No images were found for this order.</div>
                    @endif
                </div>
            </div>

            @if($order->status == 1)
                <div class="text-end">
                    <a href="{{ route('cart.index') }}" class="btn btn-success">
                        <i class="bi bi-cart me-1"></i>Continue Editing Order
                    </a>
                </div>
            @endif
        </div>
    </div>
</x-app-layout>
