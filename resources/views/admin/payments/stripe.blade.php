<x-app-layout>
    <x-slot name="header">
        <div class="d-flex justify-content-between align-items-center">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                {{ __('Stripe Transactions') }}
            </h2>
            <div class="d-flex gap-2">
                <form action="{{ route('admin.payments.stripe.payouts.sync') }}" method="POST" class="stripe-sync-form">
                    @csrf
                    <button type="submit" class="btn btn-primary fw-bold text-uppercase shadow-sm">
                        <i class="bi bi-arrow-repeat me-1"></i> Sync All Payouts
                    </button>
                </form>
                <a href="{{ route('admin.payments.stripe.payouts') }}" class="btn btn-outline-primary fw-bold text-uppercase shadow-sm">
                    <i class="bi bi-bank me-1"></i> Stripe Payouts (Deposits)
                </a>
                <a href="{{ route('admin.payments.stripe.sync-logs') }}" class="btn btn-outline-info fw-bold text-uppercase shadow-sm">
                    <i class="bi bi-journal-text me-1"></i> Sync Logs
                </a>
            </div>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Search Card -->
            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <form method="GET" action="{{ route('admin.payments.stripe') }}" class="row g-3 align-items-end">
                        <div class="col-md-9">
                            <label for="search" class="form-label small fw-bold text-uppercase text-muted">Search Transactions</label>
                            <div class="input-group">
                                <span class="input-group-text bg-light border-end-0"><i class="bi bi-search"></i></span>
                                <input type="text" name="search" id="search" class="form-control border-start-0 bg-light" placeholder="Transaction ID, Order ID, or Business Name" value="{{ request('search') }}">
                            </div>
                        </div>
                        <div class="col-md-3">
                            <button type="submit" class="btn btn-primary w-100 fw-bold text-uppercase py-2 shadow-sm">
                                <i class="bi bi-filter me-1"></i> Search
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Transactions Table -->
            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table align-middle mb-0">
                            <thead class="bg-light">
                                <tr>
                                    <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">Order / Invoice</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Business</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Transaction ID</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Amount</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Fee</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Net</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Date</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($payments as $payment)
                                    <tr class="hover-bg-light transition">
                                        <td class="ps-4 py-3">
                                            @if($payment->dtforder_id && $payment->dtforder_id != 0)
                                                <div class="fw-bold">
                                                    <a href="{{ route('admin.orders.show', $payment->dtforder_id) }}" class="text-decoration-none text-primary">
                                                        #{{ $payment->dtforder_id }}
                                                    </a>
                                                </div>
                                                @if($payment->dtfOrder && $payment->dtfOrder->qbo_invoice_number)
                                                    <div class="small text-muted">QB: {{ $payment->dtfOrder->qbo_invoice_number }}</div>
                                                @endif
                                            @else
                                                <span class="badge bg-info text-uppercase mb-1" style="font-size: 0.65rem;">Invoice Pymt</span>
                                                @if($payment->qbo_invoice_numbers)
                                                    <div class="small text-muted line-clamp-1" title="{{ $payment->qbo_invoice_numbers }}">QB: {{ $payment->qbo_invoice_numbers }}</div>
                                                @endif
                                            @endif
                                        </td>
                                        <td class="py-3">
                                            @if($payment->business)
                                                <a href="{{ route('admin.businesses.show', $payment->business_id) }}" class="text-decoration-none fw-semibold text-dark">
                                                    {{ $payment->business->business_name }}
                                                </a>
                                            @elseif($payment->dtfOrder && $payment->dtfOrder->business)
                                                <a href="{{ route('admin.businesses.show', $payment->dtfOrder->business_id) }}" class="text-decoration-none fw-semibold text-dark">
                                                    {{ $payment->dtfOrder->business->business_name }}
                                                </a>
                                            @elseif($payment->notes && str_contains($payment->notes, 'QBO Invoice Payment'))
                                                 <span class="small text-muted">{{ $payment->notes }}</span>
                                            @else
                                                <span class="text-muted">N/A</span>
                                            @endif
                                        </td>
                                        <td class="py-3 small text-muted font-monospace">
                                            {{ $payment->processor_confirm }}
                                        </td>
                                        <td class="py-3 fw-bold text-success">
                                            ${{ number_format($payment->amount, 2) }}
                                        </td>
                                        <td class="py-3 text-danger">
                                            @if($payment->stripe_fee)
                                                -${{ number_format($payment->stripe_fee, 2) }}
                                            @else
                                                <span class="text-muted">--</span>
                                            @endif
                                        </td>
                                        <td class="py-3 fw-bold">
                                            @if($payment->stripe_fee)
                                                ${{ number_format($payment->amount - $payment->stripe_fee, 2) }}
                                            @else
                                                ${{ number_format($payment->amount, 2) }}
                                            @endif
                                        </td>
                                        <td class="py-3 text-secondary small">
                                            {{ $payment->created_at ? $payment->created_at->format('M d, Y H:i') : 'N/A' }}
                                        </td>
                                        <td class="py-3 text-end pe-4">
                                            <a href="{{ route('admin.payments.stripe.show', $payment->id) }}" class="btn btn-sm btn-outline-primary fw-bold px-3">
                                                <i class="bi bi-eye me-1"></i> Detail
                                            </a>
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="8" class="text-center py-5">
                                            <div class="text-muted mb-2"><i class="bi bi-credit-card fs-1"></i></div>
                                            <p class="text-muted mb-0">No Stripe transactions found.</p>
                                        </td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
                @if($payments->hasPages())
                    <div class="card-footer bg-white border-top-0 py-3 px-4">
                        {{ $payments->links() }}
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
