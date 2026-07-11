<x-app-layout>
    <x-slot name="header">
        <div class="d-flex justify-content-between align-items-center">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                {{ __('Stripe Sync Logs') }}
            </h2>
            <div class="d-flex gap-2">
                <a href="{{ route('admin.payments.stripe') }}" class="btn btn-outline-secondary fw-bold text-uppercase shadow-sm">
                    <i class="bi bi-credit-card me-1"></i> Transactions
                </a>
                <a href="{{ route('admin.payments.stripe.payouts') }}" class="btn btn-outline-primary fw-bold text-uppercase shadow-sm">
                    <i class="bi bi-bank me-1"></i> Payouts
                </a>
            </div>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Filter Card -->
            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <form method="GET" action="{{ route('admin.payments.stripe.sync-logs') }}" class="row g-3 align-items-end">
                        <div class="col-md-4">
                            <label for="type" class="form-label small fw-bold text-uppercase text-muted">Sync Type</label>
                            <select name="type" id="type" class="form-select bg-light border-0">
                                <option value="">All Types</option>
                                <option value="webhook" {{ request('type') == 'webhook' ? 'selected' : '' }}>Webhook</option>
                                <option value="cron" {{ request('type') == 'cron' ? 'selected' : '' }}>Cron Job</option>
                                <option value="manual" {{ request('type') == 'manual' ? 'selected' : '' }}>Manual</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <label for="status" class="form-label small fw-bold text-uppercase text-muted">Status</label>
                            <select name="status" id="status" class="form-select bg-light border-0">
                                <option value="">All Statuses</option>
                                <option value="success" {{ request('status') == 'success' ? 'selected' : '' }}>Success</option>
                                <option value="failure" {{ request('status') == 'failure' ? 'selected' : '' }}>Failure</option>
                                <option value="partial" {{ request('status') == 'partial' ? 'selected' : '' }}>Partial</option>
                            </select>
                        </div>
                        <div class="col-md-4">
                            <button type="submit" class="btn btn-primary w-100 fw-bold text-uppercase py-2 shadow-sm">
                                <i class="bi bi-filter me-1"></i> Filter
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Logs Table -->
            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table align-middle mb-0">
                            <thead class="bg-light">
                                <tr>
                                    <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">Date</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Type</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Event</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Stripe ID</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Status</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Message</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($logs as $log)
                                    <tr class="hover-bg-light transition">
                                        <td class="ps-4 py-3 small text-muted">
                                            {{ $log->created_at->format('M d, H:i:s') }}
                                        </td>
                                        <td class="py-3">
                                            <span class="badge {{ $log->sync_type == 'webhook' ? 'bg-info' : ($log->sync_type == 'cron' ? 'bg-secondary' : 'bg-primary') }} text-uppercase" style="font-size: 0.7rem;">
                                                {{ $log->sync_type }}
                                            </span>
                                        </td>
                                        <td class="py-3 small">
                                            {{ $log->event_type ?: '--' }}
                                        </td>
                                        <td class="py-3 small font-monospace">
                                            {{ $log->stripe_id ?: '--' }}
                                        </td>
                                        <td class="py-3">
                                            @if($log->status == 'success')
                                                <span class="text-success"><i class="bi bi-check-circle-fill me-1"></i> Success</span>
                                            @elseif($log->status == 'failure')
                                                <span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i> Failure</span>
                                            @else
                                                <span class="text-warning"><i class="bi bi-exclamation-circle-fill me-1"></i> {{ ucfirst($log->status) }}</span>
                                            @endif
                                        </td>
                                        <td class="py-3 small text-truncate" style="max-width: 250px;">
                                            {{ $log->message }}
                                        </td>
                                        <td class="py-3 text-end pe-4">
                                            <a href="{{ route('admin.payments.stripe.sync-logs.show', $log->id) }}" class="btn btn-sm btn-outline-primary fw-bold">
                                                <i class="bi bi-eye"></i>
                                            </a>
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="7" class="text-center py-5">
                                            <p class="text-muted mb-0">No sync logs found.</p>
                                        </td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
                @if($logs->hasPages())
                    <div class="card-footer bg-white border-top-0 py-3 px-4">
                        {{ $logs->links() }}
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
