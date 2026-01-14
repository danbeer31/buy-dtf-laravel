<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('About Us') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="text-center mb-5">
                <h1 class="display-4 text-primary fw-bold">{{ $aboutInfo['title'] }}</h1>
                <p class="fs-4 text-muted">{{ $aboutInfo['headline'] }}</p>
            </div>

            <div class="row mb-5">
                <div class="col-md-8 mx-auto text-center">
                    <p class="fs-5 text-dark">{{ $aboutInfo['description'] }}</p>
                </div>
            </div>

            <div class="row text-center mb-5">
                @foreach ($aboutInfo['values'] as $value)
                    <div class="col-md-4 mb-4">
                        <div class="card h-100 border-0 shadow-sm rounded-4 p-4">
                            <h5 class="card-title text-primary fw-bold mb-3">{{ $value['title'] }}</h5>
                            <p class="card-text text-muted">{{ $value['description'] }}</p>
                        </div>
                    </div>
                @endforeach
            </div>

            <div class="text-center mb-5">
                <div class="col-md-8 mx-auto">
                    <p class="fs-5 fw-medium">{{ $aboutInfo['closing'] }}</p>
                </div>
            </div>

            <div class="text-center mt-5">
                <a href="{{ route('contact') }}" class="btn btn-primary btn-lg px-5 rounded-pill shadow">
                    <i class="bi bi-envelope me-2"></i> Contact Us
                </a>
            </div>
        </div>
    </div>
</x-app-layout>
