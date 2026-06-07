<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">Reconciliation Detail #{{ $check->id }}</h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="d-flex justify-content-end mb-3">
                <a href="{{ route('admin.payments.reconciliation.index') }}" class="btn btn-outline-secondary">Back to List</a>
            </div>

            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <div class="row g-4">
                        <div class="col-md-4">
                            <div class="text-muted small text-uppercase">Business</div>
                            <div class="fw-semibold">
                                @if($check->business)
                                    {{ $check->business->business_name ?: 'Business #' . $check->business->id }}
                                @else
                                    Global
                                @endif
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="text-muted small text-uppercase">As Of</div>
                            <div class="fw-semibold">{{ $check->as_of_date ? $check->as_of_date->format('m/d/Y') : 'Current' }}</div>
                        </div>
                        <div class="col-md-4">
                            <div class="text-muted small text-uppercase">Status</div>
                            <div>
                                @if($check->status === 'balanced')
                                    <span class="badge bg-success">Balanced</span>
                                @elseif($check->status === 'mismatch')
                                    <span class="badge bg-warning text-dark">Mismatch</span>
                                @else
                                    <span class="badge bg-danger">Error</span>
                                @endif
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row g-4 mb-4">
                <div class="col-md-4">
                    <div class="card shadow-sm border-0 rounded-4">
                        <div class="card-body p-4">
                            <div class="text-muted small text-uppercase">Expected Holding</div>
                            <div class="fs-4 fw-bold">${{ number_format($check->expected_holding_amount_cents / 100, 2) }}</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card shadow-sm border-0 rounded-4">
                        <div class="card-body p-4">
                            <div class="text-muted small text-uppercase">Actual Holding</div>
                            <div class="fs-4 fw-bold">${{ number_format($check->actual_holding_amount_cents / 100, 2) }}</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card shadow-sm border-0 rounded-4">
                        <div class="card-body p-4">
                            <div class="text-muted small text-uppercase">Difference</div>
                            <div class="fs-4 fw-bold">${{ number_format($check->difference_amount_cents / 100, 2) }}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-header bg-light fw-semibold">Component Totals (Cents)</div>
                <div class="card-body">
                    @php $components = $check->meta['components_cents'] ?? []; @endphp
                    <div class="row g-3">
                        <div class="col-md-4"><strong>Sales Receipts:</strong> {{ $components['sales_receipts'] ?? 0 }}</div>
                        <div class="col-md-4"><strong>Fees:</strong> {{ $components['fees'] ?? 0 }}</div>
                        <div class="col-md-4"><strong>Refunds:</strong> {{ $components['refunds'] ?? 0 }}</div>
                        <div class="col-md-4"><strong>Adjustments:</strong> {{ $components['adjustments'] ?? 0 }}</div>
                        <div class="col-md-4"><strong>Payout Transfers:</strong> {{ $components['payout_transfers'] ?? 0 }}</div>
                    </div>
                </div>
            </div>

            @php
                $unsyncedPaidPayoutsCents = $check->meta['unsynced_paid_payouts_cents'] ?? 0;
                $counts = $check->meta['component_counts'] ?? [];
                $unsyncedPaidPayoutRows = $counts['paid_payout_rows_unsynced'] ?? 0;
            @endphp
            @if($unsyncedPaidPayoutRows > 0 || $unsyncedPaidPayoutsCents !== 0)
                <div class="alert alert-warning">
                    <strong>Unsynced paid payouts detected:</strong>
                    {{ $unsyncedPaidPayoutRows }} row(s), {{ $unsyncedPaidPayoutsCents }} cents.
                    These are excluded from expected payout transfers until they have a QBO transfer ID.
                </div>
            @endif

            @if($check->notes)
                <div class="alert alert-warning">
                    <strong>Notes:</strong> {{ $check->notes }}
                </div>
            @endif

            <div class="card shadow-sm border-0 rounded-4">
                <div class="card-header bg-light fw-semibold">Actions</div>
                <div class="card-body">
                    <form method="POST" action="{{ route('admin.payments.reconciliation.rerun') }}" class="d-flex gap-2">
                        @csrf
                        @if($check->business_id)
                            <input type="hidden" name="business_id" value="{{ $check->business_id }}">
                        @endif
                        @if($check->as_of_date)
                            <input type="hidden" name="as_of_date" value="{{ $check->as_of_date->toDateString() }}">
                        @endif
                        <button type="submit" class="btn btn-primary">Re-run This Check</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
