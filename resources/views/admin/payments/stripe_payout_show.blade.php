<x-app-layout>
    <x-slot name="header">
        <div class="d-flex justify-content-between align-items-center">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                {{ __('Payout Details') }}: {{ $payout->stripe_payout_id }}
            </h2>
            <form action="{{ route('admin.payments.stripe.payouts.sync') }}" method="POST" class="stripe-sync-form">
                @csrf
                <button type="submit" class="btn btn-primary fw-bold text-uppercase shadow-sm">
                    <i class="bi bi-arrow-repeat me-1"></i> Sync All Payouts
                </button>
            </form>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <nav aria-label="breadcrumb" class="mb-4">
                <ol class="breadcrumb">
                    <li class="breadcrumb-item"><a href="{{ route('admin.payments.stripe') }}">Stripe Transactions</a></li>
                    <li class="breadcrumb-item"><a href="{{ route('admin.payments.stripe.payouts') }}">Payouts</a></li>
                    <li class="breadcrumb-item active">{{ $payout->stripe_payout_id }}</li>
                </ol>
            </nav>

            <div class="row g-4">
                <div class="col-md-4">
                    <div class="card shadow-sm border-0 rounded-4 p-3 mb-4">
                        <h5 class="fw-bold text-muted small text-uppercase mb-3">Payout Info</h5>
                        <div class="mb-2">
                            <label class="small text-muted d-block">Status</label>
                            <span class="badge {{ $payout->status === 'paid' ? 'bg-success' : 'bg-warning' }} text-uppercase">
                                {{ $payout->status }}
                            </span>
                        </div>
                        <div class="mb-2">
                            <label class="small text-muted d-block">Arrival Date</label>
                            <span class="fw-bold">{{ $payout->arrival_date->format('M d, Y') }}</span>
                        </div>
                        <div class="mb-2">
                            <label class="small text-muted d-block">Stripe ID</label>
                            <code class="small text-dark">{{ $payout->stripe_payout_id }}</code>
                        </div>
                        <div class="mb-2">
                            <label class="small text-muted d-block">QBO Deposit</label>
                            @if($payout->qbo_deposit_id)
                                <span class="badge bg-info text-uppercase">Synced (#{{ $payout->qbo_deposit_id }})</span>
                            @else
                                <span class="badge bg-secondary text-uppercase">Not Synced</span>
                            @endif
                        </div>
                    </div>

                    <div class="card shadow-sm border-0 rounded-4 p-3">
                        <h5 class="fw-bold text-muted small text-uppercase mb-3">Financial Summary</h5>
                        <div class="d-flex justify-content-between mb-2">
                            <span>Gross Amount</span>
                            <span class="fw-bold text-dark">${{ number_format($payout->amount, 2) }}</span>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <span>Total Fees</span>
                            <span class="fw-bold text-danger">-${{ number_format($payout->fee, 2) }}</span>
                        </div>
                        <hr>
                        <div class="d-flex justify-content-between">
                            <span class="fw-bold">Net Deposit</span>
                            <span class="fw-bold text-success fs-5">${{ number_format($payout->net, 2) }}</span>
                        </div>
                    </div>
                </div>

                <div class="col-md-8">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                        <div class="card-header bg-white py-3 px-4 border-bottom">
                            <h5 class="card-title mb-0 fw-bold">Payout Breakdown</h5>
                        </div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table align-middle mb-0">
                                    <thead class="bg-light">
                                        <tr>
                                            <th class="py-3 text-uppercase small fw-bold text-muted">Type</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted">Order/Ref</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted">QBO Status</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted text-end">Gross</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted text-end">Fee</th>
                                            <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Net</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        @foreach($payout->entries as $entry)
                                            <tr>
                                                <td class="ps-4 py-3">
                                                    <span class="badge bg-light text-dark border text-uppercase">{{ $entry->type }}</span>
                                                </td>
                                                <td class="py-3">
                                                    @if($entry->dtforder_id)
                                                        <a href="{{ route('admin.orders.show', $entry->dtforder_id) }}" class="fw-bold text-decoration-none">
                                                            Order #{{ $entry->dtforder_id }}
                                                        </a>
                                                        <div class="small text-muted">{{ $entry->dtfOrder->business->business_name ?? '' }}</div>
                                                    @else
                                                        <span class="small text-muted font-monospace">{{ $entry->stripe_transaction_id }}</span>
                                                    @endif
                                                </td>
                                                <td class="py-3">
                                                    @if($entry->dtfOrder && $entry->dtfOrder->paymentInfo && $entry->dtfOrder->paymentInfo->qbo_payment_id)
                                                        <span class="badge bg-success-subtle text-success border-success-subtle text-uppercase small" style="font-size: 0.7rem;">
                                                            Payment Synced
                                                        </span>
                                                    @elseif($entry->type === 'charge' || $entry->type === 'payment')
                                                        <span class="badge bg-warning-subtle text-warning border-warning-subtle text-uppercase small" style="font-size: 0.7rem;">
                                                            Pending QBO
                                                        </span>
                                                    @else
                                                        <span class="text-muted small">-</span>
                                                    @endif
                                                </td>
                                                <td class="py-3 text-end fw-semibold text-dark">
                                                    ${{ number_format($entry->gross, 2) }}
                                                </td>
                                                <td class="py-3 text-end text-danger">
                                                    -${{ number_format($entry->fee, 2) }}
                                                </td>
                                                <td class="py-3 text-end fw-bold text-dark pe-4">
                                                    ${{ number_format($entry->net, 2) }}
                                                </td>
                                            </tr>
                                        @endforeach
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
