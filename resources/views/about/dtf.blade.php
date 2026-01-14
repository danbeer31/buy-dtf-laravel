<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('About Our DTF Printing Services') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <h1 class="text-center text-primary fw-bold mb-4">Welcome to Our DTF Printing Services</h1>
            <p class="text-muted text-center fs-5 mb-5">
                Discover the best in Direct-to-Film (DTF) printing with unmatched quality, speed, and affordability.
            </p>

            <!-- Features Section -->
            <div class="row text-center my-5">
                @foreach ($features as $feature)
                    <div class="col-md-4 mb-4">
                        <div class="card h-100 border-0 shadow-sm rounded-4 p-4">
                            <i class="{{ $feature['icon'] }} fs-1 text-primary mb-3"></i>
                            <h4 class="fw-bold">{{ $feature['title'] }}</h4>
                            <p class="text-muted">{{ $feature['description'] }}</p>
                        </div>
                    </div>
                @endforeach
            </div>

            <!-- How to Order Section -->
            <h2 class="text-center text-primary fw-bold my-5">How to Get Started</h2>
            <div class="row">
                @foreach ($how_to as $step)
                    <div class="col-md-3 text-center mb-4">
                        <div class="step-circle text-white bg-primary d-inline-block mb-3 shadow-sm">
                            <span class="fs-3">{{ $step['step'] }}</span>
                        </div>
                        <h5 class="fw-bold">{{ $step['title'] }}</h5>
                        <p class="text-muted small">{{ $step['description'] }}</p>
                    </div>
                @endforeach
            </div>
        </div>
    </div>

    <style>
        .step-circle {
            width: 60px;
            height: 60px;
            line-height: 60px;
            border-radius: 50%;
            font-weight: bold;
        }
    </style>
</x-app-layout>
