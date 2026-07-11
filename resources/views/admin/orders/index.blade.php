<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
            {{ __('Manage Orders') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Search and Filter Card -->
            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <form method="GET" action="{{ route('admin.orders.index') }}" class="row g-3 align-items-end">
                        <div class="col-md-4">
                            <label for="search" class="form-label small fw-bold text-uppercase text-muted">Search Orders</label>
                            <div class="input-group">
                                <span class="input-group-text bg-light border-end-0"><i class="bi bi-search"></i></span>
                                <input type="text" name="search" id="search" class="form-control border-start-0 bg-light" placeholder="Business name, contact, email or ID" value="{{ request('search') }}">
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label for="filter_status" class="form-label small fw-bold text-uppercase text-muted">Filter by Status</label>
                            <select name="filter_status" id="filter_status" class="form-select bg-light" onchange="this.form.submit()">
                                <option value="">All Statuses</option>
                                @foreach($orderStatuses as $status)
                                    <option value="{{ $status->id }}" {{ request('filter_status') == $status->id ? 'selected' : '' }}>
                                        {{ $status->name }}
                                    </option>
                                @endforeach
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label for="filter_paid" class="form-label small fw-bold text-uppercase text-muted">Payment</label>
                            <select name="filter_paid" id="filter_paid" class="form-select bg-light" onchange="this.form.submit()">
                                <option value="">All</option>
                                <option value="paid" {{ request('filter_paid') === 'paid' ? 'selected' : '' }}>Paid</option>
                                <option value="unpaid" {{ request('filter_paid') === 'unpaid' ? 'selected' : '' }}>Unpaid</option>
                            </select>
                        </div>
                        <div class="col-md-2">
                            <button type="submit" class="btn btn-primary w-100 fw-bold text-uppercase py-2 shadow-sm">
                                <i class="bi bi-funnel me-1"></i> Filter
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Orders Table Card -->
            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table align-middle mb-0">
                            <thead class="bg-light">
                                <tr>
                                    <th class="ps-4 py-3 text-uppercase small fw-bold text-muted" style="width: 80px;">ID</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Business</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Contact</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Order Date</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Status</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Shipping</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Payment</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">QBO</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Total</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($orders as $order)
                                    @php
                                        $businessQboMap = $qboInvoicesMapByBusiness[$order->business_id] ?? [];
                                        $qboInvoice = isset($businessQboMap[$order->qbo_invoice_id])
                                            ? $businessQboMap[$order->qbo_invoice_id]
                                            : (
                                                $order->qbo_invoice_number && isset($businessQboMap['doc_' . $order->qbo_invoice_number])
                                                    ? $businessQboMap['doc_' . $order->qbo_invoice_number]
                                                    : null
                                            );
                                        $qboPaid = $qboInvoice ? ((float)($qboInvoice['Balance'] ?? 0) <= 0) : null;
                                        $isPaid = $qboPaid ?? $order->isPaid();
                                    @endphp
                                    <tr class="hover-bg-light transition">
                                        <td class="ps-4 py-3 fw-bold">#{{ $order->id }}</td>
                                        <td class="py-3">
                                            <a href="{{ route('admin.businesses.show', $order->business_id) }}" class="text-decoration-none fw-semibold text-primary">
                                                {{ $order->business->business_name }}
                                            </a>
                                        </td>
                                        <td class="py-3 text-secondary">{{ $order->business->contact_name }}</td>
                                        <td class="py-3 text-secondary">
                                            {{ $order->order_date ? $order->order_date->format('m-d-Y') : 'N/A' }}
                                        </td>
                                        <td class="py-3">
                                            <span class="badge border text-uppercase px-2 py-1" style="background-color: {{ $order->orderStatus->color ?? '#6c757d' }}22; color: {{ $order->orderStatus->color ?? '#6c757d' }}; border-color: {{ $order->orderStatus->color ?? '#6c757d' }}44;">
                                                {{ $order->orderStatus->name ?? 'Unknown' }}
                                            </span>
                                        </td>
                                        <td class="py-3">
                                            <div class="small">
                                                <div class="fw-bold text-truncate" style="max-width: 120px;" title="{{ $order->shipping_method ?? ($order->shippo_service_name ?? ($order->shippingMethod->method_name ?? 'Standard')) }}">
                                                    {{ $order->shipping_method ?? ($order->shippo_service_name ?? ($order->shippingMethod->method_name ?? 'Standard')) }}
                                                </div>
                                                @if($order->tracking_number)
                                                    <div class="text-muted"><i class="bi bi-truck me-1"></i>Shipped</div>
                                                @else
                                                    @php
                                                        $shippingMethodName = $order->shipping_method ?? ($order->shippo_service_name ?? ($order->shippingMethod->method_name ?? 'Standard'));
                                                    @endphp
                                                    @if(strtolower($shippingMethodName) !== 'standard')
                                                        <div class="text-warning"><i class="bi bi-clock me-1"></i>Pending</div>
                                                    @endif
                                                @endif
                                            </div>
                                        </td>
                                        <td class="py-3">
                                            @if($isPaid)
                                                <span class="text-success fw-bold small"><i class="bi bi-check-circle-fill me-1"></i> PAID</span>
                                            @else
                                                <span class="text-danger fw-bold small"><i class="bi bi-x-circle-fill me-1"></i> UNPAID</span>
                                            @endif
                                        </td>
                                        <td class="py-3">
                                            @if($order->qbo_invoice_id)
                                                <span class="text-success fs-5" title="QBO Invoice Created"><i class="bi bi-check-circle-fill"></i></span>
                                            @else
                                                <span class="text-muted fs-5 opacity-25"><i class="bi bi-circle"></i></span>
                                            @endif
                                        </td>
                                        <td class="py-3 fw-bold">
                                            ${{ number_format($order->total_price, 2) }}
                                        </td>
                                        <td class="py-3 text-end pe-4">
                                            <a href="{{ route('admin.orders.show', $order->id) }}" class="btn btn-sm btn-outline-primary fw-bold px-3">
                                                <i class="bi bi-eye me-1"></i> View
                                            </a>
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="10" class="text-center py-5">
                                            <div class="text-muted mb-2"><i class="bi bi-inbox fs-1"></i></div>
                                            <p class="text-muted mb-0">No orders found. Try adjusting your search or filters.</p>
                                        </td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
                @if($orders->hasPages())
                    <div class="card-footer bg-white border-top-0 py-3 px-4">
                        {{ $orders->links() }}
                    </div>
                @endif
            </div>
        </div>
    </div>

    <style>
        .hover-bg-light:hover { background-color: rgba(0,0,0,.02); }
        .transition { transition: all 0.2s ease-in-out; }
    </style>
</x-app-layout>
