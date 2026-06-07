<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
            {{ __('Ready For Production') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Production Table Card -->
            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="card-header bg-white py-3 px-4 border-bottom-0">
                    <div class="d-flex align-items-center justify-content-between">
                        <h5 class="fw-bold mb-0">Active Production Queue</h5>
                        <span class="badge bg-primary text-uppercase tracking-wider px-3">{{ $orders->total() }} Orders</span>
                    </div>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table align-middle mb-0">
                            <thead class="bg-light">
                                <tr>
                                    <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">Order Date</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted" style="width: 80px;">ID</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Business</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Contact</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Email</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Payment</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted">Status</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-center">Inches (L/S)</th>
                                    <th class="py-3 text-uppercase small fw-bold text-muted text-end pe-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($orders as $order)
                                    <tr class="hover-bg-light transition">
                                        <td class="ps-4 py-3 text-secondary">
                                            {{ $order->order_date ? $order->order_date->format('m-d-Y') : 'N/A' }}
                                        </td>
                                        <td class="py-3 fw-bold">#{{ $order->id }}</td>
                                        <td class="py-3 fw-semibold text-dark">{{ $order->business->business_name }}</td>
                                        <td class="py-3 text-secondary small">{{ $order->business->contact_name }}</td>
                                        <td class="py-3 small">
                                            <a href="mailto:{{ $order->business->email }}" class="text-decoration-none">{{ $order->business->email }}</a>
                                        </td>
                                        <td class="py-3">
                                            @if($order->isPaid())
                                                <span class="text-success fw-bold smaller"><i class="bi bi-check-circle-fill me-1"></i> PAID</span>
                                            @else
                                                <span class="text-danger fw-bold smaller"><i class="bi bi-x-circle-fill me-1"></i> UNPAID</span>
                                            @endif
                                        </td>
                                        <td class="py-3">
                                            <span class="badge border text-uppercase px-2 py-1" style="background-color: {{ $order->orderStatus->color ?? '#6c757d' }}22; color: {{ $order->orderStatus->color ?? '#6c757d' }}; border-color: {{ $order->orderStatus->color ?? '#6c757d' }}44; font-size: 0.7rem;">
                                                {{ $order->orderStatus->name ?? 'Unknown' }}
                                            </span>
                                        </td>
                                        <td class="py-3 text-center small fw-bold">
                                            {{ $order->linear_inches }} / {{ $order->square_inches }}
                                        </td>
                                        <td class="py-3 text-end pe-4">
                                            <div class="btn-group">
                                                <a href="{{ route('admin.orders.production-order', $order->id) }}" class="btn btn-sm btn-outline-success fw-bold px-3">
                                                    <i class="bi bi-printer me-1"></i> Print
                                                </a>
                                                <button class="btn btn-sm btn-info fw-bold px-3 add-order-to-production"
                                                        data-id="{{ $order->id }}"
                                                        data-images="{{ json_encode($order->dtfImages->pluck('id')->toArray()) }}">
                                                    <i class="bi bi-plus-circle me-1"></i> Production
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="9" class="text-center py-5">
                                            <div class="text-muted mb-2"><i class="bi bi-clipboard-check fs-1"></i></div>
                                            <p class="text-muted mb-0">No orders currently in production queue.</p>
                                        </td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
                @if($orders->hasPages())
                    <div class="card-footer bg-white border-top-0 py-3 px-4">
                        {{ $orders->links() }}
                    </div>
                @endif
            </div>
        </div>
    </div>

    <!-- Production Progress Modal -->
    <div class="modal fade" id="productionProgressModal" data-bs-backdrop="static" data-bs-keyboard="false" tabindex="-1" aria-labelledby="productionProgressModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow rounded-4">
                <div class="modal-header bg-primary text-white py-3 px-4 border-bottom-0 rounded-top-4">
                    <h5 class="modal-title fw-bold" id="productionProgressModalLabel">Production Processing</h5>
                </div>
                <div class="modal-body p-4 text-center">
                    <div id="progressStatus" class="mb-3 fw-bold">Starting...</div>
                    <div class="progress mb-3" style="height: 25px;">
                        <div id="productionProgressBar" class="progress-bar progress-bar-striped progress-bar-animated bg-success" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                    </div>
                    <div id="progressDetails" class="small text-muted">Please wait while we process the images.</div>
                </div>
            </div>
        </div>
    </div>

    <style>
        .hover-bg-light:hover { background-color: rgba(0,0,0,.02); }
        .transition { transition: all 0.2s ease-in-out; }
        .smaller { font-size: 0.75rem; }
    </style>

    @push('scripts')
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const progressModal = new bootstrap.Modal(document.getElementById('productionProgressModal'));
            const progressBar = document.getElementById('productionProgressBar');
            const progressStatus = document.getElementById('progressStatus');
            const progressDetails = document.getElementById('progressDetails');

            async function processImage(imageId, index, total) {
                const percent = Math.round(((index) / total) * 100);
                progressBar.style.width = percent + '%';
                progressBar.innerText = percent + '%';
                progressBar.setAttribute('aria-valuenow', percent);
                progressStatus.innerText = `Processing image ${index + 1} of ${total}...`;
                progressDetails.innerText = `Currently processing Image ID: ${imageId}`;

                try {
                    const response = await fetch("{{ route('admin.orders.add-to-production') }}", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRF-TOKEN": "{{ csrf_token() }}"
                        },
                        body: JSON.stringify({ image_id: imageId })
                    });

                    const data = await response.json();
                    if (data.status !== 'success') {
                        throw new Error(data.message || 'Unknown error');
                    }
                    return true;
                } catch (err) {
                    console.error(err);
                    alert(`Error processing image ${imageId}: ${err.message}`);
                    return false;
                }
            }

            document.querySelectorAll('.add-order-to-production').forEach(btn => {
                btn.addEventListener('click', async function() {
                    const imageIds = JSON.parse(this.dataset.images || '[]');
                    const orderId = this.dataset.id;

                    if (imageIds.length === 0) {
                        alert('No images to process.');
                        return;
                    }

                    if (!confirm(`Add ${imageIds.length} images to production?`)) return;

                    progressModal.show();

                    let successCount = 0;
                    for (let i = 0; i < imageIds.length; i++) {
                        const success = await processImage(imageIds[i], i, imageIds.length);
                        if (success) successCount++;
                    }

                    if (successCount === imageIds.length) {
                        progressBar.style.width = '100%';
                        progressBar.innerText = '100%';
                        progressStatus.innerText = 'Order processing completed!';
                        setTimeout(() => window.location.reload(), 800);
                    } else {
                        progressStatus.innerText = `Processing finished with some errors (${successCount}/${imageIds.length} successful).`;
                        progressDetails.innerText = 'Please check the errors and try again.';
                        setTimeout(() => window.location.reload(), 3000);
                    }
                });
            });
        });
    </script>
    @endpush
</x-app-layout>
