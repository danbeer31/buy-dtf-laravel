<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Edit User') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card shadow-sm border-0 rounded-4">
                        <div class="card-header bg-white border-bottom-0 pt-4 px-4">
                            <h4 class="fw-bold mb-0">User Information: {{ $user->name }}</h4>
                        </div>
                        <div class="card-body p-4">
                            <form method="POST" action="{{ route('admin.users.update', $user) }}">
                                @csrf
                                @method('PATCH')

                                <div class="mb-3">
                                    <label for="name" class="form-label small fw-bold text-uppercase">Name</label>
                                    <input type="text" name="name" id="name" class="form-control @error('name') is-invalid @enderror" value="{{ old('name', $user->name) }}" required>
                                    @error('name')
                                        <div class="invalid-feedback">{{ $message }}</div>
                                    @enderror
                                </div>

                                <div class="mb-3">
                                    <label for="email" class="form-label small fw-bold text-uppercase">Email</label>
                                    <input type="email" name="email" id="email" class="form-control @error('email') is-invalid @enderror" value="{{ old('email', $user->email) }}" required>
                                    @error('email')
                                        <div class="invalid-feedback">{{ $message }}</div>
                                    @enderror
                                </div>

                                <div class="mb-3">
                                    <label for="role" class="form-label small fw-bold text-uppercase">Role</label>
                                    <select name="role" id="role" class="form-select @error('role') is-invalid @enderror" required>
                                        <option value="user" {{ old('role', $user->role) == 'user' ? 'selected' : '' }}>User</option>
                                        <option value="admin" {{ old('role', $user->role) == 'admin' ? 'selected' : '' }}>Admin</option>
                                        <option value="superadmin" {{ old('role', $user->role) == 'superadmin' ? 'selected' : '' }}>Superadmin</option>
                                    </select>
                                    @error('role')
                                        <div class="invalid-feedback">{{ $message }}</div>
                                    @enderror
                                </div>

                                <hr class="my-4">
                                <h5 class="fw-bold mb-3">Change Password</h5>
                                <p class="text-muted small mb-3">Leave blank if you don't want to change the password.</p>

                                <div class="mb-3">
                                    <label for="password" class="form-label small fw-bold text-uppercase">New Password</label>
                                    <input type="password" name="password" id="password" class="form-control @error('password') is-invalid @enderror">
                                    @error('password')
                                        <div class="invalid-feedback">{{ $message }}</div>
                                    @enderror
                                </div>

                                <div class="mb-4">
                                    <label for="password_confirmation" class="form-label small fw-bold text-uppercase">Confirm New Password</label>
                                    <input type="password" name="password_confirmation" id="password_confirmation" class="form-control">
                                </div>

                                <div class="d-flex justify-content-between">
                                    <a href="{{ route('admin.users.index') }}" class="btn btn-outline-secondary px-4 fw-bold">Cancel</a>
                                    <button type="submit" class="btn btn-primary px-4 fw-bold">Update User</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
