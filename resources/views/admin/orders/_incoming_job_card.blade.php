@php($incomingJob = $image->incomingOrderJob)
@if($incomingJob && $incomingJob->job_label_status)
    <div class="mt-2 p-2 border rounded bg-light small" data-api-job-card="{{ $incomingJob->id }}">
        <div class="d-flex flex-wrap align-items-center gap-1 mb-1">
            <span class="badge bg-primary-subtle text-primary border">API Job Card</span>
            <span class="badge {{ $incomingJob->job_label_status === 'rendered' ? 'bg-success' : ($incomingJob->job_label_status === 'accepted' ? 'bg-info text-dark' : 'bg-secondary') }}">
                {{ ucfirst($incomingJob->job_label_status) }}
            </span>
            @if($incomingJob->production_state)
                <span class="text-muted">Handoff: {{ str_replace('_', ' ', $incomingJob->production_state) }}</span>
            @endif
        </div>
        @if(is_array($incomingJob->job_label_metadata))
            @php($card = $incomingJob->job_label_metadata)
            <div><strong>Order:</strong> #{{ $card['order_number'] }}</div>
            <div><strong>Product:</strong> {{ $card['product_name'] }}@if(!empty($card['product_sku'])) ({{ $card['product_sku'] }})@endif</div>
            <div><strong>Color / Size:</strong> {{ $card['color'] }} / {{ $card['size'] }}</div>
            <div><strong>Placement:</strong> {{ $card['placement'] }} &middot; <strong>Qty:</strong> {{ $card['quantity'] }}</div>
            <div><strong>Origin:</strong> {{ $card['shop_domain'] }}</div>
        @elseif($incomingJob->job_label_reason)
            <div class="text-muted">Metadata ignored: {{ str_replace('_', ' ', $incomingJob->job_label_reason) }}</div>
        @endif
    </div>
@endif
