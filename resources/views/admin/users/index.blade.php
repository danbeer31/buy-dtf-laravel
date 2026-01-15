<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Manage Users') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="fw-bold mb-0">Users</h3>
                <a href="{{ route('admin.users.create') }}" class="btn btn-primary fw-bold">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-lg me-2" viewBox="0 0 16 16">
                        <path fill-rule="evenodd" d="M8 2a.5.5 0 0 1 .5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5A.5.5 0 0 1 8 2Z"/>
                    </svg>
                    Create New User
                </a>
            </div>

            @if(session('success'))
                <div class="alert alert-success border-0 shadow-sm rounded-4 mb-4">
                    {{ session('success') }}
                </div>
            @endif

            @if(session('error'))
                <div class="alert alert-danger border-0 shadow-sm rounded-4 mb-4">
                    {{ session('error') }}
                </div>
            @endif

            <!-- Search and Filter -->
            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-body p-4">
                    <form method="GET" action="{{ route('admin.users.index') }}" class="row g-3 align-items-end">
                        <div class="col-md-5">
                            <label for="search" class="form-label small fw-bold text-uppercase">Search</label>
                            <input type="text" name="search" id="search" class="form-control" placeholder="Name or email..." value="{{ request('search') }}">
                        </div>
                        <div class="col-md-4">
                            <label for="role" class="form-label small fw-bold text-uppercase">Role</label>
                            <select name="role" id="role" class="form-select">
                                <option value="">All Roles</option>
                                <option value="user" {{ request('role') == 'user' ? 'selected' : '' }}>User</option>
                                <option value="admin" {{ request('role') == 'admin' ? 'selected' : '' }}>Admin</option>
                                <option value="superadmin" {{ request('role') == 'superadmin' ? 'selected' : '' }}>Superadmin</option>
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

            <!-- Users Table -->
            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle mb-0">
                            <thead class="bg-light">
                                <tr>
                                    <th class="ps-4 py-3 text-uppercase small fw-bold">Name</th>
                                    <th class="py-3 text-uppercase small fw-bold">Email</th>
                                    <th class="py-3 text-uppercase small fw-bold">Role</th>
                                    <th class="py-3 text-uppercase small fw-bold">Created At</th>
                                    <th class="py-3 text-uppercase small fw-bold text-end pe-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                @forelse($users as $user)
                                    <tr>
                                        <td class="ps-4 py-3 fw-bold">{{ $user->name }}</td>
                                        <td class="py-3">
                                            <a href="mailto:{{ $user->email }}" class="text-decoration-none">{{ $user->email }}</a>
                                        </td>
                                        <td class="py-3">
                                            @php
                                                $badgeClass = match($user->role) {
                                                    'superadmin' => 'bg-danger-subtle text-danger border-danger-subtle',
                                                    'admin' => 'bg-primary-subtle text-primary border-primary-subtle',
                                                    default => 'bg-light text-dark'
                                                };
                                            @endphp
                                            <span class="badge border {{ $badgeClass }} text-uppercase px-2 py-1">
                                                {{ $user->role }}
                                            </span>
                                        </td>
                                        <td class="py-3 text-muted small">
                                            {{ $user->created_at->format('M d, Y') }}
                                        </td>
                                        <td class="py-3 text-end pe-4">
                                            <div class="btn-group">
                                                <a href="{{ route('admin.users.edit', $user) }}" class="btn btn-sm btn-outline-primary fw-bold">
                                                    Edit
                                                </a>
                                                @if($user->id !== auth()->id())
                                                    <form action="{{ route('admin.users.destroy', $user) }}" method="POST" class="d-inline" onsubmit="return confirm('Are you sure you want to delete this user?');">
                                                        @csrf
                                                        @method('DELETE')
                                                        <button type="submit" class="btn btn-sm btn-outline-danger fw-bold">
                                                            Delete
                                                        </button>
                                                    </form>
                                                @endif
                                            </div>
                                        </td>
                                    </tr>
                                @empty
                                    <tr>
                                        <td colspan="5" class="text-center py-5 text-muted">
                                            No users found matching your criteria.
                                        </td>
                                    </tr>
                                @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
                @if($users->hasPages())
                    <div class="card-footer bg-white border-top-0 p-4">
                        {{ $users->links() }}
                    </div>
                @endif
            </div>
        </div>
    </div>
</x-app-layout>
