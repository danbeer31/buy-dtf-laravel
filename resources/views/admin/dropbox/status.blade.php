<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
            {{ __('Dropbox Connection Status') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
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

            <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                <div class="card-header bg-white py-3 px-4 border-bottom-0">
                    <h5 class="fw-bold mb-0">Connection Status</h5>
                </div>
                <div class="card-body p-4">
                    @if($status['connected'])
                        <div class="alert alert-success d-flex align-items-center rounded-3">
                            <i class="bi bi-check-circle-fill me-2 fs-4"></i>
                            <div>{{ $status['message'] }}</div>
                        </div>

                        <div class="row mt-4 g-4">
                            <div class="col-md-6">
                                <div class="p-3 bg-light rounded-3">
                                    <label class="small text-muted text-uppercase fw-bold d-block mb-1">Access Token Expires In</label>
                                    <p class="mb-0 fw-bold">{{ $status['access_token_expires_in'] }} seconds</p>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="p-3 bg-light rounded-3">
                                    <label class="small text-muted text-uppercase fw-bold d-block mb-1">Last Updated At</label>
                                    <p class="mb-0 fw-bold">{{ $status['updated_at'] }}</p>
                                </div>
                            </div>
                            <div class="col-12">
                                <div class="p-3 bg-light rounded-3">
                                    <label class="small text-muted text-uppercase fw-bold d-block mb-1">Refresh Token</label>
                                    <p class="mb-0 text-break font-monospace small">{{ $status['refresh_token'] }}</p>
                                </div>
                            </div>
                        </div>

                        <div class="text-center mt-5">
                            <a href="{{ route('admin.dropbox.connect') }}" class="btn btn-primary btn-lg px-5 rounded-3 fw-bold shadow-sm">
                                <i class="bi bi-arrow-repeat me-2"></i> Re-connect to Dropbox
                            </a>
                            <a href="{{ route('admin.dropbox.refresh') }}" class="btn btn-warning btn-lg px-5 rounded-3 fw-bold shadow-sm ms-2">
                                <i class="bi bi-arrow-clockwise me-2"></i> Refresh Now
                            </a>
                        </div>
                    @else
                        <div class="alert alert-danger d-flex align-items-center rounded-3">
                            <i class="bi bi-exclamation-triangle-fill me-2 fs-4"></i>
                            <div>{{ $status['message'] }}</div>
                        </div>
                        <p class="text-muted mt-3">No valid tokens found or tokens have expired. Please connect your application to Dropbox to enable automated uploads.</p>

                        <div class="text-center mt-5">
                            <a href="{{ route('admin.dropbox.connect') }}" class="btn btn-primary btn-lg px-5 rounded-3 fw-bold shadow-sm">
                                <i class="bi bi-box-arrow-in-right me-2"></i> Connect to Dropbox
                            </a>
                        </div>
                    @endif
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
