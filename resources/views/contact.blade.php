<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Contact Us') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-10 col-lg-8">
                    <div class="card shadow-sm border-0 rounded-4 overflow-hidden">
                        <div class="row g-0">
                            <!-- Contact Info Sidebar -->
                            <div class="col-md-4 bg-dark text-white p-4 p-lg-5">
                                <h3 class="fw-bold mb-4 font-ubuntu">Get in Touch</h3>
                                <p class="text-light opacity-75 mb-5 small">
                                    Have questions about our DTF prints or need help with your order? Fill out the form and our team will get back to you as soon as possible.
                                </p>

                                <div class="d-flex align-items-start mb-4">
                                    <div class="text-warning me-3">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" class="bi bi-geo-alt-fill" viewBox="0 0 16 16">
                                            <path d="M8 16s6-5.686 6-10A6 6 0 0 0 2 6c0 4.314 6 10 6 10zm0-7a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"/>
                                        </svg>
                                    </div>
                                    <div>
                                        <h6 class="fw-bold mb-1">Headquarters</h6>
                                        <p class="small text-light opacity-75 mb-0">Next Level DTF</p>
                                    </div>
                                </div>

                                <div class="d-flex align-items-start mb-4">
                                    <div class="text-warning me-3">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" class="bi bi-envelope-fill" viewBox="0 0 16 16">
                                            <path d="M.05 3.555A2 2 0 0 1 2 2h12a2 2 0 0 1 1.95 1.555L8 8.414.05 3.555zM0 4.697v7.104l5.803-3.558L0 4.697zM6.761 8.83l-6.57 4.027A2 2 0 0 0 2 14h12a2 2 0 0 0 1.808-1.144l-6.57-4.027L8 9.586l-.239-.756zm3.436-.569L16 11.801V4.697l-5.803 3.564z"/>
                                        </svg>
                                    </div>
                                    <div>
                                        <h6 class="fw-bold mb-1">Email Us</h6>
                                        <p class="small text-light opacity-75 mb-0">support@nextleveldtf.com</p>
                                    </div>
                                </div>
                            </div>

                            <!-- Contact Form -->
                            <div class="col-md-8 bg-white p-4 p-lg-5">
                                @if (session('success'))
                                    <div class="alert alert-success alert-dismissible fade show mb-4 rounded-3 border-0 shadow-sm" role="alert">
                                        <div class="d-flex align-items-center">
                                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="currentColor" class="bi bi-check-circle-fill me-2" viewBox="0 0 16 16">
                                                <path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/>
                                            </svg>
                                            <strong>{{ session('success') }}</strong>
                                        </div>
                                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                                    </div>
                                @endif

                                <form action="{{ route('contact.store') }}" method="POST" class="needs-validation">
                                    @csrf

                                    <div class="mb-4">
                                        <label for="name" class="form-label fw-semibold text-dark small text-uppercase tracking-wider">{{ __('Name') }}</label>
                                        <input type="text" id="name" name="name" class="form-control form-control-lg bg-light border-0 @error('name') is-invalid @enderror" value="{{ old('name') }}" required autofocus placeholder="Your Full Name">
                                        @error('name')
                                            <div class="invalid-feedback">{{ $message }}</div>
                                        @enderror
                                    </div>

                                    <div class="mb-4">
                                        <label for="email" class="form-label fw-semibold text-dark small text-uppercase tracking-wider">{{ __('Email Address') }}</label>
                                        <input type="email" id="email" name="email" class="form-control form-control-lg bg-light border-0 @error('email') is-invalid @enderror" value="{{ old('email') }}" required placeholder="email@example.com">
                                        @error('email')
                                            <div class="invalid-feedback">{{ $message }}</div>
                                        @enderror
                                    </div>

                                    <div class="mb-4">
                                        <label for="subject" class="form-label fw-semibold text-dark small text-uppercase tracking-wider">{{ __('Subject') }}</label>
                                        <input type="text" id="subject" name="subject" class="form-control form-control-lg bg-light border-0 @error('subject') is-invalid @enderror" value="{{ old('subject') }}" required placeholder="How can we help?">
                                        @error('subject')
                                            <div class="invalid-feedback">{{ $message }}</div>
                                        @enderror
                                    </div>

                                    <div class="mb-4">
                                        <label for="message" class="form-label fw-semibold text-dark small text-uppercase tracking-wider">{{ __('Message') }}</label>
                                        <textarea id="message" name="message" rows="5" class="form-control form-control-lg bg-light border-0 @error('message') is-invalid @enderror" required placeholder="Tell us more about your request...">{{ old('message') }}</textarea>
                                        @error('message')
                                            <div class="invalid-feedback">{{ $message }}</div>
                                        @enderror
                                    </div>

                                    <div class="d-grid mt-5">
                                        <button type="submit" class="btn btn-warning btn-lg fw-bold text-uppercase tracking-wider py-3 shadow-sm hover-lift">
                                            {{ __('Send Message') }}
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</x-app-layout>
