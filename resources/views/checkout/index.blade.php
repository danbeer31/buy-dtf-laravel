<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('Checkout') }}
        </h2>
    </x-slot>

    <div class="container py-5">
        <div class="row g-5">
            <!-- Order Summary -->
            <div class="col-lg-7">
                <!-- Shipping Address Form -->
                <div class="card border-0 shadow-sm rounded-4 mb-4">
                    <div class="card-header bg-white py-3 border-bottom-0">
                        <h4 class="fw-bold mb-0">Shipping Address</h4>
                    </div>
                    <div class="card-body">
                        <form id="shipping-address-form">
                            <div class="row g-3">
                                <div class="col-12">
                                    <label for="name" class="form-label">Full Name</label>
                                    <input type="text" class="form-control" id="name" name="name" value="{{ $order->shippingAddress->name ?? '' }}" required>
                                </div>
                                <div class="col-12">
                                    <label for="address1" class="form-label">Address</label>
                                    <input type="text" class="form-control" id="address1" name="address1" value="{{ $order->shippingAddress->address1 ?? '' }}" required>
                                </div>
                                <div class="col-12">
                                    <label for="address2" class="form-label">Address 2 (Optional)</label>
                                    <input type="text" class="form-control" id="address2" name="address2" value="{{ $order->shippingAddress->address2 ?? '' }}">
                                </div>
                                <div class="col-md-6">
                                    <label for="city" class="form-label">City</label>
                                    <input type="text" class="form-control" id="city" name="city" value="{{ $order->shippingAddress->city ?? '' }}" required>
                                </div>
                                <div class="col-md-3">
                                    <label for="state" class="form-label">State</label>
                                    <input type="text" class="form-control" id="state" name="state" value="{{ $order->shippingAddress->state ?? '' }}" placeholder="TX" maxlength="2" required>
                                </div>
                                <div class="col-md-3">
                                    <label for="zip" class="form-label">ZIP</label>
                                    <input type="text" class="form-control" id="zip" name="zip" value="{{ $order->shippingAddress->zip ?? '' }}" required>
                                </div>
                            </div>
                            <div class="mt-3">
                                <button type="submit" class="btn btn-secondary btn-sm" id="update-address-btn">Update Address & Rates</button>
                            </div>
                        </form>
                    </div>
                </div>

                <div class="card border-0 shadow-sm rounded-4 mb-4">
                    <div class="card-header bg-white py-3 border-bottom-0">
                        <h4 class="fw-bold mb-0">Order Summary</h4>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table align-middle">
                                <thead>
                                    <tr>
                                        <th>Image</th>
                                        <th>Dimensions</th>
                                        <th class="text-center">Qty</th>
                                        <th class="text-end">Price</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    @foreach($order->dtfImages as $item)
                                        <tr>
                                            <td>
                                                <img src="{{ $item->image }}" alt="{{ $item->image_name }}" class="rounded shadow-sm" style="width: 60px; height: 60px; object-fit: contain;">
                                                <div class="small fw-bold mt-1 text-truncate" style="max-width: 150px;">
                                                    {{ $item->image_name }}
                                                    @if($item->item_type === 'gang_sheet')
                                                        <span class="badge bg-dark-subtle text-dark border ms-1">Gang Sheet</span>
                                                    @endif
                                                </div>
                                            </td>
                                            <td>
                                                @if($item->item_type === 'gang_sheet')
                                                    {{ strtoupper(data_get($item->item_meta, 'size_key', $item->width . 'x' . $item->height)) }}
                                                @else
                                                    {{ $item->width }}" x {{ $item->height }}"
                                                @endif
                                            </td>
                                            <td class="text-center">{{ $item->quantity }}</td>
                                            <td class="text-end">${{ number_format($item->get_price() * $item->quantity, 2) }}</td>
                                        </tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Shipping Selection -->
                <div class="card border-0 shadow-sm rounded-4">
                    <div class="card-header bg-white py-3 border-bottom-0">
                        <h4 class="fw-bold mb-0">Shipping Method</h4>
                    </div>
                    <div class="card-body">
                        @php
                            $hasPickup = false;
                            foreach($rates as $r) {
                                if(($r['object_id'] ?? '') === 'pickup') {
                                    $hasPickup = true;
                                    break;
                                }
                            }
                            $showRates = !empty($rates);
                        @endphp

                        @if(!$showRates)
                            <div class="alert alert-info rounded-3 border-0">
                                <i class="bi bi-info-circle-fill me-2"></i>
                                @if(!$order->shippingAddress)
                                    Please <a href="{{ route('account') }}" class="fw-bold">set your shipping address</a> to see shipping rates.
                                @else
                                    Calculating shipping options... if this message persists, please contact support.
                                @endif
                            </div>
                        @elseif(!$hasPickup && empty(array_filter($rates, fn($r) => ($r['object_id'] ?? '') !== 'pickup')))
                             <div class="alert alert-warning rounded-3 border-0">
                                <i class="bi bi-exclamation-triangle-fill me-2"></i>
                                No shipping rates available. Please contact support.
                            </div>
                        @endif

                        @if($showRates)
                            <div class="list-group">
                                @foreach($rates as $rate)
                                    <label class="list-group-item d-flex justify-content-between align-items-center py-3 rounded-3 mb-2 border cursor-pointer hover-bg-light">
                                        <div class="d-flex align-items-center">
                                            <input class="form-check-input me-3 shipping-rate-input" type="radio" name="shipping_rate"
                                                   value="{{ $rate['object_id'] }}"
                                                   data-amount="{{ $rate['amount'] }}"
                                                   data-service-name="{{ $rate['servicelevel']['name'] }}"
                                                   {{ $loop->first ? 'checked' : '' }}>
                                            <div>
                                                <div class="fw-bold">
                                                    {{ $rate['servicelevel']['name'] }}
                                                    @if(!empty($rate['is_free']) || ($rate['object_id'] ?? '') === 'pickup')
                                                        <span class="badge bg-success ms-2">FREE</span>
                                                    @endif
                                                </div>
                                                <div class="small text-muted">{{ $rate['duration_terms'] ?? 'Estimated delivery' }}</div>
                                            </div>
                                        </div>
                                        <span class="fw-bold text-primary">
                                            @if(!empty($rate['is_free']) || (isset($rate['object_id']) && $rate['object_id'] === 'pickup'))
                                                $0.00
                                            @else
                                                ${{ number_format($rate['amount'], 2) }}
                                            @endif
                                        </span>
                                    </label>
                                @endforeach
                            </div>
                        @endif
                    </div>
                </div>
            </div>

            <!-- Payment & Totals -->
            <div class="col-lg-5">
                <div class="card border-0 shadow-sm rounded-4 sticky-top" style="top: 100px; z-index: 10;">
                    <div class="card-body p-4">
                        <h4 class="fw-bold mb-4">Final Totals</h4>

                        <div class="d-flex justify-content-between mb-2">
                            <span class="text-muted">Subtotal</span>
                            <span class="fw-bold">${{ number_format($order->price, 2) }}</span>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <span class="text-muted">Shipping</span>
                            <span class="fw-bold" id="display-shipping-cost">$0.00</span>
                        </div>
                        <div class="d-flex justify-content-between mb-3 pb-3 border-bottom">
                            <span class="text-muted">Tax</span>
                            <span class="fw-bold">$0.00</span>
                        </div>
                        <div class="d-flex justify-content-between mb-4">
                            <h5 class="fw-bold mb-0">Total</h5>
                            <h5 class="fw-bold mb-0 text-primary" id="display-total-price">${{ number_format($order->price, 2) }}</h5>
                        </div>

                        <hr class="my-4">

                        <h5 class="fw-bold mb-3">Payment Method</h5>
                        <div class="mb-4">
                            @php
                                $invoiceMethod = $paymentMethods->where('payment_controller', 'invoice')->first();
                                $cardMethod = $paymentMethods->where('payment_controller', 'cardpayment')->first();
                                $hasBoth = $invoiceMethod && $cardMethod;
                                $currentMethod = $order->paymentMethod;
                            @endphp

                            @if($hasBoth)
                                <!-- Both methods available: Show QB Invoice by default with option to switch to Card -->
                                <div id="payment-method-selection-wrapper">
                                    <div id="qb-invoice-display" style="{{ $currentMethod && $currentMethod->payment_controller === 'invoice' ? '' : 'display: none;' }}">
                                        <div class="d-flex justify-content-between align-items-center p-3 rounded-3 border bg-light mb-2">
                                            <div class="d-flex align-items-center">
                                                <i class="bi bi-receipt-cutoff fs-4 me-3 text-primary"></i>
                                                <div>
                                                    <div class="fw-bold text-success"><i class="bi bi-check-circle-fill me-1"></i> {{ $invoiceMethod->method_name }}</div>
                                                    <div class="small text-muted">Invoice will be sent to your email</div>
                                                </div>
                                            </div>
                                            <input type="hidden" name="payment_method_id" value="{{ $invoiceMethod->id }}" class="payment-method-radio" data-controller="invoice" {{ $currentMethod && $currentMethod->payment_controller === 'invoice' ? '' : 'disabled' }}>
                                        </div>
                                        <button type="button" id="switch-to-card" class="btn btn-link btn-sm text-decoration-none p-0 fw-bold">
                                            <i class="bi bi-credit-card me-1"></i> Pay by Credit Card instead
                                        </button>
                                    </div>

                                    <div id="card-payment-display" style="{{ $currentMethod && $currentMethod->payment_controller === 'cardpayment' ? '' : 'display: none;' }}">
                                        <div class="d-flex justify-content-between align-items-center p-3 rounded-3 border bg-light mb-2">
                                            <div class="d-flex align-items-center">
                                                <i class="bi bi-credit-card fs-4 me-3 text-primary"></i>
                                                <div>
                                                    <div class="fw-bold">{{ $cardMethod->method_name }}</div>
                                                    <div class="small text-muted">Secure payment via Stripe</div>
                                                </div>
                                            </div>
                                            <input type="hidden" name="payment_method_id" value="{{ $cardMethod->id }}" class="payment-method-radio" data-controller="cardpayment" {{ $currentMethod && $currentMethod->payment_controller === 'cardpayment' ? '' : 'disabled' }}>
                                        </div>
                                        <button type="button" id="switch-to-invoice" class="btn btn-link btn-sm text-decoration-none p-0 fw-bold">
                                            <i class="bi bi-receipt-cutoff me-1"></i> Switch back to Quickbooks Invoice (Default)
                                        </button>
                                    </div>
                                </div>
                            @else
                                <!-- Only one (or none) method available: Just show it -->
                                @foreach($paymentMethods as $pm)
                                    <div class="d-flex justify-content-between align-items-center p-3 rounded-3 border bg-light mb-2">
                                        <div class="d-flex align-items-center">
                                            @if($pm->payment_controller === 'cardpayment')
                                                <i class="bi bi-credit-card fs-4 me-3 text-primary"></i>
                                            @else
                                                <i class="bi bi-receipt-cutoff fs-4 me-3 text-primary"></i>
                                            @endif
                                            <div>
                                                <div class="fw-bold">{{ $pm->method_name }}</div>
                                                <div class="small text-muted">{{ $pm->description }}</div>
                                            </div>
                                        </div>
                                        <input type="hidden" name="payment_method_id" value="{{ $pm->id }}" class="payment-method-radio" data-controller="{{ $pm->payment_controller }}">
                                    </div>
                                @endforeach
                            @endif
                        </div>

                        <div id="stripe-payment-details" style="{{ $order->paymentMethod && $order->paymentMethod->payment_controller === 'cardpayment' ? '' : 'display: none;' }}">
                            <h5 class="fw-bold mb-3">Card Details</h5>
                            <form id="payment-form">
                                <div id="payment-element" class="mb-4">
                                    <!-- Stripe Elements will be inserted here -->
                                    <div id="stripe-loading" class="text-center py-3">
                                        <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
                                        <span class="ms-2 small text-muted">Loading card fields...</span>
                                    </div>
                                    <div id="card-number-element" class="form-control bg-light border-0 mb-3 py-3" style="display: none;"></div>
                                    <div class="row g-3" id="card-details-row" style="display: none;">
                                        <div class="col-6">
                                            <div id="card-expiry-element" class="form-control bg-light border-0 py-3"></div>
                                        </div>
                                        <div class="col-6">
                                            <div id="card-cvc-element" class="form-control bg-light border-0 py-3"></div>
                                        </div>
                                    </div>
                                </div>
                                <div id="card-errors" class="text-danger small mb-3" role="alert"></div>
                            </form>
                        </div>

                        <div id="invoice-payment-details" style="{{ $order->paymentMethod && $order->paymentMethod->payment_controller === 'invoice' ? '' : 'display: none;' }}">
                            <div class="alert alert-info py-2 small">
                                An invoice will be sent to your email after placing the order.
                            </div>
                        </div>

                        <button id="submit-button" class="btn btn-primary btn-lg w-100 fw-bold py-3 rounded-3 shadow-sm text-uppercase tracking-wider" {{ empty($rates) ? 'disabled' : '' }}>
                                <span id="button-text">Place Order</span>
                                <div class="spinner-border spinner-border-sm d-none" id="spinner" role="status"></div>
                            </button>

                        <div class="text-center mt-3">
                            <img src="https://help.shopify.com/showcase/customer-payment-methods.png" alt="Payment Methods" class="img-fluid" style="max-height: 25px; opacity: 0.6;">
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    @push('scripts')
    <script src="https://js.stripe.com/v3/"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const subtotal = {{ $order->price }};
            const shippingInputs = document.querySelectorAll('.shipping-rate-input');
            const displayShipping = document.getElementById('display-shipping-cost');
            const displayTotal = document.getElementById('display-total-price');

            const stripeDetails = document.getElementById('stripe-payment-details');
            const invoiceDetails = document.getElementById('invoice-payment-details');

            const shippingAddressForm = document.getElementById('shipping-address-form');
            const updateAddressBtn = document.getElementById('update-address-btn');

            function updateTotals() {
                const checked = document.querySelector('.shipping-rate-input:checked');
                if (checked) {
                    const shipping = parseFloat(checked.dataset.amount);
                    displayShipping.textContent = '$' + shipping.toFixed(2);
                    displayTotal.textContent = '$' + (subtotal + shipping).toFixed(2);
                }
            }

            shippingInputs.forEach(input => input.addEventListener('change', updateTotals));
            updateTotals();

            // Handle payment method switching
            const switchToCardBtn = document.getElementById('switch-to-card');
            const switchToInvoiceBtn = document.getElementById('switch-to-invoice');
            const qbInvoiceDisplay = document.getElementById('qb-invoice-display');
            const cardPaymentDisplay = document.getElementById('card-payment-display');

            if (switchToCardBtn) {
                switchToCardBtn.addEventListener('click', function() {
                    qbInvoiceDisplay.style.display = 'none';
                    cardPaymentDisplay.style.display = 'block';
                    stripeDetails.style.display = 'block';
                    invoiceDetails.style.display = 'none';

                    // Update hidden inputs
                    qbInvoiceDisplay.querySelector('input').disabled = true;
                    cardPaymentDisplay.querySelector('input').disabled = false;
                });
            }

            if (switchToInvoiceBtn) {
                switchToInvoiceBtn.addEventListener('click', function() {
                    qbInvoiceDisplay.style.display = 'block';
                    cardPaymentDisplay.style.display = 'none';
                    stripeDetails.style.display = 'none';
                    invoiceDetails.style.display = 'block';

                    // Update hidden inputs
                    qbInvoiceDisplay.querySelector('input').disabled = false;
                    cardPaymentDisplay.querySelector('input').disabled = true;
                });
            }

            const paymentMethodRadios = document.querySelectorAll('.payment-method-radio');

            // Initial setup for payment method details visibility (for non-switched case)
            function updatePaymentDetailsVisibility() {
                const activeRadio = document.querySelector('.payment-method-radio:not([disabled])');
                if (activeRadio) {
                    const controller = activeRadio.dataset.controller;
                    if (controller === 'cardpayment') {
                        stripeDetails.style.display = 'block';
                        invoiceDetails.style.display = 'none';
                    } else if (controller === 'invoice') {
                        stripeDetails.style.display = 'none';
                        invoiceDetails.style.display = 'block';
                    }
                }
            }
            updatePaymentDetailsVisibility();

            // Handle shipping address update
            shippingAddressForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                updateAddressBtn.disabled = true;
                updateAddressBtn.textContent = 'Updating...';

                const formData = new FormData(shippingAddressForm);
                const data = Object.fromEntries(formData.entries());

                try {
                    const response = await fetch("{{ route('checkout.shipping-address.update') }}", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRF-TOKEN": "{{ csrf_token() }}"
                        },
                        body: JSON.stringify(data)
                    });

                    if (response.ok) {
                        window.location.reload();
                    } else {
                        alert('Failed to update address. Please check your input.');
                        updateAddressBtn.disabled = false;
                        updateAddressBtn.textContent = 'Update Address & Rates';
                    }
                } catch (err) {
                    console.error(err);
                    alert('An error occurred.');
                    updateAddressBtn.disabled = false;
                    updateAddressBtn.textContent = 'Update Address & Rates';
                }
            });

            // Stripe logic
            let stripe, elements, cardNumber, cardExpiry, cardCvc;

            const style = {
                base: {
                    fontSize: '16px',
                    color: '#32325d',
                    fontFamily: '"Blinker", sans-serif',
                    '::placeholder': {
                        color: '#aab7c4'
                    }
                },
                invalid: {
                    color: '#fa755a',
                    iconColor: '#fa755a'
                }
            };

            // We need to fetch the key first or just use the one from config if we want it hardcoded in JS
            // But let's fetch it via the payment start call as intended.

            const stripeKey = "{{ config('services.stripe.key') }}";
            stripe = Stripe(stripeKey);
            elements = stripe.elements();

            cardNumber = elements.create('cardNumber', {style: style});
            cardExpiry = elements.create('cardExpiry', {style: style});
            cardCvc = elements.create('cardCvc', {style: style});

            cardNumber.mount('#card-number-element');
            cardExpiry.mount('#card-expiry-element');
            cardCvc.mount('#card-cvc-element');

            cardNumber.on('ready', function() {
                document.getElementById('stripe-loading').style.display = 'none';
                document.getElementById('card-number-element').style.display = 'block';
                document.getElementById('card-details-row').style.display = 'flex';
            });

            const form = document.getElementById('payment-form');
            const submitButton = document.getElementById('submit-button');
            const spinner = document.getElementById('spinner');
            const buttonText = document.getElementById('button-text');

            submitButton.addEventListener('click', async (e) => {
                const selectedShipping = document.querySelector('.shipping-rate-input:checked');
                const selectedPaymentMethod = document.querySelector('.payment-method-radio:not([disabled])');

                if (!selectedShipping) {
                    alert('Please select a shipping method.');
                    return;
                }

                if (!selectedPaymentMethod) {
                    alert('Please select a payment method.');
                    return;
                }

                // If it's an invoice, we could potentially just submit a hidden form to avoid AJAX
                // But let's stick with AJAX for now but make it more robust.
                await handleCheckout();
            });

            async function handleCheckout() {
                const selectedShipping = document.querySelector('.shipping-rate-input:checked');
                const selectedPaymentMethod = document.querySelector('.payment-method-radio:not([disabled])');

                if (!selectedShipping) {
                    alert('Please select a shipping method.');
                    return;
                }

                if (!selectedPaymentMethod) {
                    alert('Please select a payment method.');
                    return;
                }

                setLoading(true);

                try {
                    // 1. Get Payment Intent / Initialize Transaction
                    const response = await fetch("{{ route('checkout.payment') }}", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRF-TOKEN": "{{ csrf_token() }}"
                        },
                        body: JSON.stringify({
                            shipping_rate_id: selectedShipping.value,
                            shipping_cost: selectedShipping.dataset.amount,
                            shipping_service_name: selectedShipping.dataset.serviceName,
                            payment_method_id: selectedPaymentMethod.value
                        })
                    });

                    const data = await response.json().catch(async err => {
                        const text = await response.text();
                        console.error('Non-JSON response:', text);

                        // Check if it's a known error page or just general HTML
                        if (text.includes('SQLSTATE') || text.includes('Connection timed out')) {
                            throw new Error('Database connection issue. Please wait a moment and try again.');
                        }

                        // If it's HTML, it might be a 500 error page
                        if (text.trim().startsWith('<!DOCTYPE') || text.trim().startsWith('<html')) {
                            throw new Error('Server error occurred (500). Please check if your session is still active or try again later.');
                        }

                        throw new Error('Server returned an unexpected response. Please try again.');
                    });
                    if (data.error) {
                        throw new Error(data.error);
                    }

                    if (data.requires_redirect) {
                        window.location.href = data.redirect_url;
                        return;
                    }

                    // 2. Confirm Payment if Stripe
                    if (selectedPaymentMethod.dataset.controller === 'cardpayment') {
                        const result = await stripe.confirmCardPayment(data.client_secret, {
                            payment_method: {
                                card: cardNumber,
                            }
                        });

                        if (result.error) {
                            document.getElementById('card-errors').textContent = result.error.message;
                            setLoading(false);
                        } else {
                            if (result.paymentIntent.status === 'succeeded') {
                                window.location.href = "{{ route('checkout.complete') }}?pi=" + result.paymentIntent.id;
                            }
                        }
                    } else {
                        // For other methods that didn't require redirect (though invoice probably should redirect to complete)
                        alert('Order placed successfully.');
                        window.location.href = "{{ route('checkout.complete') }}";
                    }
                } catch (err) {
                    console.error(err);
                    alert('An error occurred during checkout: ' + err.message);
                    setLoading(false);
                }
            }

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                await handleCheckout();
            });

            function setLoading(isLoading) {
                if (isLoading) {
                    submitButton.disabled = true;
                    spinner.classList.remove('d-none');
                    buttonText.classList.add('d-none');
                } else {
                    submitButton.disabled = false;
                    spinner.classList.add('d-none');
                    buttonText.classList.remove('d-none');
                }
            }
        });
    </script>
    @endpush
</x-app-layout>
