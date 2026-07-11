<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Shipping Settings') }}
        </h2>
    </x-slot>

    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h3 class="mb-0 fw-bold">Shipping Settings</h3>
        </div>

        @if(session('success'))
            <div class="alert alert-success border-0 shadow-sm rounded-3 mb-4">
                {{ session('success') }}
            </div>
        @endif

        @if($errors->any())
            <div class="alert alert-danger border-0 shadow-sm rounded-3 mb-4">
                <ul class="mb-0">
                    @foreach($errors->all() as $error)
                        <li>{{ $error }}</li>
                    @endforeach
                </ul>
            </div>
        @endif

        <form action="{{ route('admin.shipping.update') }}" method="POST">
            @csrf
            <div class="row">
                <div class="col-lg-8">
                    <!-- Allowed UPS Services -->
                    <div class="card shadow-sm border-0 rounded-3 mb-4">
                        <div class="card-header bg-white py-3">
                            <h5 class="mb-0 fw-bold">Allowed UPS Services</h5>
                            <p class="text-muted small mb-0">Select which UPS shipping options will be shown to customers.</p>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                @foreach($ups_services as $token => $name)
                                    <div class="col-md-6 mb-2">
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" name="allowed_services[]" value="{{ $token }}" id="service-{{ $token }}" {{ in_array($token, $allowed_services) ? 'checked' : '' }}>
                                            <label class="form-check-label" for="service-{{ $token }}">
                                                {{ $name }} <br><small class="text-muted">{{ $token }}</small>
                                            </label>
                                        </div>
                                    </div>
                                @endforeach
                            </div>
                        </div>
                    </div>

                    <!-- Free Shipping Configuration -->
                    <div class="card shadow-sm border-0 rounded-3 mb-4">
                        <div class="card-header bg-white py-3">
                            <h5 class="mb-0 fw-bold">Free Shipping Configuration</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-4">
                                <label for="free_shipping_threshold" class="form-label fw-bold">Free Shipping Threshold ($)</label>
                                <div class="input-group" style="max-width: 250px;">
                                    <span class="input-group-text">$</span>
                                    <input type="number" step="0.01" class="form-control" id="free_shipping_threshold" name="free_shipping_threshold" value="{{ $free_shipping_threshold }}">
                                </div>
                                <div class="form-text">Orders equal to or above this amount will qualify for free shipping on selected services. Set to a very high number to effectively disable.</div>
                            </div>

                            <hr class="my-4">

                            <h6 class="fw-bold mb-3">Services eligible for Free Shipping:</h6>
                            <div class="row">
                                @foreach($ups_services as $token => $name)
                                    <div class="col-md-6 mb-2">
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" name="free_shipping_services[]" value="{{ $token }}" id="free-service-{{ $token }}" {{ in_array($token, $free_shipping_services) ? 'checked' : '' }}>
                                            <label class="form-check-label" for="free-service-{{ $token }}">
                                                {{ $name }}
                                            </label>
                                        </div>
                                    </div>
                                @endforeach
                            </div>
                        </div>
                    </div>

                    <!-- Pickup Configuration -->
                    <div class="card shadow-sm border-0 rounded-3 mb-4">
                        <div class="card-header bg-white py-3">
                            <h5 class="mb-0 fw-bold">Local Pickup Configuration</h5>
                        </div>
                        <div class="card-body">
                            <div class="form-check form-switch mb-3">
                                <input class="form-check-input" type="checkbox" name="pickup_enabled" id="pickup_enabled" value="1" {{ $pickup_enabled == '1' ? 'checked' : '' }}>
                                <label class="form-check-label fw-bold" for="pickup_enabled">Enable Local Pickup</label>
                            </div>

                            <div class="mb-3">
                                <label for="pickup_message" class="form-label fw-bold">Pickup Message / Label</label>
                                <input type="text" class="form-control" id="pickup_message" name="pickup_message" value="{{ $pickup_message }}">
                                <div class="form-text">This label will be shown to customers as a shipping option.</div>
                            </div>
                        </div>
                    </div>

                    <div class="d-flex justify-content-end mb-5">
                        <button type="submit" class="btn btn-primary px-5 py-2 fw-bold shadow-sm">
                            Save Settings
                        </button>
                    </div>
                </div>

                <div class="col-lg-4">
                    <div class="card shadow-sm border-0 rounded-3 bg-light">
                        <div class="card-body">
                            <h5 class="fw-bold mb-3">Help & Info</h5>
                            <p class="small">
                                <strong>Allowed Services:</strong> These are the shipping options retrieved from Shippo that will be presented to the customer. If a service is returned by Shippo but not checked here, it will be hidden.
                            </p>
                            <p class="small">
                                <strong>Free Shipping:</strong> When the order subtotal reaches the threshold, the selected services will have their cost set to $0.00.
                            </p>
                            <p class="small">
                                <strong>Note:</strong> "Pickup" is always available and free by default, and is not affected by these settings.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </form>
    </div>
</x-app-layout>
