<x-app-layout>
    <x-slot name="header">
        <div class="d-flex align-items-center justify-content-between">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                Sync Log Detail: #{{ $log->id }}
            </h2>
            <a href="{{ route('admin.payments.stripe.sync-logs') }}" class="btn btn-outline-secondary btn-sm fw-bold">
                <i class="bi bi-arrow-left me-1"></i> Back to Logs
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row g-4">
                <div class="col-lg-8">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-dark text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold">Log Information</h5>
                        </div>
                        <div class="card-body p-4">
                            <div class="row g-4">
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Sync Type</label>
                                    <span class="badge {{ $log->sync_type == 'webhook' ? 'bg-info' : ($log->sync_type == 'cron' ? 'bg-secondary' : 'bg-primary') }} text-uppercase px-3 py-2">
                                        {{ $log->sync_type }}
                                    </span>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Status</label>
                                    <span class="badge {{ $log->status == 'success' ? 'bg-success' : 'bg-danger' }} text-uppercase px-3 py-2">
                                        {{ $log->status }}
                                    </span>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Event Type</label>
                                    <p class="fs-5 fw-bold mb-0">{{ $log->event_type ?: '--' }}</p>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Stripe ID</label>
                                    <p class="fs-5 font-monospace mb-0">{{ $log->stripe_id ?: '--' }}</p>
                                </div>
                                <div class="col-md-12">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Message</label>
                                    <p class="fs-5 mb-0">{{ $log->message }}</p>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Date</label>
                                    <p class="fs-5 fw-bold mb-0">{{ $log->created_at->format('F d, Y H:i:s') }}</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    @if($log->payload)
                        <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                            <div class="card-header bg-light py-3 px-4 border-bottom">
                                <h5 class="mb-0 fw-bold">Raw Payload Data</h5>
                            </div>
                            <div class="card-body p-0">
                                <pre class="m-0 p-4 bg-dark text-success" style="max-height: 500px; overflow-y: auto;">{{ json_encode($log->payload, JSON_PRETTY_PRINT) }}</pre>
                            </div>
                        </div>
                    @endif
                </div>

                <div class="col-lg-4">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-primary text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold">Related Actions</h5>
                        </div>
                        <div class="card-body p-4">
                            @if($log->stripe_id)
                                @if(str_starts_with($log->stripe_id, 'po_'))
                                    <a href="{{ route('admin.payments.stripe.payouts.show', $log->stripe_id) }}" class="btn btn-outline-primary w-100 fw-bold mb-3">
                                        <i class="bi bi-bank me-1"></i> View Payout Detail
                                    </a>
                                @elseif(str_starts_with($log->stripe_id, 'pi_') || str_starts_with($log->stripe_id, 'ch_'))
                                     <a href="{{ route('admin.payments.stripe.index', ['search' => $log->stripe_id]) }}" class="btn btn-outline-primary w-100 fw-bold mb-3">
                                        <i class="bi bi-credit-card me-1"></i> Search Transaction
                                    </a>
                                @endif
                            @endif
                            <p class="text-muted small mb-0">
                                This log was generated during a {{ $log->sync_type }} process.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
