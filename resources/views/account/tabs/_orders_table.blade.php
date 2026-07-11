<div class="d-flex justify-content-between align-items-center mb-4">
    <h5 class="mb-0">Order History</h5>
    @if(!$business->open_order())
        <a href="{{ route('orders.new') }}" class="btn btn-primary">
            <i class="bi bi-plus-circle me-1"></i> Start New Order
        </a>
    @else
        <a href="{{ route('cart.index') }}" class="btn btn-success">
            <i class="bi bi-cart-plus me-1"></i> Continue Open Order
        </a>
    @endif
</div>

@if($orders->count() > 0)
    <div class="table-responsive">
        <table class="table table-hover align-middle">
            <thead class="table-light">
                <tr>
                    <th><i class="bi bi-hash me-1 text-muted"></i>Invoice #</th>
                    <th><i class="bi bi-calendar-event me-1 text-muted"></i>Date</th>
                    <th><i class="bi bi-info-circle me-1 text-muted"></i>Status</th>
                    <th><i class="bi bi-credit-card me-1 text-muted"></i>Payment</th>
                    <th class="text-center"><i class="bi bi-images me-1 text-muted"></i>Images</th>
                    <th class="text-end"><i class="bi bi-cash-stack me-1 text-muted"></i>Total</th>
                    <th class="text-end">Actions</th>
                </tr>
            </thead>
            <tbody>
                @foreach($orders as $order)
                    @php
                        $qboInvoice = isset($qboInvoicesMap[$order->qbo_invoice_id])
                            ? $qboInvoicesMap[$order->qbo_invoice_id]
                            : (
                                $order->qbo_invoice_number && isset($qboInvoicesMap['doc_' . $order->qbo_invoice_number])
                                    ? $qboInvoicesMap['doc_' . $order->qbo_invoice_number]
                                    : null
                            );
                        $qboDocNumber = $qboInvoice['DocNumber'] ?? null;
                        $localPayment = $order->paymentInfo;
                        $localPaid = $localPayment && $localPayment->processor === 'Stripe' && $localPayment->status === 'complete';
                        $localInvoiced = $localPayment && $localPayment->processor === 'QB Invoice' && in_array($localPayment->status, ['invoiced', 'processing', 'complete']);
                        $isPaid = $qboInvoice ? (($qboInvoice['Balance'] ?? 0) <= 0) : $localPaid;
                    @endphp
                    <tr>
                        <td>
                            @if($qboDocNumber)
                                {{ $qboDocNumber }}
                            @else
                                {{ $order->id }}
                            @endif
                        </td>
                        <td>{{ $order->order_date->format('m/d/Y') }}</td>
                        <td>
                            <span class="badge" style="background-color: {{ $order->orderStatus->color ?? '#6c757d' }}">
                                {{ ucfirst($order->orderStatus->name ?? 'Unknown') }}
                            </span>
                        </td>
                        <td>
                            @if($qboInvoice)
                                @if($isPaid)
                                    <span class="badge bg-success">Paid</span>
                                @else
                                    <span class="badge bg-warning text-dark">Open</span>
                                @endif
                            @elseif($localPaid)
                                <span class="badge bg-success">Paid</span>
                            @elseif($localInvoiced)
                                <span class="badge bg-info text-dark">Invoiced</span>
                            @else
                                <span class="badge bg-secondary">Pending</span>
                            @endif
                        </td>
                        <td class="text-center">{{ $order->get_total_image_count() }}</td>
                        <td class="text-end fw-bold text-nowrap">
                            ${{ number_format($order->total_price, 2) }}
                        </td>
                        <td class="text-end text-nowrap">
                            <a href="{{ route('account.orders.show', $order->id) }}" class="btn btn-sm btn-outline-primary me-1">
                                <i class="bi bi-eye me-1"></i>View
                            </a>
                            @if($order->status == 1)
                                <a href="{{ route('cart.index') }}" class="btn btn-sm btn-outline-success">
                                    <i class="bi bi-cart me-1"></i>Edit
                                </a>
                            @endif
                        </td>
                    </tr>
                @endforeach
            </tbody>
        </table>
    </div>
    <div class="mt-4 ajax-pagination">
        {{ $orders->links() }}
    </div>
@else
    <div class="text-center py-5">
        <i class="bi bi-receipt fs-1 text-muted opacity-25"></i>
        <p class="mt-3 text-muted">No orders found.</p>
    </div>
@endif
