<x-app-layout>
    <x-slot name="header">
        <div class="d-flex justify-content-between align-items-center">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                {{ __('Stripe Payouts (Deposits)') }}
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
                    <li class="breadcrumb-item active">Payouts</li>
                </ol>
            </nav>

            <!-- Payouts Table -->
            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table align-middle mb-0">
                            <thead class="bg-light">
                                <tr>
                                    <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">Arrival Date</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Payout ID</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Status</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Amount</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($payouts as $payout)
                                    @php
                                        $isFuture = in_array($payout->status, ['pending', 'in_transit']) || $payout->arrival_date->isFuture();
                                    @endphp
                                    <tr class="hover-bg-light transition {{ $isFuture ? 'bg-light-info' : '' }}">
                                        <td class="ps-4 py-3 fw-bold">
                                            {{ $payout->arrival_date->format('M d, Y') }}
                                            @if($isFuture)
                                                <span class="ms-2 badge bg-info text-dark small text-uppercase" style="font-size: 0.65rem;">Estimated</span>
                                            @endif
                                        </td>
                                        <td class="py-3 small text-muted font-monospace">
                                            {{ $payout->stripe_payout_id }}
                                        </td>
                                        <td class="py-3">
                                            @php
                                                $statusBadge = match($payout->status) {
                                                    'paid' => 'bg-success',
                                                    'pending' => 'bg-warning text-dark',
                                                    'in_transit' => 'bg-info text-dark',
                                                    'failed' => 'bg-danger',
                                                    default => 'bg-secondary',
                                                };
                                            @endphp
                                            <span class="badge rounded-pill {{ $statusBadge }} text-uppercase">
                                                {{ str_replace('_', ' ', $payout->status) }}
                                            </span>
                                        </td>
                                        <td class="py-3 fw-bold text-dark">
                                            ${{ number_format($payout->amount, 2) }}
                                        </td>
                                        <td class="py-3 text-end pe-4">
                                            <a href="{{ route('admin.payments.stripe.payouts.show', $payout->id) }}" class="btn btn-sm btn-outline-primary fw-bold px-3">
                                                <i class="bi bi-eye me-1"></i> View Details
                                            </a>
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="5" class="text-center py-5">
                                            <div class="text-muted mb-2"><i class="bi bi-bank fs-1"></i></div>
                                            <p class="text-muted mb-0">No payouts found. Click sync to fetch from Stripe.</p>
                                        </td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
                @if($payouts->hasPages())
                    <div class="card-footer bg-white border-top-0 py-3 px-4">
                        {{ $payouts->links() }}
                    </div>
                @endif
            </div>
        </div>
    </div>

    <style>
        .hover-bg-light:hover { background-color: rgba(0,0,0,.02); }
        .transition { transition: all 0.2s ease-in-out; }
        .bg-light-info { background-color: rgba(13, 202, 240, 0.05); }
    </style>
</x-app-layout>
