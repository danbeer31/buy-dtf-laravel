<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Custom Colors') }}
        </h2>
    </x-slot>

    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3 class="mb-0 fw-bold">Custom Colors</h3>
            @if($business)
                <a href="{{ route('admin.customcolors.create') }}" class="btn btn-primary px-4">
                    <i class="bi bi-plus-lg me-1"></i> Add Color
                </a>
            @endif
        </div>

        @if(session('success'))
            <div class="alert alert-success border-0 shadow-sm rounded-3 mb-4">
                {{ session('success') }}
            </div>
        @endif

        @if(session('error'))
            <div class="alert alert-danger border-0 shadow-sm rounded-3 mb-4">
                {{ session('error') }}
            </div>
        @endif

        <div class="card shadow-sm border-0 rounded-3 mb-4">
            <div class="card-header bg-white py-3">
                <h5 class="mb-0 fw-bold">Standard Colors (Global)</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="table-light">
                        <tr>
                            <th style="width:100px;">Swatch</th>
                            <th>Name</th>
                            <th>Hex</th>
                            <th class="text-center">Status</th>
                            <th class="text-end">Actions</th>
                        </tr>
                        </thead>
                        <tbody>
                        @foreach($global_colors as $c)
                            <tr>
                                <td>
                                    <div class="rounded shadow-sm border" style="width:48px;height:28px;background:{{ $c->hex }};"></div>
                                </td>
                                <td>
                                    <span class="fw-semibold">{{ $c->name }}</span>
                                    <span class="badge bg-secondary ms-2 small text-uppercase">Global</span>
                                </td>
                                <td><code>{{ $c->hex }}</code></td>
                                <td class="text-center">
                                    @if($c->active)
                                        <span class="badge bg-success-subtle text-success border border-success-subtle px-3">Active</span>
                                    @else
                                        <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle px-3">Inactive</span>
                                    @endif
                                </td>
                                <td class="text-end">
                                    <a href="{{ route('admin.customcolors.edit', $c->id) }}"
                                       class="btn btn-sm btn-outline-secondary px-3">View</a>
                                </td>
                            </tr>
                        @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        @if($business)
        <div class="card shadow-sm border-0 rounded-3">
            <div class="card-header bg-white py-3">
                <h5 class="mb-0 fw-bold">{{ $business->business_name ?? 'This Shop' }} Colors</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="table-light">
                        <tr>
                            <th style="width:100px;">Swatch</th>
                            <th>Name</th>
                            <th>Hex</th>
                            <th class="text-center">Status</th>
                            <th class="text-end">Actions</th>
                        </tr>
                        </thead>
                        <tbody>
                        @forelse($shop_colors as $c)
                            <tr>
                                <td>
                                    <div class="rounded shadow-sm border" style="width:48px;height:28px;background:{{ $c->hex }};"></div>
                                </td>
                                <td class="fw-semibold">{{ $c->name }}</td>
                                <td><code>{{ $c->hex }}</code></td>
                                <td class="text-center">
                                    @if($c->active)
                                        <span class="badge bg-success-subtle text-success border border-success-subtle px-3">Active</span>
                                    @else
                                        <span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle px-3">Inactive</span>
                                    @endif
                                </td>
                                <td class="text-end">
                                    <div class="btn-group">
                                        <a href="{{ route('admin.customcolors.edit', $c->id) }}"
                                           class="btn btn-sm btn-outline-primary px-3">Edit</a>
                                        <a href="{{ route('admin.customcolors.toggle', $c->id) }}"
                                           class="btn btn-sm {{ $c->active ? 'btn-outline-warning' : 'btn-outline-success' }} px-3"
                                           onclick="return confirm('Toggle active for this color?');">
                                            {{ $c->active ? 'Deactivate' : 'Activate' }}
                                        </a>
                                    </div>
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="5" class="text-center py-4 text-muted small">No custom colors defined for this shop.</td>
                            </tr>
                        @endforelse
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        @endif
    </div>
</x-app-layout>
