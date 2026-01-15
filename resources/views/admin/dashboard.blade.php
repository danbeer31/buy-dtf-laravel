<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Admin Dashboard') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="card shadow-sm border-0 rounded-4">
                <div class="card-body p-4 text-center">
                    <p class="fs-5 text-dark mb-4">You are logged in as admin.</p>
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
</x-app-layout>

