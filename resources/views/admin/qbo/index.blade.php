<x-app-layout>
    <x-slot name="header">
        <h2 class="fw-bold fs-4 text-dark mb-0 font-ubuntu">
            {{ __('QuickBooks Settings') }}
        </h2>
    </x-slot>

    <div class="py-5">
        <div class="container">
            <div class="row">
                <!-- Connection Status -->
                <div class="col-md-4 mb-4">
                    <div class="card shadow-sm border-0 rounded-4 h-100">
                        <div class="card-header bg-white border-bottom-0 pt-4 px-4">
                            <h5 class="fw-bold mb-0">Connection Status</h5>
                        </div>
                        <div class="card-body p-4 text-center">
                            @if($token)
                                <div class="mb-3">
                                    <span class="badge bg-success p-2 px-3 fs-6 rounded-pill">
                                        <i class="bi bi-check-circle-fill me-1"></i> Connected
                                    </span>
                                </div>
                                <p class="text-muted small mb-4">
                                    Realm ID: <span class="fw-bold">{{ $token->realm_id }}</span><br>
                                    Last Updated: {{ $token->updated_at->format('M d, Y H:i') }}
                                </p>

                                <div class="d-grid gap-2 mb-4">
                                    <button type="button" class="btn btn-outline-primary fw-bold text-uppercase py-2 shadow-sm" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="items">
                                        <i class="bi bi-eye me-1"></i> View Products
                                    </button>
                                    <button type="button" class="btn btn-outline-primary fw-bold text-uppercase py-2 shadow-sm" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="accounts">
                                        <i class="bi bi-eye me-1"></i> View Accounts
                                    </button>
                                    <button type="button" class="btn btn-outline-primary fw-bold text-uppercase py-2 shadow-sm" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="terms">
                                        <i class="bi bi-eye me-1"></i> View Terms
                                    </button>
                                </div>

                                <form method="POST" action="{{ route('admin.qbo.disconnect') }}" onsubmit="return confirm('Are you sure you want to disconnect QuickBooks?')">
                                    @csrf
                                    <button type="submit" class="btn btn-outline-danger w-100 fw-bold text-uppercase py-2 shadow-sm mb-2">
                                        Disconnect
                                    </button>
                                </form>

                                <form method="POST" action="{{ route('admin.qbo.reset-mappings') }}" onsubmit="return confirm('WARNING: This will clear all links between your Businesses/Orders and QuickBooks. This is usually only needed when switching between Sandbox and Production. Proceed?')">
                                    @csrf
                                    <button type="submit" class="btn btn-link text-danger small text-decoration-none fw-bold">
                                        Reset Environment Mappings
                                    </button>
                                </form>
                            @else
                                <div class="mb-3">
                                    <span class="badge bg-secondary p-2 px-3 fs-6 rounded-pill">
                                        <i class="bi bi-x-circle-fill me-1"></i> Not Connected
                                    </span>
                                </div>
                                <p class="text-muted small mb-4">
                                    Connect your application to QuickBooks Online to sync orders and payments.
                                </p>
                                <a href="{{ route('admin.qbo.connect') }}" class="btn btn-primary w-100 fw-bold text-uppercase py-2 shadow-sm">
                                    Connect to QuickBooks
                                </a>
                            @endif
                        </div>
                    </div>
                </div>

                <!-- QBO Settings -->
                <div class="col-md-8 mb-4">
                    <div class="card shadow-sm border-0 rounded-4 h-100">
                        <div class="card-header bg-white border-bottom-0 pt-4 px-4">
                            <h5 class="fw-bold mb-0">Configuration</h5>
                        </div>
                        <div class="card-body p-4">
                            <form method="POST" action="{{ route('admin.qbo.settings.update') }}">
                                @csrf
                                <div class="row g-3">
                                    <div class="col-md-6">
                                        <label for="qbo_product_id" class="form-label small fw-bold text-uppercase text-muted">DTF Product ID (Service/Item)</label>
                                        <div class="input-group">
                                            <input type="text" name="qbo_product_id" id="qbo_product_id" class="form-control bg-light" value="{{ $settings['qbo_product_id'] }}" placeholder="e.g. 1010000391">
                                            <button type="button" class="btn btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="items">View Items</button>
                                        </div>
                                        <div class="form-text small">Internal ID for DTF printing service in QBO.</div>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="qbo_shipping_id" class="form-label small fw-bold text-uppercase text-muted">Shipping Product ID</label>
                                        <div class="input-group">
                                            <input type="text" name="qbo_shipping_id" id="qbo_shipping_id" class="form-control bg-light" value="{{ $settings['qbo_shipping_id'] }}" placeholder="e.g. 1010000392">
                                            <button type="button" class="btn btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="items">View Items</button>
                                        </div>
                                        <div class="form-text small">Internal ID for Shipping service in QBO.</div>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="qbo_stripe_clearing_id" class="form-label small fw-bold text-uppercase text-muted">Stripe Holding (Clearing) Account ID</label>
                                        <div class="input-group">
                                            <input type="text" name="qbo_stripe_clearing_id" id="qbo_stripe_clearing_id" class="form-control bg-light" value="{{ $settings['qbo_stripe_clearing_id'] }}" placeholder="e.g. 101">
                                            <button type="button" class="btn btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="accounts">View Accounts</button>
                                        </div>
                                        <div class="form-text small">Account ID for temporary holding of Stripe activity (Must be Bank/Checking type in QBO).</div>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="qbo_deposit_account_id" class="form-label small fw-bold text-uppercase text-muted">Fallback Deposit Account ID</label>
                                        <div class="input-group">
                                            <input type="text" name="qbo_deposit_account_id" id="qbo_deposit_account_id" class="form-control bg-light" value="{{ $settings['qbo_deposit_account_id'] }}" placeholder="e.g. 35">
                                            <button type="button" class="btn btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="accounts">View Accounts</button>
                                        </div>
                                        <div class="form-text small">Fallback account ID if Stripe Clearing is not set (e.g. 35 for Undeposited Funds).</div>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="qbo_fee_account_id" class="form-label small fw-bold text-uppercase text-muted">Bank Fee Account ID</label>
                                        <div class="input-group">
                                            <input type="text" name="qbo_fee_account_id" id="qbo_fee_account_id" class="form-control bg-light" value="{{ $settings['qbo_fee_account_id'] }}" placeholder="e.g. 80">
                                            <button type="button" class="btn btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="accounts">View Accounts</button>
                                        </div>
                                        <div class="form-text small">Account ID for recording Stripe fees (e.g. 80 for Bank Charges).</div>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="qbo_bank_account_id" class="form-label small fw-bold text-uppercase text-muted">Target Bank Account ID</label>
                                        <div class="input-group">
                                            <input type="text" name="qbo_bank_account_id" id="qbo_bank_account_id" class="form-control bg-light" value="{{ $settings['qbo_bank_account_id'] }}" placeholder="e.g. 1">
                                            <button type="button" class="btn btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="accounts">View Accounts</button>
                                        </div>
                                        <div class="form-text small">Account ID for your actual Bank/Checking account where deposits land.</div>
                                    </div>
                                    <div class="col-md-6">
                                        <label for="qbo_term_id" class="form-label small fw-bold text-uppercase text-muted">Default Payment Term ID</label>
                                        <div class="input-group">
                                            <input type="text" name="qbo_term_id" id="qbo_term_id" class="form-control bg-light" value="{{ $settings['qbo_term_id'] }}" placeholder="e.g. 3">
                                            <button type="button" class="btn btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#qboDataModal" data-type="terms">View Terms</button>
                                        </div>
                                        <div class="form-text small">Internal ID for "Net 10" or other terms in QBO.</div>
                                    </div>
                                    <div class="col-12 mt-3">
                                        <div class="form-check form-switch custom-switch">
                                            <input class="form-check-input" type="checkbox" name="qbo_auto_invoice_on_checkout" id="qbo_auto_invoice_on_checkout" value="1" {{ $settings['qbo_auto_invoice_on_checkout'] == '1' ? 'checked' : '' }}>
                                            <label class="form-check-label fw-bold text-dark" for="qbo_auto_invoice_on_checkout">Auto-create QBO Invoices for "Invoice" orders</label>
                                        </div>
                                        <div class="form-text small">If enabled, orders paid via "Invoice" method will sync to QBO automatically on checkout. Stripe orders are always synced automatically.</div>
                                    </div>
                                    <div class="col-12 mt-4 text-end">
                                        <button type="submit" class="btn btn-primary fw-bold text-uppercase px-4 py-2 shadow-sm">
                                            Save Settings
                                        </button>
                                    </div>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- QBO Data Modal -->
    <div class="modal fade" id="qboDataModal" tabindex="-1" aria-labelledby="qboDataModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-scrollable">
            <div class="modal-content border-0 shadow rounded-4">
                <div class="modal-header bg-dark text-white py-3 px-4 border-bottom-0 rounded-top-4">
                    <h5 class="modal-title fw-bold" id="qboDataModalLabel">QuickBooks Data</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body p-0">
                    <div id="modalLoading" class="text-center py-5">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mt-2 text-muted">Fetching data from QuickBooks...</p>
                    </div>
                    <div id="modalError" class="alert alert-danger m-4 d-none">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>
                        <span id="errorMessage"></span>
                    </div>
                    <div id="modalContent" class="table-responsive d-none">
                        <table class="table align-middle mb-0">
                            <thead class="bg-light sticky-top">
                                <tr id="tableHeader">
                                    <!-- Dynamic Headers -->
                                </tr>
                            </thead>
                            <tbody id="tableBody">
                                <!-- Dynamic Rows -->
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="modal-footer bg-light border-top-0 py-3 px-4">
                    <button type="button" class="btn btn-secondary fw-bold text-uppercase" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>

    @push('scripts')
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const modal = document.getElementById('qboDataModal');
            const modalTitle = document.getElementById('qboDataModalLabel');
            const loading = document.getElementById('modalLoading');
            const error = document.getElementById('modalError');
            const content = document.getElementById('modalContent');
            const tableHeader = document.getElementById('tableHeader');
            const tableBody = document.getElementById('tableBody');
            const errorMessage = document.getElementById('errorMessage');

            modal.addEventListener('show.bs.modal', function(event) {
                const button = event.relatedTarget;
                const type = button.getAttribute('data-type');

                // Reset Modal
                let title = 'QuickBooks Data';
                let url = '';
                let headers = [];
                let fields = [];

                if (type === 'items') {
                    title = 'QuickBooks Products (Items)';
                    url = "{{ route('admin.qbo.items') }}";
                    headers = ['ID', 'Name', 'Type', 'Unit Price'];
                    fields = ['Id', 'Name', 'Type', 'UnitPrice'];
                } else if (type === 'accounts') {
                    title = 'QuickBooks Accounts';
                    url = "{{ route('admin.qbo.accounts') }}";
                    headers = ['ID', 'Name', 'Type', 'Classification'];
                    fields = ['Id', 'Name', 'AccountType', 'Classification'];
                } else if (type === 'terms') {
                    title = 'QuickBooks Payment Terms';
                    url = "{{ route('admin.qbo.terms') }}";
                    headers = ['ID', 'Name', 'Due Days'];
                    fields = ['Id', 'Name', 'DueDays'];
                }

                modalTitle.textContent = title;
                loading.classList.remove('d-none');
                error.classList.add('d-none');
                content.classList.add('d-none');
                tableHeader.innerHTML = '';
                tableBody.innerHTML = '';

                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        loading.classList.add('d-none');
                        if (data.error) {
                            error.classList.remove('d-none');
                            errorMessage.textContent = data.error;
                        } else {
                            content.classList.remove('d-none');
                            renderTable(type, data);
                        }
                    })
                    .catch(err => {
                        loading.classList.add('d-none');
                        error.classList.remove('d-none');
                        errorMessage.textContent = 'An unexpected error occurred while fetching data.';
                        console.error(err);
                    });
            });

            function renderTable(type, data) {
                if (type === 'items') {
                    tableHeader.innerHTML = `
                        <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">ID</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Name</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Type</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Description</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Income Account</th>
                    `;
                    data.forEach(item => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td class="ps-4 py-3 fw-bold text-primary font-monospace">${item.Id}</td>
                            <td class="py-3 fw-bold">${item.Name}</td>
                            <td class="py-3"><span class="badge bg-light text-dark border">${item.Type}</span></td>
                            <td class="py-3 small text-muted">${item.Description || '--'}</td>
                            <td class="py-3 small">${item.IncomeAccountRef ? item.IncomeAccountRef.name : '--'}</td>
                        `;
                        tableBody.appendChild(row);
                    });
                } else if (type === 'terms') {
                    tableHeader.innerHTML = `
                        <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">ID</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Name</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Due Days</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Active</th>
                    `;
                    data.forEach(term => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td class="ps-4 py-3 fw-bold text-primary font-monospace">${term.Id}</td>
                            <td class="py-3 fw-bold">${term.Name}</td>
                            <td class="py-3">${term.DueDays || '0'}</td>
                            <td class="py-3"><span class="badge ${term.Active ? 'bg-success' : 'bg-danger'}">${term.Active ? 'Yes' : 'No'}</span></td>
                        `;
                        tableBody.appendChild(row);
                    });
                } else {
                    tableHeader.innerHTML = `
                        <th class="ps-4 py-3 text-uppercase small fw-bold text-muted">ID</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Name</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Type</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Sub-Type</th>
                        <th class="py-3 text-uppercase small fw-bold text-muted">Classification</th>
                    `;
                    data.forEach(acc => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td class="ps-4 py-3 fw-bold text-primary font-monospace">${acc.Id}</td>
                            <td class="py-3 fw-bold">${acc.Name}</td>
                            <td class="py-3 small">${acc.AccountType}</td>
                            <td class="py-3 small text-muted">${acc.AccountSubType}</td>
                            <td class="py-3"><span class="badge bg-info-subtle text-info border border-info-subtle">${acc.Classification}</span></td>
                        `;
                        tableBody.appendChild(row);
                    });
                }
            }
        });
    </script>
    @endpush
</x-app-layout>
