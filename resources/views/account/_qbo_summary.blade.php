@if(isset($qboBalance) && $qboBalance > 0)
    @php
        $isOverdue = false;
        $dueSoon = false;
        $today = now()->startOfDay();
        foreach($unpaidInvoices as $inv) {
            $dueDate = \Carbon\Carbon::parse($inv['DueDate'])->startOfDay();
            if ($dueDate->isPast() && !$dueDate->isToday()) {
                $isOverdue = true;
                break;
            }
            if ($dueDate->diffInDays($today, true) <= 3) {
                $dueSoon = true;
            }
        }

        $alertClass = 'alert-warning';
        $iconClass = 'bi-exclamation-triangle-fill';
        if ($isOverdue) {
            $alertClass = 'alert-danger';
            $iconClass = 'bi-exclamation-octagon-fill';
        } elseif ($dueSoon) {
            $alertClass = 'alert-warning';
            $iconClass = 'bi-exclamation-triangle-fill';
        } else {
            $alertClass = 'alert-success';
            $iconClass = 'bi-check-circle-fill';
        }
    @endphp
    <div class="alert {{ $alertClass }} border-0 shadow-sm rounded-4 d-flex align-items-center mb-0 mt-3">
        <i class="bi {{ $iconClass }} fs-4 me-3"></i>
        <div class="flex-grow-1">
            <div class="fw-bold">{{ $isOverdue ? 'Overdue QuickBooks Balance' : 'Outstanding QuickBooks Balance' }}</div>
            <div class="fs-5 fw-bold {{ $isOverdue ? 'text-danger' : 'text-dark' }}">${{ number_format($qboBalance, 2) }}</div>
            <div class="small text-muted">
                @if($isOverdue)
                    You have overdue invoices. Please settle them immediately.
                @else
                    Please settle your outstanding invoices.
                @endif
            </div>
        </div>
        @if(count($unpaidInvoices) > 0)
            <div class="ms-3">
                <button type="button" class="btn btn-sm {{ $isOverdue ? 'btn-danger' : 'btn-primary' }} fw-bold" data-bs-toggle="modal" data-bs-target="#payInvoicesModal">
                    Pay Now
                </button>
            </div>
        @endif
    </div>
@elseif(isset($qboBalance) && $qboBalance <= 0)
    <div class="alert alert-success border-0 shadow-sm rounded-4 d-flex align-items-center mb-0 mt-3 py-2">
        <i class="bi bi-check-circle-fill fs-5 me-2"></i>
        <div class="small fw-bold">Your QuickBooks account is fully paid. Thank you!</div>
    </div>
@endif
