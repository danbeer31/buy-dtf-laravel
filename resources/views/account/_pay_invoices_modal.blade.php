<div class="modal fade" id="payInvoicesModal" tabindex="-1" aria-labelledby="payInvoicesModalLabel" aria-hidden="true">
    <div class="modal-dialog modal-lg">
        <div class="modal-content border-0 shadow rounded-4">
            <div class="modal-header bg-dark text-white py-3 px-4 border-bottom-0 rounded-top-4">
                <h5 class="modal-title fw-bold" id="payInvoicesModalLabel">Pay Outstanding Invoices</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body p-4">
                <p class="mb-4">Select the invoices you would like to pay. Payments are processed securely via Stripe.</p>

                <div class="table-responsive">
                    <table class="table align-middle">
                        <thead class="bg-light">
                            <tr>
                                <th style="width: 40px;"></th>
                                <th>Invoice #</th>
                                <th>Date</th>
                                <th>Due Date</th>
                                <th class="text-end">Balance</th>
                            </tr>
                        </thead>
                        <tbody>
                            @foreach($unpaidInvoices as $inv)
                                @php
                                    $dueDate = \Carbon\Carbon::parse($inv['DueDate']);
                                    $isInvOverdue = $dueDate->isPast() && !$dueDate->isToday();
                                    $payableBalance = $inv['PayableBalance'] ?? $inv['Balance'];
                                @endphp
                                <tr class="{{ $isInvOverdue ? 'table-danger-subtle' : '' }}">
                                    <td>
                                        <input type="checkbox" class="form-check-input invoice-checkbox" id="check_inv_{{ $inv['Id'] }}" data-id="{{ $inv['Id'] }}" data-amount="{{ $payableBalance }}" checked>
                                    </td>
                                    <td class="fw-bold">{{ $inv['DocNumber'] ?? $inv['Id'] }}</td>
                                    <td>{{ \Carbon\Carbon::parse($inv['TxnDate'])->format('m/d/Y') }}</td>
                                    <td>
                                        <span class="{{ $isInvOverdue ? 'text-danger fw-bold' : '' }}">
                                            {{ $dueDate->format('m/d/Y') }}
                                        </span>
                                        @if($isInvOverdue)
                                            <span class="badge bg-danger ms-1">OVERDUE</span>
                                        @endif
                                    </td>
                                    <td class="text-end fw-bold">${{ number_format($payableBalance, 2) }}</td>
                                </tr>
                            @endforeach
                        </tbody>
                        <tfoot class="bg-light">
                            <tr class="fw-bold">
                                <td colspan="4" class="text-end">Total to Pay:</td>
                                <td class="text-end text-primary fs-5" id="selectedTotal">${{ number_format($qboBalance, 2) }}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>
            <div class="modal-footer bg-light border-top-0 py-3 px-4">
                <button type="button" class="btn btn-secondary fw-bold text-uppercase" data-bs-dismiss="modal">Cancel</button>
                <form id="paymentForm" action="{{ route('qbo.pay') }}" method="POST">
                    @csrf
                    <input type="hidden" name="invoice_ids" id="invoiceIdsInput" value="{{ implode(',', array_column($unpaidInvoices, 'Id')) }}">
                    <button type="button" id="payButton" class="btn btn-primary fw-bold text-uppercase px-4">
                        Proceed to Payment
                    </button>
                </form>
            </div>
        </div>
    </div>
</div>
