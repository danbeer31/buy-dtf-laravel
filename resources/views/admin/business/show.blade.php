<x-app-layout>
    <x-slot name="header">
        <div class="d-flex align-items-center justify-content-between">
            <h2 class="fw-bold fs-4 text-dark mb-0">
                {{ __('Business Details') }}
            </h2>
            <a href="{{ route('admin.businesses.index') }}" class="btn btn-outline-secondary btn-sm fw-bold">
                &larr; Back to List
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            @if(session('success'))
                <div class="alert alert-success alert-dismissible fade show border-0 shadow-sm rounded-4 mb-4" role="alert">
                    {{ session('success') }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            @endif

            @if(session('error'))
                <div class="alert alert-danger alert-dismissible fade show border-0 shadow-sm rounded-4 mb-4" role="alert">
                    {{ session('error') }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            @endif

            <div class="row g-4">
                <!-- Main Info -->
                <div class="col-lg-8">
                    <div class="card shadow-sm border-0 rounded-4 mb-4">
                        <div class="card-header bg-white border-bottom-0 pt-4 px-4">
                            <h5 class="fw-bold mb-0">General Information</h5>
                        </div>
                        <div class="card-body p-4">
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block">Business Name</label>
                                    <p class="fs-5 fw-bold">{{ $business->business_name }}</p>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block">Contact Name</label>
                                    <p class="fs-5">{{ $business->contact_name }}</p>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block">Email Address</label>
                                    <p><a href="mailto:{{ $business->email }}" class="text-decoration-none">{{ $business->email }}</a></p>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block">Phone Number</label>
                                    <p><a href="tel:{{ $business->phone }}" class="text-decoration-none">{{ $business->phone }}</a></p>
                                </div>
                                <div class="col-12">
                                    <label class="small text-uppercase text-muted fw-bold d-block">Address</label>
                                    <p class="mb-0">
                                        {{ $business->address }}@if($business->address2), {{ $business->address2 }}@endif<br>
                                        {{ $business->city }}, {{ $business->state }} {{ $business->zip }}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Orders Table (Placeholder) -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                        <div class="card-header bg-white border-bottom-0 pt-4 px-4">
                            <h5 class="fw-bold mb-0">Recent Orders</h5>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table align-middle mb-0">
                                    <thead class="bg-light">
                                        <tr>
                                            <th class="ps-4 py-3 text-uppercase small fw-bold">Order ID</th>
                                            <th class="py-3 text-uppercase small fw-bold">Date</th>
                                            <th class="py-3 text-uppercase small fw-bold">Status</th>
                                            <th class="py-3 text-uppercase small fw-bold text-end pe-4">Total</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        @forelse($orders as $order)
                                            <tr>
                                                <td class="ps-4 py-3 fw-bold">#{{ $order->id }}</td>
                                                <td class="py-3">{{ $order->order_date ? $order->order_date->format('M d, Y') : ($order->created_at ? $order->created_at->format('M d, Y') : 'N/A') }}</td>
                                                <td class="py-3">
                                                    <span class="badge border text-uppercase px-2 py-1" style="background-color: {{ $order->orderStatus->color ?? '#6c757d' }}22; color: {{ $order->orderStatus->color ?? '#6c757d' }}; border-color: {{ $order->orderStatus->color ?? '#6c757d' }}44;">
                                                        {{ $order->orderStatus->name ?? 'Unknown' }}
                                                    </span>
                                                </td>
                                                <td class="py-3 text-end pe-4 fw-bold">
                                                    ${{ number_format($order->total_price, 2) }}
                                                </td>
                                            </tr>
                                        @empty
                                            <tr>
                                                <td colspan="4" class="text-center py-5 text-muted small">
                                                    No orders found for this business.
                                                </td>
                                            </tr>
                                        @endforelse
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Sidebar Actions -->
                <div class="col-lg-4">
                    <div class="card shadow-sm border-0 rounded-4 mb-4">
                        <div class="card-body p-4 text-center">
                            @php
                                $badgeClass = match($business->status) {
                                    'confirmed' => 'bg-success text-white',
                                    'unconfirmed' => 'bg-warning text-dark',
                                    'closed' => 'bg-secondary text-white',
                                    'cancelled' => 'bg-danger text-white',
                                    default => 'bg-light text-dark'
                                };
                            @endphp
                            <div class="display-6 mb-2">
                                <span class="badge {{ $badgeClass }} rounded-pill px-4 fs-6 text-uppercase tracking-wider">
                                    {{ $business->status }}
                                </span>
                            </div>
                            <p class="text-muted small">Registered on {{ $business->created_at ? $business->created_at->format('M d, Y') : 'Unknown' }}</p>

                            <hr class="my-4">

                            <div class="d-grid gap-2">
                                <button type="button" class="btn btn-warning fw-bold text-uppercase py-2 shadow-sm" data-bs-toggle="modal" data-bs-target="#updateRateModal">
                                    Update Rate
                                </button>
                                <form action="{{ route('admin.businesses.toggle-tax-exempt', $business) }}" method="POST">
                                    @csrf
                                    @method('PATCH')
                                    <button type="submit" class="btn btn-outline-primary fw-bold text-uppercase py-2 shadow-sm w-100">
                                        {{ $business->tax_exempt ? 'Remove Tax Exempt' : 'Set Tax Exempt' }}
                                    </button>
                                </form>
                                <form action="{{ route('admin.businesses.impersonate', $business) }}" method="POST">
                                    @csrf
                                    <button type="submit" class="btn btn-outline-info fw-bold text-uppercase py-2 shadow-sm w-100">
                                        Login as Customer
                                    </button>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Additional Details -->
                    <div class="card shadow-sm border-0 rounded-4 mb-4">
                        <div class="card-body p-4">
                            <h6 class="fw-bold text-uppercase small mb-3">System Information</h6>
                            <ul class="list-unstyled mb-0 small">
                                <li class="d-flex justify-content-between mb-2">
                                    <span class="text-muted">Business ID:</span>
                                    <span class="fw-bold">#{{ $business->id }}</span>
                                </li>
                                <li class="d-flex justify-content-between mb-2">
                                    <span class="text-muted">Linked User:</span>
                                    <span class="fw-bold">{{ $business->user->name ?? 'None' }}</span>
                                </li>
                                <li class="d-flex justify-content-between mb-2">
                                    <span class="text-muted">Current Rate:</span>
                                    <span class="fw-bold text-primary">${{ number_format($business->settings->rate ?? 0.03, 3) }} / sq in</span>
                                </li>
                                <li class="d-flex justify-content-between mb-2">
                                    <span class="text-muted">Tax Exempt:</span>
                                    <span class="fw-bold {{ $business->tax_exempt ? 'text-success' : 'text-danger' }}">
                                        {{ $business->tax_exempt ? 'YES' : 'NO' }}
                                    </span>
                                </li>
                                <li class="d-flex justify-content-between mb-2">
                                    <span class="text-muted">Tax Number:</span>
                                    <span class="fw-bold">{{ $business->tax_number ?? 'N/A' }}</span>
                                </li>
                                <li class="d-flex justify-content-between">
                                    <span class="text-muted">QBO ID:</span>
                                    <span class="fw-bold">{{ $business->qbo_customer_id ?? 'Not synced' }}</span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Update Rate Modal -->
    <div class="modal fade" id="updateRateModal" tabindex="-1" aria-labelledby="updateRateModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow rounded-4">
                <form action="{{ route('admin.businesses.update-rate', $business) }}" method="POST">
                    @csrf
                    @method('PATCH')
                    <div class="modal-header border-bottom-0 pt-4 px-4">
                        <h5 class="modal-title fw-bold" id="updateRateModalLabel">Update Business Rate</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body p-4">
                        <div class="mb-3">
                            <label for="rate" class="form-label small fw-bold text-uppercase">New Rate ($ per sq inch)</label>
                            <div class="input-group">
                                <span class="input-group-text bg-light">$</span>
                                <input type="number" step="0.001" min="0" name="rate" id="rate" class="form-control" value="{{ $business->settings->rate ?? 0.03 }}" required>
                            </div>
                            <div class="form-text small">Default rate is typically 0.030.</div>
                        </div>
                    </div>
                    <div class="modal-footer border-top-0 pb-4 px-4">
                        <button type="button" class="btn btn-light fw-bold" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-warning fw-bold">Update Rate</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</x-app-layout>
