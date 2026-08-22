<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">Stripe/QBO Reconciliation</h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <form method="GET" action="{{ route('admin.payments.reconciliation.index') }}" class="row g-3 align-items-end">
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">Status</label>
                            <select name="status" class="form-select">
                                <option value="">All</option>
                                @foreach(['balanced', 'mismatch', 'error'] as $status)
                                    <option value="{{ $status }}" {{ request('status') === $status ? 'selected' : '' }}>
                                        {{ ucfirst($status) }}
                                    </option>
                                @endforeach
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label fw-semibold">Business ID</label>
                            <input type="number" class="form-control" name="business_id" value="{{ request('business_id') }}">
                        </div>
                        <div class="col-md-6 d-flex gap-2">
                            <button type="submit" class="btn btn-primary">Filter</button>
                            <a href="{{ route('admin.payments.reconciliation.index') }}" class="btn btn-outline-secondary">Reset</a>
                        </div>
                    </form>
                    <form method="POST" action="{{ route('admin.payments.reconciliation.rerun') }}" class="mt-3 text-end">
                        @csrf
                        <button type="submit" class="btn btn-outline-primary">Run Global Check</button>
                    </form>
                </div>
            </div>

            <div class="card shadow-sm border-0 rounded-4">
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>ID</th>
                                    <th>Business</th>
                                    <th>As Of</th>
                                    <th class="text-end">Expected</th>
                                    <th class="text-end">Actual</th>
                                    <th class="text-end">Diff</th>
                                    <th>Status</th>
                                    <th>Ran At</th>
                                    <th class="text-end">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($checks as $check)
                                    <tr>
                                        <td>{{ $check->id }}</td>
                                        <td>
                                            @if($check->business)
                                                <div class="fw-semibold">{{ $check->business->business_name ?: 'Business #' . $check->business->id }}</div>
                                                <div class="small text-muted">ID {{ $check->business->id }}</div>
                                            @else
                                                <span class="text-muted">Global</span>
                                            @endif
                                        </td>
                                        <td>{{ $check->as_of_date ? $check->as_of_date->format('m/d/Y') : 'Current' }}</td>
                                        <td class="text-end">${{ number_format($check->expected_holding_amount_cents / 100, 2) }}</td>
                                        <td class="text-end">${{ number_format($check->actual_holding_amount_cents / 100, 2) }}</td>
                                        <td class="text-end fw-bold">${{ number_format($check->difference_amount_cents / 100, 2) }}</td>
                                        <td>
                                            @if($check->status === 'balanced')
                                                <span class="badge bg-success">Balanced</span>
                                            @elseif($check->status === 'mismatch')
                                                <span class="badge bg-warning text-dark">Mismatch</span>
                                            @else
                                                <span class="badge bg-danger">Error</span>
                                            @endif
                                        </td>
                                        <td>{{ optional($check->ran_at)->format('m/d/Y H:i') }}</td>
                                        <td class="text-end text-nowrap">
                                            <a class="btn btn-sm btn-outline-secondary" href="{{ route('admin.payments.reconciliation.show', $check) }}">Detail</a>
                                            <form method="POST" action="{{ route('admin.payments.reconciliation.rerun') }}" class="d-inline">
                                                @csrf
                                                @if($check->business_id)
                                                    <input type="hidden" name="business_id" value="{{ $check->business_id }}">
                                                @endif
                                                @if($check->as_of_date)
                                                    <input type="hidden" name="as_of_date" value="{{ $check->as_of_date->toDateString() }}">
                                                @endif
                                                <button type="submit" class="btn btn-sm btn-primary">Re-run</button>
                                            </form>
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="9" class="text-center py-4 text-muted">No reconciliation checks found.</td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="mt-3">
                {{ $checks->links() }}
            </div>
        </div>
    </div>
</x-app-layout>
