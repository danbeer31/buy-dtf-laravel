<x-app-layout>
    <x-slot name="header">
        <div class="d-flex align-items-center justify-content-between">
            <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
                Stripe Detail: {{ $payment->processor_confirm }}
            </h2>
            <a href="{{ route('admin.payments.stripe') }}" class="btn btn-outline-secondary btn-sm fw-bold">
                <i class="bi bi-arrow-left me-1"></i> Back to Transactions
            </a>
        </div>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row g-4">
                <!-- Left Column: Transaction Details -->
                <div class="col-lg-8">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-dark text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold">Transaction Information</h5>
                        </div>
                        <div class="card-body p-4">
                            <div class="row g-4">
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Processor</label>
                                    <p class="fs-5 fw-bold mb-0">Stripe</p>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Status</label>
                                    <span class="badge bg-success-subtle text-success border border-success-subtle text-uppercase px-3 py-2">
                                        {{ $payment->status }}
                                    </span>
                                </div>
                                <div class="col-md-12">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Stripe PaymentIntent ID</label>
                                    <p class="fs-5 font-monospace mb-0 text-primary">{{ $payment->processor_confirm }}</p>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Date Created</label>
                                    <p class="fs-5 fw-bold mb-0">{{ $payment->created_at ? $payment->created_at->format('F d, Y H:i:s') : 'N/A' }}</p>
                                </div>
                                <div class="col-md-6">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Last Updated</label>
                                    <p class="fs-5 fw-bold mb-0">
                                        @if($payment->updated_at && $payment->updated_at->year > 0)
                                            {{ $payment->updated_at->format('F d, Y H:i:s') }}
                                        @else
                                            N/A
                                        @endif
                                    </p>
                                </div>
                            </div>

                            <hr class="my-4">

                            <h6 class="fw-bold mb-3">Associated Order / Invoice</h6>
                            @if($payment->dtforder_id && $payment->dtforder_id != 0 && $payment->dtfOrder)
                                <div class="p-3 bg-light rounded-3 d-flex justify-content-between align-items-center">
                                    <div>
                                        <p class="fw-bold mb-1">DTF Order #{{ $payment->dtforder_id }}</p>
                                        @if($payment->dtfOrder->qbo_invoice_number)
                                            <p class="mb-1 text-primary fw-bold">QuickBooks Invoice: {{ $payment->dtfOrder->qbo_invoice_number }}</p>
                                        @endif
                                        <p class="text-muted small mb-0">
                                            @if($payment->dtfOrder->business)
                                                Business: {{ $payment->dtfOrder->business->business_name }}
                                            @endif
                                        </p>
                                    </div>
                                    <a href="{{ route('admin.orders.show', $payment->dtforder_id) }}" class="btn btn-sm btn-primary fw-bold">
                                        View Order
                                    </a>
                                </div>
                            @elseif($payment->notes && str_contains($payment->notes, 'QBO Invoice Payment'))
                                <div class="alert alert-info mb-3">
                                    <i class="bi bi-info-circle me-1"></i> This is a generic payment for multiple QBO invoices.
                                </div>
                                @if($payment->qbo_invoice_numbers)
                                    <div class="p-3 bg-light rounded-3 mb-3">
                                        <label class="small text-uppercase text-muted fw-bold d-block mb-1">QuickBooks Invoice Numbers</label>
                                        <p class="fs-5 fw-bold text-primary mb-0">{{ $payment->qbo_invoice_numbers }}</p>
                                    </div>
                                @endif
                            @else
                                <div class="alert alert-warning mb-0">No order found for this payment record.</div>
                            @endif

                            @if($payment->stripePayoutEntries->count() > 0)
                                <div class="mt-4 p-3 bg-success-subtle border border-success-subtle rounded-4">
                                    <h6 class="fw-bold text-success mb-3">Associated Stripe Payout(s)</h6>
                                    @foreach($payment->stripePayoutEntries as $entry)
                                        <div class="d-flex justify-content-between align-items-center mb-2 pb-2 border-bottom border-success-subtle last-border-0">
                                            <div>
                                                <div class="fw-bold">{{ $entry->payout->stripe_payout_id }}</div>
                                                <div class="small text-muted">Arrival: {{ $entry->payout->arrival_date->format('M d, Y') }} ({{ $entry->payout->status }})</div>
                                            </div>
                                            <a href="{{ route('admin.payments.stripe.payouts.show', $entry->stripe_payout_id) }}" class="btn btn-sm btn-success fw-bold">
                                                View Payout
                                            </a>
                                        </div>
                                    @endforeach
                                </div>
                            @endif
                        </div>
                    </div>

                    <!-- Financial Summary Card -->
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-white border-bottom py-3 px-4 d-flex justify-content-between align-items-center">
                            <h5 class="mb-0 fw-bold">Financial Summary</h5>
                            @if(!$payment->stripe_fee || $payment->stripe_fee == 0)
                                <form action="{{ route('admin.payments.stripe.refresh-fee', $payment) }}" method="POST">
                                    @csrf
                                    <button type="submit" class="btn btn-sm btn-outline-primary fw-bold">
                                        <i class="bi bi-arrow-clockwise me-1"></i> Refresh Fee from Stripe
                                    </button>
                                </form>
                            @endif
                        </div>
                        <div class="card-body p-4">
                            <div class="row text-center">
                                <div class="col-md-4">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Gross Amount</label>
                                    <p class="h3 fw-bold text-success mb-0">${{ number_format($payment->amount, 2) }}</p>
                                </div>
                                <div class="col-md-4">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Stripe Fee</label>
                                    <p class="h3 fw-bold text-danger mb-0">-${{ number_format($payment->stripe_fee ?: 0, 2) }}</p>
                                </div>
                                <div class="col-md-4">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Net Amount</label>
                                    <p class="h3 fw-bold text-dark mb-0">${{ number_format($payment->amount - ($payment->stripe_fee ?: 0), 2) }}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Column: Business Info -->
                <div class="col-lg-4">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-primary text-white py-3 px-4">
                            <h5 class="mb-0 fw-bold">Business Contact</h5>
                        </div>
                        <div class="card-body p-4">
                            @if($payment->business)
                                <div class="mb-3">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Business Name</label>
                                    <p class="fw-bold mb-0">{{ $payment->business->business_name }}</p>
                                </div>
                                <div class="mb-3">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Contact Name</label>
                                    <p class="mb-0">{{ $payment->business->contact_name }}</p>
                                </div>
                                <div class="mb-0">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Email</label>
                                    <p class="mb-0"><a href="mailto:{{ $payment->business->email }}">{{ $payment->business->email }}</a></p>
                                </div>
                                <hr>
                                <a href="{{ route('admin.businesses.show', $payment->business_id) }}" class="btn btn-sm btn-outline-primary w-100 fw-bold">
                                    View Business Detail
                                </a>
                            @elseif($payment->dtfOrder && $payment->dtfOrder->business)
                                <div class="mb-3">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Business Name</label>
                                    <p class="fw-bold mb-0">{{ $payment->dtfOrder->business->business_name }}</p>
                                </div>
                                <div class="mb-3">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Contact Name</label>
                                    <p class="mb-0">{{ $payment->dtfOrder->business->contact_name }}</p>
                                </div>
                                <div class="mb-0">
                                    <label class="small text-uppercase text-muted fw-bold d-block mb-1">Email</label>
                                    <p class="mb-0"><a href="mailto:{{ $payment->dtfOrder->business->email }}">{{ $payment->dtfOrder->business->email }}</a></p>
                                </div>
                                <hr>
                                <a href="{{ route('admin.businesses.show', $payment->dtfOrder->business_id) }}" class="btn btn-sm btn-outline-primary w-100 fw-bold">
                                    View Business Detail
                                </a>
                            @else
                                <p class="text-muted mb-0">No business associated.</p>
                            @endif
                        </div>
                    </div>

                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden mb-4">
                        <div class="card-header bg-light py-3 px-4 border-bottom">
                            <h5 class="mb-0 fw-bold">Internal Notes</h5>
                        </div>
                        <div class="card-body p-4">
                            <p class="mb-0 text-secondary italic">
                                {{ $payment->notes ?: 'No notes for this transaction.' }}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
