<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Manage Businesses') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Search and Filter -->
            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <form method="GET" action="{{ route('admin.businesses.index') }}" class="row g-3 align-items-end">
                        <div class="col-md-5">
                            <label for="search" class="form-label small fw-bold text-uppercase">Search</label>
                            <input type="text" name="search" id="search" class="form-control" placeholder="Name, contact, or email..." value="{{ request('search') }}">
                        </div>
                        <div class="col-md-4">
                            <label for="filter_status" class="form-label small fw-bold text-uppercase">Status</label>
                            <select name="filter_status" id="filter_status" class="form-select">
                                <option value="">All Statuses</option>
                                <option value="unconfirmed" {{ request('filter_status') == 'unconfirmed' ? 'selected' : '' }}>Unconfirmed</option>
                                <option value="confirmed" {{ request('filter_status') == 'confirmed' ? 'selected' : '' }}>Confirmed</option>
                                <option value="closed" {{ request('filter_status') == 'closed' ? 'selected' : '' }}>Closed</option>
                                <option value="cancelled" {{ request('filter_status') == 'cancelled' ? 'selected' : '' }}>Cancelled</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <button type="submit" class="btn btn-primary w-100 fw-bold">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-search me-2" viewBox="0 0 16 16">
                                    <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z"/>
                                </svg>
                                Filter Results
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Businesses Table -->
            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0">
                            <thead class="bg-light">
                                <tr>
                                    <th class="ps-4 py-3 text-uppercase small fw-bold">Business Name</th>
                                    <th class="py-3 text-uppercase small fw-bold">Contact</th>
                                    <th class="py-3 text-uppercase small fw-bold">Email</th>
                                    <th class="py-3 text-uppercase small fw-bold">Status</th>
                                    <th class="py-3 text-uppercase small fw-bold text-end pe-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($businesses as $business)
                                    <tr>
                                        <td class="ps-4 py-3 fw-bold">{{ $business->business_name }}</td>
                                        <td class="py-3">{{ $business->contact_name }}</td>
                                        <td class="py-3">
                                            <a href="mailto:{{ $business->email }}" class="text-decoration-none">{{ $business->email }}</a>
                                        </td>
                                        <td class="py-3">
                                            @php
                                                $badgeClass = match($business->status) {
                                                    'confirmed' => 'bg-success-subtle text-success border-success-subtle',
                                                    'unconfirmed' => 'bg-warning-subtle text-warning-emphasis border-warning-subtle',
                                                    'closed' => 'bg-secondary-subtle text-secondary-emphasis border-secondary-subtle',
                                                    'cancelled' => 'bg-danger-subtle text-danger border-danger-subtle',
                                                    default => 'bg-light text-dark'
                                                };
                                            @endphp
                                            <span class="badge border {{ $badgeClass }} text-uppercase px-2 py-1">
                                                {{ $business->status }}
                                            </span>
                                        </td>
                                        <td class="py-3 text-end pe-4">
                                            <a href="{{ route('admin.businesses.show', $business) }}" class="btn btn-sm btn-outline-primary fw-bold">
                                                View Details
                                            </a>
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="5" class="text-center py-5 text-muted">
                                            No businesses found matching your criteria.
                                        </td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
                @if($businesses->hasPages())
                    <div class="card-footer bg-white border-top-0 p-4">
                        {{ $businesses->links() }}
                    </div>
                @endif
            </div>
        </div>
    </div>
</x-app-layout>
