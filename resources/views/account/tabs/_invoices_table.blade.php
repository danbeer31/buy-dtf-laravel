<h5 class="mb-4">QuickBooks Invoices</h5>
@if(count($invoiceHistory) > 0)
    <div class="table-responsive">
        <table class="table table-hover align-middle">
            <thead class="table-light">
                <tr>
                    <th><i class="bi bi-hash me-1 text-muted"></i>Invoice #</th>
                    <th><i class="bi bi-calendar-event me-1 text-muted"></i>Date</th>
                    <th><i class="bi bi-calendar-check me-1 text-muted"></i>Due Date</th>
                    <th><i class="bi bi-info-circle me-1 text-muted"></i>Status</th>
                    <th class="text-end"><i class="bi bi-cash me-1 text-muted"></i>Amount</th>
                    <th class="text-end"><i class="bi bi-cash-stack me-1 text-muted"></i>Balance</th>
                    <th class="text-end">Actions</th>
                </tr>
            </thead>
            <tbody>
                @foreach($invoiceHistory as $inv)
                    @php
                        $dueDate = \Carbon\Carbon::parse($inv['DueDate']);
                        $isPaid = $inv['Balance'] <= 0;
                        $isOverdue = !$isPaid && $dueDate->isPast() && !$dueDate->isToday();
                    @endphp
                    <tr>
                        <td class="fw-bold">{{ $inv['DocNumber'] ?? $inv['Id'] }}</td>
                        <td>{{ \Carbon\Carbon::parse($inv['TxnDate'])->format('m/d/Y') }}</td>
                        <td>{{ $dueDate->format('m/d/Y') }}</td>
                        <td>
                            @if($isPaid)
                                <span class="badge bg-success">Paid</span>
                            @elseif($isOverdue)
                                <span class="badge bg-danger">Overdue</span>
                            @else
                                <span class="badge bg-warning text-dark">Open</span>
                            @endif
                        </td>
                        <td class="text-end">${{ number_format($inv['TotalAmt'], 2) }}</td>
                        <td class="text-end fw-bold">${{ number_format($inv['Balance'], 2) }}</td>
                        <td class="text-end">
                            @if(!$isPaid)
                                <button type="button" class="btn btn-sm btn-primary py-0 px-2 fw-bold"
                                        onclick="if(typeof uncheckAllInvoices === 'function') { uncheckAllInvoices(); document.getElementById('check_inv_{{ $inv['Id'] }}').checked = true; if(typeof updateSelectedTotal === 'function') updateSelectedTotal(); }"
                                        data-bs-toggle="modal" data-bs-target="#payInvoicesModal">
                                    Pay
                                </button>
                            @else
                                <span class="text-muted small"><i class="bi bi-check-all text-success"></i> Settled</span>
                            @endif
                        </td>
                    </tr>
                @endforeach
            </tbody>
        </table>
    </div>
    <p class="small text-muted mt-3">Showing last {{ count($invoiceHistory) }} invoices from QuickBooks.</p>
@else
    <div class="text-center py-5">
        <i class="bi bi-receipt-cutoff fs-1 text-muted opacity-25"></i>
        <p class="mt-3 text-muted">No QuickBooks invoices found for your account.</p>
    </div>
@endif
