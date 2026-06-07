<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Pay QuickBooks Invoices') }}
        </h2>
    </x-slot>

    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-lg-6">
                <div class="card border-0 shadow-sm rounded-4">
                    <div class="card-header bg-white py-4 border-bottom-0 text-center">
                        <h4 class="fw-bold mb-1">Secure Payment</h4>
                        <p class="text-muted small">Powered by Stripe</p>
                    </div>
                    <div class="card-body px-5 pb-5">
                        <div class="mb-4 p-3 bg-light rounded-3">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="text-muted">Payment for:</span>
                                <span class="fw-bold">{{ count($invoices) }} Invoice(s)</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <span class="h5 mb-0 fw-bold">Total Amount</span>
                                <span class="h4 mb-0 fw-bold text-primary">${{ number_format($total, 2) }}</span>
                            </div>
                        </div>

                        <form id="payment-form">
                            <div id="payment-element" class="mb-4">
                                <!-- Stripe.js injects the Payment Element here -->
                            </div>
                            <div id="payment-message" class="alert alert-danger d-none rounded-3 small"></div>

                            <button id="submit" class="btn btn-primary w-100 py-3 fw-bold text-uppercase shadow-sm">
                                <span id="button-text">Pay Now</span>
                                <div class="spinner-border spinner-border-sm d-none" id="spinner" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                            </button>
                        </form>
                    </div>
                </div>

                <div class="text-center mt-4">
                    <p class="small text-muted">
                        <i class="bi bi-shield-lock-fill me-1"></i> Your payment information is processed securely. We do not store your credit card details.
                    </p>
                    <a href="{{ route('account') }}" class="btn btn-link text-decoration-none fw-bold text-secondary">
                        <i class="bi bi-arrow-left me-1"></i> Return to My Account
                    </a>
                </div>
            </div>
        </div>
    </div>

    @push('scripts')
    <script src="https://js.stripe.com/v3/"></script>
    <script>
        const stripe = Stripe("{{ $stripe_publishable_key }}");
        const clientSecret = "{{ $client_secret }}";

        const elements = stripe.elements({ clientSecret });
        const paymentElement = elements.create("payment");
        paymentElement.mount("#payment-element");

        const form = document.getElementById("payment-form");
        const submitBtn = document.getElementById("submit");
        const spinner = document.getElementById("spinner");
        const buttonText = document.getElementById("button-text");
        const messageContainer = document.getElementById("payment-message");

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            setLoading(true);

            const { error } = await stripe.confirmPayment({
                elements,
                confirmParams: {
                    return_url: "{{ route('qbo.pay.complete') }}",
                },
            });

            if (error.type === "card_error" || error.type === "validation_error") {
                showMessage(error.message);
            } else {
                showMessage("An unexpected error occurred.");
            }

            setLoading(false);
        });

        function showMessage(messageText) {
            messageContainer.classList.remove("d-none");
            messageContainer.textContent = messageText;

            setTimeout(function () {
                messageContainer.classList.add("d-none");
                messageContainer.textContent = "";
            }, 4000);
        }

        function setLoading(isLoading) {
            if (isLoading) {
                submitBtn.disabled = true;
                spinner.classList.remove("d-none");
                buttonText.classList.add("d-none");
            } else {
                submitBtn.disabled = false;
                spinner.classList.add("d-none");
                buttonText.classList.remove("d-none");
            }
        }
    </script>
    @endpush
</x-app-layout>
