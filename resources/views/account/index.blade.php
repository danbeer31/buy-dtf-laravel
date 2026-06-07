<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0">
            {{ __('My Account') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <!-- Business Information -->
            <div class="card shadow-sm border-0 rounded-4 mb-4">
                <div class="card-header bg-white border-0 py-3 d-flex justify-content-between align-items-center">
                    <h5 class="mb-0 fw-bold">Business Information</h5>
                    <a href="{{ route('profile.edit') }}" class="btn btn-sm btn-outline-primary">Edit Profile Settings</a>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6 border-end">
                            <p class="mb-2"><i class="bi bi-building me-2 text-muted"></i><strong>Business Name:</strong> {{ $business->business_name }}</p>
                            <p class="mb-2"><i class="bi bi-person me-2 text-muted"></i><strong>Contact Name:</strong> {{ $business->contact_name }}</p>
                            <p class="mb-2"><i class="bi bi-envelope me-2 text-muted"></i><strong>Email:</strong> {{ $business->email }}</p>
                            <p class="mb-2"><i class="bi bi-telephone me-2 text-muted"></i><strong>Phone:</strong> {{ $business->phone }}</p>
                            <p class="mb-0"><i class="bi bi-geo-alt me-2 text-muted"></i><strong>Address:</strong> {{ $business->address }} {{ $business->address2 }}</p>
                        </div>
                        <div class="col-md-6" id="qbo-summary-container">
                            <div class="d-flex justify-content-center align-items-center h-100 py-4">
                                <div class="text-center">
                                    <div class="spinner-border text-primary spinner-border-sm mb-2" role="status"></div>
                                    <div class="small text-muted">Loading QuickBooks data...</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tabs for Orders and Images -->
            <div class="card shadow-sm border-0 rounded-4">
                <div class="card-header bg-white border-0 p-0">
                    <ul class="nav nav-tabs border-0" id="accountTabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active px-4 py-3 fw-bold border-0" id="orders-tab" data-bs-toggle="tab" data-bs-target="#orders" type="button" role="tab" aria-controls="orders" aria-selected="true">
                                Orders
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link px-4 py-3 fw-bold border-0" id="invoices-tab" data-bs-toggle="tab" data-bs-target="#invoices" type="button" role="tab" aria-controls="invoices" aria-selected="false">
                                Invoices (QuickBooks)
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link px-4 py-3 fw-bold border-0" id="images-tab" data-bs-toggle="tab" data-bs-target="#images" type="button" role="tab" aria-controls="images" aria-selected="false">
                                Images
                            </button>
                        </li>
                    </ul>
                </div>
                <div class="card-body p-0">
                    <div class="tab-content" id="accountTabsContent">
                        <!-- Orders Tab -->
                        <div class="tab-pane fade show active p-4" id="orders" role="tabpanel" aria-labelledby="orders-tab">
                            <div class="d-flex justify-content-center py-5">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="visually-hidden">Loading orders...</span>
                                </div>
                            </div>
                        </div>

                        <!-- Invoices Tab -->
                        <div class="tab-pane fade p-4" id="invoices" role="tabpanel" aria-labelledby="invoices-tab">
                            <div class="d-flex justify-content-center py-5">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="visually-hidden">Loading invoices...</span>
                                </div>
                            </div>
                        </div>

                        <!-- Images Tab -->
                        <div class="tab-pane fade p-4" id="images" role="tabpanel" aria-labelledby="images-tab">
                            <div class="d-flex justify-content-center py-5">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="visually-hidden">Loading images...</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="modal-container"></div>

    <style>
        .checkerboard {
            background-image: linear-gradient(45deg, #e5e5e5 25%, transparent 25%),
                              linear-gradient(-45deg, #e5e5e5 25%, transparent 25%),
                              linear-gradient(45deg, transparent 75%, #e5e5e5 75%),
                              linear-gradient(-45deg, transparent 75%, #e5e5e5 75%);
            background-size: 20px 20px;
            background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
        }
        .nav-tabs .nav-link {
            color: #6c757d;
            border-bottom: 3px solid transparent !important;
        }
        .nav-tabs .nav-link.active {
            color: #000;
            background: transparent !important;
            border-bottom: 3px solid #ffc107 !important;
        }
    </style>

    @push('scripts')
    <script>
        $(document).ready(function() {
            // State to keep track of loaded tabs
            const loadedTabs = {
                orders: false,
                invoices: false,
                images: false
            };

            // Function to load QBO summary
            function loadQboSummary() {
                $.get('{{ route('account.invoices') }}', function(data) {
                    $('#qbo-summary-container').html(data.summary_html);
                    $('#modal-container').html(data.modal_html);

                    // Initialize modal scripts if necessary
                    if ($('#payInvoicesModal').length) {
                        $('.invoice-checkbox').on('change', window.updateSelectedTotal);
                        window.updateSelectedTotal();

                        $('#payButton').on('click', function() {
                            $(this).prop('disabled', true).html('<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...');
                            $('#paymentForm').submit();
                        });
                    }
                });
            }

            // Function to load Tab content
            function loadTabContent(tabName, url) {
                if (loadedTabs[tabName]) return;

                const containerId = '#' + tabName;
                $.get(url, function(data) {
                    $(containerId).html(data.html || data);
                    loadedTabs[tabName] = true;

                    // Handle pagination for orders
                    if (tabName === 'orders') {
                        $(containerId).on('click', '.ajax-pagination a', function(e) {
                            e.preventDefault();
                            const pageUrl = $(this).attr('href');
                            $(containerId).html('<div class="d-flex justify-content-center py-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>');
                            $.get(pageUrl, function(pageData) {
                                $(containerId).html(pageData.html || pageData);
                            });
                        });
                    }
                });
            }

            // Initial load
            loadQboSummary();
            loadTabContent('orders', '{{ route('account.orders') }}');

            // Tab change listeners
            $('button[data-bs-toggle="tab"]').on('shown.bs.tab', function (e) {
                const targetId = $(e.target).data('bs-target').replace('#', '');
                if (targetId === 'invoices') {
                    loadTabContent('invoices', '{{ route('account.invoices') }}');
                } else if (targetId === 'images') {
                    loadTabContent('images', '{{ route('account.images') }}');
                } else if (targetId === 'orders') {
                    loadTabContent('orders', '{{ route('account.orders') }}');
                }
            });

            // Re-define within window context for global access
            window.uncheckAllInvoices = function() {
                $('.invoice-checkbox').prop('checked', false);
            };

            window.updateSelectedTotal = function() {
                let total = 0;
                let selectedIds = [];
                $('.invoice-checkbox:checked').each(function() {
                    total += parseFloat($(this).data('amount'));
                    selectedIds.push($(this).data('id'));
                });
                $('#selectedTotal').text('$' + total.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}));
                $('#invoiceIdsInput').val(selectedIds.join(','));
                $('#payButton').prop('disabled', selectedIds.length === 0);
            };
        });
    </script>
    @endpush
</x-app-layout>
