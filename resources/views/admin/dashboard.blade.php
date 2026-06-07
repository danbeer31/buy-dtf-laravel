<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Admin Dashboard') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Quick View Stats -->
            <div class="row g-3 mb-4">
                <div class="col-md">
                    <div class="card shadow-sm border-0 rounded-4 text-center p-3 h-100">
                        <div class="text-uppercase text-muted fw-bold small mb-1">waiting production</div>
                        <h4 class="fw-bold mb-0">{{ $stats['waiting_production'] }}</h4>
                    </div>
                </div>
                <div class="col-md">
                    <div class="card shadow-sm border-0 rounded-4 text-center p-3 h-100">
                        <div class="text-uppercase text-muted fw-bold small mb-1">In Production</div>
                        <h4 class="fw-bold mb-0 text-info">{{ $stats['in_production'] }}</h4>
                    </div>
                </div>
                <div class="col-md">
                    <div class="card shadow-sm border-0 rounded-4 text-center p-3 h-100">
                        <div class="text-uppercase text-muted fw-bold small mb-1">Pickup Ready</div>
                        <h4 class="fw-bold mb-0 text-warning">{{ $stats['pickup_ready'] }}</h4>
                    </div>
                </div>
                <div class="col-md">
                    <div class="card shadow-sm border-0 rounded-4 text-center p-3 h-100">
                        <div class="text-uppercase text-muted fw-bold small mb-1">Shipped</div>
                        <h4 class="fw-bold mb-0 text-primary">{{ $stats['shipped'] }}</h4>
                    </div>
                </div>
                <div class="col-md">
                    <div class="card shadow-sm border-0 rounded-4 text-center p-3 h-100">
                        <div class="text-uppercase text-muted fw-bold small mb-1">In Transit</div>
                        <h4 class="fw-bold mb-0 text-info">{{ $stats['in_transit'] }}</h4>
                    </div>
                </div>
                <div class="col-md">
                    <div class="card shadow-sm border-0 rounded-4 text-center p-3 h-100">
                        <div class="text-uppercase text-muted fw-bold small mb-1">Out for Delivery</div>
                        <h4 class="fw-bold mb-0 text-info">{{ $stats['out_for_delivery'] }}</h4>
                    </div>
                </div>
            </div>

            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <div class="d-flex flex-wrap justify-content-between align-items-center gap-3">
                        <div>
                            <h6 class="text-uppercase text-muted fw-bold mb-2">Stripe/QBO Reconciliation</h6>
                            <div class="d-flex align-items-center gap-3">
                                <span class="badge bg-success">Balanced: {{ $reconSummary['balanced'] ?? 0 }}</span>
                                <span class="badge bg-warning text-dark">Mismatches: {{ $reconSummary['mismatch'] ?? 0 }}</span>
                                <span class="badge bg-danger">Errors: {{ $reconSummary['error'] ?? 0 }}</span>
                            </div>
                        </div>
                        <a href="{{ route('admin.payments.reconciliation.index') }}" class="btn btn-outline-primary">
                            View Reconciliation
                        </a>
                    </div>
                </div>
            </div>

            <div class="row g-4 mb-4">
                <div class="col-md-6">
                    <div class="card shadow-sm border-0 rounded-4">
                        <div class="card-body p-4">
                            <h6 class="text-uppercase text-muted fw-bold mb-2">Today's Sales</h6>
                            <h3 class="fw-bold mb-1">${{ number_format($salesSummary['today'] ?? 0, 2) }}</h3>
                            <div class="small text-muted">{{ \Carbon\Carbon::parse($salesSummary['today_date'])->format('m/d/Y') }} (CT)</div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card shadow-sm border-0 rounded-4">
                        <div class="card-body p-4">
                            <h6 class="text-uppercase text-muted fw-bold mb-2">Last Year Total Sales</h6>
                            <h3 class="fw-bold mb-1">${{ number_format($salesSummary['last_year_total'] ?? 0, 2) }}</h3>
                            <div class="small text-muted">{{ $salesSummary['last_year_label'] ?? '' }}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <div class="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-3">
                        <div>
                            <h6 class="text-uppercase text-muted fw-bold mb-1">Who Owes Money</h6>
                            <div class="small text-muted">{{ $owedBusinessesCount ?? 0 }} businesses with an outstanding balance</div>
                        </div>
                        <div class="text-end">
                            <div class="small text-muted text-uppercase fw-bold">Total Owed</div>
                            <div class="fs-4 fw-bold">${{ number_format($totalOwed ?? 0, 2) }}</div>
                        </div>
                    </div>

                    @if(!empty($businessesWhoOwe))
                        <div class="table-responsive">
                            <table class="table table-sm align-middle mb-0">
                                <thead>
                                    <tr>
                                        <th>Business</th>
                                        <th class="text-end">Balance Owed</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    @foreach($businessesWhoOwe as $businessOwed)
                                        <tr>
                                            <td>{{ $businessOwed['business_name'] }}</td>
                                            <td class="text-end fw-semibold">${{ number_format($businessOwed['balance'], 2) }}</td>
                                        </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    @else
                        <div class="alert alert-success mb-0">No outstanding business balances.</div>
                    @endif
                </div>
            </div>

            <!-- Stats Summary -->
            <div class="row g-4 mb-4">
                <div class="col-md-4">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                        <div class="card-body p-4">
                            <h6 class="text-uppercase text-muted fw-bold mb-2">Weekly Sales</h6>
                            <h3 class="fw-bold mb-0">${{ number_format(array_sum($weeklyData), 2) }}</h3>
                            <div class="small text-muted mt-1">
                                Last year same 7 days ({{ \Carbon\Carbon::parse($salesSummary['weekly_last_year_label_start'])->format('m/d/Y') }} - {{ \Carbon\Carbon::parse($salesSummary['weekly_last_year_label_end'])->format('m/d/Y') }}):
                                ${{ number_format($salesSummary['weekly_last_year_same_window'] ?? 0, 2) }}
                            </div>
                        </div>
                        <div class="px-4 pb-4" style="height: 100px;">
                            <canvas id="weeklyChart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                        <div class="card-body p-4">
                            <h6 class="text-uppercase text-muted fw-bold mb-2">Monthly Sales</h6>
                            <h3 class="fw-bold mb-0">${{ number_format(array_sum($monthlyData), 2) }}</h3>
                            <div class="small text-muted mt-1">
                                Last year ({{ $salesSummary['same_month_last_year_label'] ?? '' }}):
                                ${{ number_format($salesSummary['same_month_last_year'] ?? 0, 2) }}
                            </div>
                        </div>
                        <div class="px-4 pb-4" style="height: 100px;">
                            <canvas id="monthlyChart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                        <div class="card-body p-4">
                            <h6 class="text-uppercase text-muted fw-bold mb-2">Yearly Sales</h6>
                            <h3 class="fw-bold mb-0">${{ number_format(array_sum($yearlyData), 2) }}</h3>
                            <div class="small text-muted mt-1">
                                Last year to date (through {{ \Carbon\Carbon::parse($salesSummary['year_to_date_last_year_label'])->format('m/d/Y') }}):
                                ${{ number_format($salesSummary['year_to_date_last_year'] ?? 0, 2) }}
                            </div>
                        </div>
                        <div class="px-4 pb-4" style="height: 100px;">
                            <canvas id="yearlyChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4 text-center">
                    <p class="fs-5 text-dark mb-4">Quick Links</p>
                    <div class="d-grid gap-3 d-sm-flex justify-content-sm-center">
                        <a href="{{ route('admin.businesses.index') }}" class="btn btn-primary btn-lg px-4">
                            <i class="bi bi-briefcase me-2"></i>Manage Businesses
                        </a>
                        <a href="{{ route('admin.customnames.index') }}" class="btn btn-outline-primary btn-lg px-4">
                            <i class="bi bi-layers me-2"></i>Custom Names
                        </a>
                        <a href="{{ route('admin.customcolors.index') }}" class="btn btn-outline-primary btn-lg px-4">
                            <i class="bi bi-palette me-2"></i>Custom Colors
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    @push('scripts')
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const chartOptions = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: true }
                },
                scales: {
                    x: { display: false },
                    y: { display: false }
                },
                elements: {
                    line: { tension: 0.4, borderWidth: 2, fill: true },
                    point: { radius: 0 }
                }
            };

            // Weekly Chart
            new Chart(document.getElementById('weeklyChart'), {
                type: 'line',
                data: {
                    labels: {!! json_encode(array_keys($weeklyData)) !!},
                    datasets: [{
                        data: {!! json_encode(array_values($weeklyData)) !!},
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13, 110, 253, 0.1)'
                    }]
                },
                options: chartOptions
            });

            // Monthly Chart
            new Chart(document.getElementById('monthlyChart'), {
                type: 'line',
                data: {
                    labels: {!! json_encode(array_keys($monthlyData)) !!},
                    datasets: [{
                        data: {!! json_encode(array_values($monthlyData)) !!},
                        borderColor: '#198754',
                        backgroundColor: 'rgba(25, 135, 84, 0.1)'
                    }]
                },
                options: chartOptions
            });

            // Yearly Chart
            new Chart(document.getElementById('yearlyChart'), {
                type: 'line',
                data: {
                    labels: {!! json_encode(array_keys($yearlyData)) !!},
                    datasets: [{
                        data: {!! json_encode(array_values($yearlyData)) !!},
                        borderColor: '#6f42c1',
                        backgroundColor: 'rgba(111, 66, 193, 0.1)'
                    }]
                },
                options: chartOptions
            });
        });
    </script>
    @endpush
</x-app-layout>
