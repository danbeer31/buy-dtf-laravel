<div class="card border-0 shadow-sm rounded-4 overflow-hidden mb-4">
    <div class="card-header bg-info text-white py-3">
        <h5 class="mb-0">Invoice Information</h5>
    </div>
    <div class="card-body p-4">
        <p class="text-danger fw-bold">
            By completing this order, you have agreed to the following terms:
        </p>
        <ul class="text-muted">
            <li>You agree to pay the invoice sent via QuickBooks to <strong>{{ $order->business->email }}</strong>.</li>
            @if($order->qbo_invoice_id)
                <li>Your QuickBooks Invoice ID is: <strong>{{ $order->qbo_invoice_id }}</strong></li>
            @endif
            <li>The invoice is due in 10 days from the date it is issued.</li>
        </ul>
        <div class="alert alert-info border-0 rounded-3 mb-0">
            <i class="bi bi-info-circle-fill me-2"></i>
            QuickBooks will send you an email with a link to pay your invoice online.
        </div>
        <p class="text-danger fw-bold mt-3 mb-0 small">
            Failure to pay the invoice on time may result in additional fees or penalties.
        </p>
    </div>
</div>
