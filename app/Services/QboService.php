<?php

namespace App\Services;

use App\Models\QboToken;
use App\Models\Setting;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Cache;

class QboService
{
    protected $baseUrl;
    protected $clientId;
    protected $clientSecret;
    protected $accessToken;
    protected $realmId;

    public function __construct()
    {
        $environment = config('services.qbo.environment', 'Development');
        $this->baseUrl = $environment === 'Production'
            ? 'https://quickbooks.api.intuit.com/v3/company/'
            : 'https://sandbox-quickbooks.api.intuit.com/v3/company/';

        $this->clientId = config('services.qbo.client_id');
        $this->clientSecret = config('services.qbo.client_secret');
    }

    public function init()
    {
        $qboToken = QboToken::getTokenRecord();
        if (!$qboToken) {
            throw new \Exception('No QBO tokens found. Please initialize tokens first.');
        }

        if ($qboToken->isAccessTokenExpired()) {
            $qboToken = $this->refreshTokens($qboToken);
        }

        $this->accessToken = $qboToken->access_token;
        $this->realmId = $qboToken->realm_id;

        return $this;
    }

    protected function refreshTokens(QboToken $qboToken)
    {
        Log::info('Refreshing QBO tokens...');

        $response = Http::asForm()->withHeaders([
            'Authorization' => 'Basic ' . base64_encode($this->clientId . ':' . $this->clientSecret),
            'Accept' => 'application/json',
        ])->post('https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer', [
            'grant_type' => 'refresh_token',
            'refresh_token' => $qboToken->refresh_token,
        ]);

        if ($response->failed()) {
            Log::error('Failed to refresh QBO tokens: ' . $response->body());
            throw new \Exception('Failed to refresh QBO tokens');
        }

        $data = $response->json();

        $qboToken->update([
            'access_token' => $data['access_token'],
            'refresh_token' => $data['refresh_token'] ?? $qboToken->refresh_token,
            'expires_in' => time() + $data['expires_in'],
            'x_refresh_token_expires_in' => time() + ($data['x_refresh_token_expires_in'] ?? 8640000), // ~100 days default
        ]);

        return $qboToken;
    }

    public function request($method, $endpoint, $data = [])
    {
        $this->init();

        $url = $this->baseUrl . $this->realmId . '/' . $endpoint;

        $request = Http::withHeaders([
            'Authorization' => 'Bearer ' . $this->accessToken,
            'Accept' => 'application/json',
            'Content-Type' => 'application/json',
        ]);

        if ($method === 'GET') {
            $response = $request->get($url, $data);
        } else {
            $response = $request->post($url, $data);
        }

        if ($response->failed()) {
            Log::error("QBO API Error ($endpoint): " . $response->body());
            return [
                'error' => true,
                'status' => $response->status(),
                'body' => $response->json(),
                'raw' => $response->body()
            ];
        }

        return $response->json();
    }

    public function findOrCreateCustomer($business)
    {
        if (!empty($business->qbo_customer_id)) {
            // Verify customer still exists in QBO (since user might be using a new sandbox)
            $verify = $this->request('GET', "customer/{$business->qbo_customer_id}");
            if (!isset($verify['error'])) {
                return $business->qbo_customer_id;
            }

            Log::warning("QBO Customer ID {$business->qbo_customer_id} for business {$business->id} is invalid or not found. Re-searching by email.");
            $business->update(['qbo_customer_id' => null]);
        }

        $email = $business->email;
        // Basic escaping for single quotes in email
        $safeEmail = str_replace("'", "\\'", $email);
        $query = "SELECT * FROM Customer WHERE PrimaryEmailAddr = '{$safeEmail}'";

        $result = $this->request('GET', 'query', ['query' => $query]);

        if (isset($result['QueryResponse']['Customer']) && count($result['QueryResponse']['Customer']) > 0) {
            $customer = $result['QueryResponse']['Customer'][0];
            $business->update(['qbo_customer_id' => $customer['Id']]);
            return $customer['Id'];
        }

        // Create new customer
        $customerData = [
            "GivenName" => (string)$business->contact_name,
            "CompanyName" => (string)$business->business_name,
            "DisplayName" => (string)$business->business_name,
            "PrimaryEmailAddr" => [
                "Address" => (string)$business->email
            ],
            "BillAddr" => [
                "Line1" => (string)$business->address,
                "Line2" => (string)$business->address2,
                "City" => (string)$business->city,
                "CountrySubDivisionCode" => (string)$business->state,
                "PostalCode" => (string)$business->zip
            ]
        ];

        $createResult = $this->request('POST', 'customer', $customerData);

        if (isset($createResult['error'])) {
            throw new \Exception("Failed to create customer in QBO: " . json_encode($createResult['body']));
        }

        $customerId = $createResult['Customer']['Id'];
        $business->update(['qbo_customer_id' => $customerId]);

        return $customerId;
    }

    public function getCustomerBalance($qboCustomerId)
    {
        if (empty($qboCustomerId)) return 0;

        $result = $this->request('GET', "customer/{$qboCustomerId}");

        if (isset($result['error'])) {
            Log::error("Failed to fetch customer balance for QBO ID {$qboCustomerId}: " . json_encode($result['body']));

            // If customer not found, it might be a sandbox mismatch.
            // We don't clear it here to avoid side effects on GET requests,
            // but we return 0 safely.
            return 0;
        }

        return $result['Customer']['Balance'] ?? 0;
    }

    public function getUnpaidInvoices($qboCustomerId)
    {
        if (empty($qboCustomerId)) return [];

        // Query for unpaid or partially paid invoices for this customer
        $query = "SELECT * FROM Invoice WHERE CustomerRef = '{$qboCustomerId}' AND Balance > '0' ORDERBY TxnDate ASC";
        $result = $this->request('GET', 'query', ['query' => $query]);

        if (isset($result['error'])) {
            Log::error("Failed to fetch unpaid invoices for QBO ID {$qboCustomerId}: " . json_encode($result['body']));
            return [];
        }

        return array_map(function (array $invoice) {
            $invoice['PayableBalance'] = $this->getInvoicePayableBalance($invoice);

            return $invoice;
        }, $result['QueryResponse']['Invoice'] ?? []);
    }

    public function getInvoiceHistory($qboCustomerId, $limit = 20)
    {
        if (empty($qboCustomerId)) return [];

        // Query for the last X invoices for this customer
        $query = "SELECT * FROM Invoice WHERE CustomerRef = '{$qboCustomerId}' ORDERBY TxnDate DESC MAXRESULTS {$limit}";
        $result = $this->request('GET', 'query', ['query' => $query]);

        if (isset($result['error'])) {
            Log::error("Failed to fetch invoice history for QBO ID {$qboCustomerId}: " . json_encode($result['body']));
            return [];
        }

        return array_map(function (array $invoice) {
            $invoice['PayableBalance'] = $this->getInvoicePayableBalance($invoice);

            return $invoice;
        }, $result['QueryResponse']['Invoice'] ?? []);
    }

    public function getInvoicePayableBalance(array $invoice): float
    {
        $balance = round((float)($invoice['Balance'] ?? 0), 2);
        if ($balance <= 0) {
            return 0.0;
        }

        $totalAmount = round((float)($invoice['TotalAmt'] ?? $balance), 2);
        $totalTax = round((float)($invoice['TxnTaxDetail']['TotalTax'] ?? 0), 2);
        $deposit = round((float)($invoice['Deposit'] ?? 0), 2);
        $difference = round($totalAmount - $balance, 2);

        if (
            $deposit <= 0
            && $totalTax > 0
            && abs($difference - $totalTax) <= 0.01
            && !$this->invoiceHasAppliedPayment($invoice)
        ) {
            return $totalAmount;
        }

        return $balance;
    }

    private function invoiceHasAppliedPayment(array $invoice): bool
    {
        $linkedTransactions = $invoice['LinkedTxn'] ?? [];
        if (!is_array($linkedTransactions)) {
            return false;
        }

        if (isset($linkedTransactions['TxnType'])) {
            $linkedTransactions = [$linkedTransactions];
        }

        $paymentTypes = ['Payment', 'CreditMemo', 'RefundReceipt'];
        foreach ($linkedTransactions as $transaction) {
            if (!is_array($transaction)) {
                continue;
            }

            if (in_array($transaction['TxnType'] ?? null, $paymentTypes, true)) {
                return true;
            }
        }

        return false;
    }

    public function getItems()
    {
        $query = "SELECT * FROM Item MAXRESULTS 1000";
        $result = $this->request('GET', 'query', ['query' => $query]);
        return $result['QueryResponse']['Item'] ?? [];
    }

    public function getAccounts()
    {
        $query = "SELECT * FROM Account MAXRESULTS 1000";
        $result = $this->request('GET', 'query', ['query' => $query]);
        return $result['QueryResponse']['Account'] ?? [];
    }

    /**
     * Fetch current balance for a specific QBO account ID.
     */
    public function getAccountBalance(string $accountId): float
    {
        $result = $this->request('GET', "account/{$accountId}");

        if (isset($result['error'])) {
            throw new \RuntimeException("Failed to fetch QBO account {$accountId}: " . json_encode($result['body'] ?? $result));
        }

        $account = $result['Account'] ?? null;
        if (!$account) {
            throw new \RuntimeException("QBO account {$accountId} not found in response.");
        }

        if (isset($account['CurrentBalance'])) {
            return (float) $account['CurrentBalance'];
        }

        if (isset($account['CurrentBalanceWithSubAccounts'])) {
            return (float) $account['CurrentBalanceWithSubAccounts'];
        }

        throw new \RuntimeException("QBO account {$accountId} response missing balance fields.");
    }

    public function getSalesTerms()
    {
        $query = "SELECT * FROM Term MAXRESULTS 100";
        $result = $this->request('GET', 'query', ['query' => $query]);
        return $result['QueryResponse']['Term'] ?? [];
    }

    public function createInvoice($business, $order, bool $allowCustomerRetry = true)
    {
        $item_number = Setting::get('qbo_product_id', Setting::get('QBO_Product_ID'));
        $ship_item_number = Setting::get('qbo_shipping_id', Setting::get('QBO_Shipping_ID'));

        if (empty($item_number)) {
            throw new \Exception("QuickBooks DTF Product ID is not configured. Please set it in QuickBooks Settings.");
        }

        if (empty($ship_item_number) && $order->shipping_cost > 0) {
            throw new \Exception("QuickBooks Shipping Product ID is not configured. Please set it in QuickBooks Settings.");
        }

        $qboCustomerId = $this->findOrCreateCustomer($business);

        $isTaxExemptBusiness = (bool) ($business->tax_exempt ?? false);
        $taxCodeTaxable = Setting::get('qbo_tax_code', 'TAX');
        $taxCodeNonTaxable = Setting::get('qbo_non_tax_code', 'NON');

        // Build line items
        $lineItems = [];
        foreach ($order->dtfImages as $img) {
            $unitPrice = (float)$img->get_price();
            $description = (string)$img->image_name;
            if ($img->item_type === 'gang_sheet') {
                $sizeKey = strtoupper((string)(data_get($img->item_meta, 'size_key') ?: ($img->width . 'x' . $img->height)));
                $description = trim($description . ' (Gang Sheet ' . $sizeKey . ')');
            }

            $lineItems[] = [
                "Description" => $description,
                "DetailType" => "SalesItemLineDetail",
                "Amount" => round($unitPrice * $img->quantity, 2),
                "SalesItemLineDetail" => [
                    "ItemRef" => [
                        "value" => $item_number
                    ],
                    "Qty" => (int)$img->quantity,
                    "UnitPrice" => round($unitPrice, 2),
                    // Tax-exempt businesses should never be taxed in QBO.
                    "TaxCodeRef" => [
                        "value" => $isTaxExemptBusiness ? $taxCodeNonTaxable : $taxCodeTaxable
                    ],
                ]
            ];
        }

        // Add shipping if applicable
        if ($order->shipping_cost > 0) {
            $lineItems[] = [
                "Description" => "Shipping " . ($order->shippingMethod->description ?? 'UPS'),
                "DetailType" => "SalesItemLineDetail",
                "Amount" => round($order->shipping_cost, 2),
                "SalesItemLineDetail" => [
                    "ItemRef" => [
                        "value" => $ship_item_number
                    ],
                    "Qty" => 1,
                    "UnitPrice" => round($order->shipping_cost, 2),
                    // Shipping is always non-taxable per business rule.
                    "TaxCodeRef" => [
                        "value" => $taxCodeNonTaxable
                    ],
                ]
            ];
        }

        $invoiceNote = "Order #" . $order->id;
        if ($order->paymentInfo && $order->paymentInfo->stripe_charge_id) {
            $invoiceNote .= "\nStripe Charge ID: " . $order->paymentInfo->stripe_charge_id;
        }

        $invoiceData = [
            "CustomerRef" => [
                "value" => $qboCustomerId
            ],
            "Line" => $lineItems,
            "BillEmail" => [
                "Address" => (string)$business->email
            ],
            "ShipAddr" => [
                "Line1" => (string)$business->address,
                "Line2" => (string)$business->address2,
                "City" => (string)$business->city,
                "CountrySubDivisionCode" => (string)$business->state,
                "PostalCode" => (string)$business->zip
            ],
            "BillAddr" => [
                "Line1" => (string)$business->address,
                "Line2" => (string)$business->address2,
                "City" => (string)$business->city,
                "CountrySubDivisionCode" => (string)$business->state,
                "PostalCode" => (string)$business->zip
            ],
            "TxnDate" => date('Y-m-d'),
            "DueDate" => date('Y-m-d', strtotime('+10 days')),
            "AllowOnlinePayment" => true,
            "AllowOnlineCreditCardPayment" => true,
            "EmailStatus" => "NeedToSend",
            "PrivateNote" => $invoiceNote
        ];

        // If business is tax-exempt, explicitly indicate no tax should apply at txn level.
        if ($isTaxExemptBusiness) {
            $invoiceData["GlobalTaxCalculation"] = "NotApplicable";
        }

        // Add Sales Term if configured
        $termId = Setting::get('qbo_term_id');
        if (!empty($termId)) {
            $invoiceData["SalesTermRef"] = [
                "value" => $termId
            ];
        }

        $invoiceResult = $this->request('POST', 'invoice', $invoiceData);

        if (isset($invoiceResult['error'])) {
            $errorBody = $invoiceResult['body'] ?? [];
            $errorMessage = $errorBody['Fault']['Error'][0]['Message'] ?? 'Unknown error';
            $errorDetail = $errorBody['Fault']['Error'][0]['Detail'] ?? '';

            // Handle invalid IDs (sandbox/company switch)
            if ($invoiceResult['status'] == 400 && (str_contains($errorDetail, 'Invalid Reference Id') || str_contains($errorMessage, 'Invalid Reference Id'))) {
                Log::warning("QBO Invoice creation failed due to Invalid Reference ID. This usually means Customer, Product, or Account IDs are mismatched with the current environment.");

                // If it's a customer mismatch, clear it and retry once in the same request.
                if (str_contains($errorDetail, 'Names element id')) {
                    $business->update(['qbo_customer_id' => null]);
                    Log::info("Cleared qbo_customer_id for business {$business->id} due to mismatch.");

                    if ($allowCustomerRetry) {
                        Log::info("Retrying QBO invoice creation once after clearing customer link.", [
                            'order_id' => $order->id,
                            'business_id' => $business->id,
                        ]);

                        return $this->createInvoice($business->fresh(), $order, false);
                    }
                }
            }

            throw new \Exception("Failed to create invoice in QBO: " . json_encode($invoiceResult['body']));
        }

        $invoiceId = $invoiceResult['Invoice']['Id'];
        $docNumber = $invoiceResult['Invoice']['DocNumber'] ?? null;
        $order->update([
            'qbo_invoice_id' => $invoiceId,
            'qbo_invoice_number' => $docNumber
        ]);

        // Clear cache for this business
        if ($business && $business->id) {
            Cache::forget('qbo_data_' . $business->id);
        }

        return $invoiceResult['Invoice'];
    }

    public function recordPayment($order, $amount, $paymentRef = null, $fee = 0)
    {
        if (!$order->qbo_invoice_id) {
            throw new \Exception("Order does not have a QBO invoice ID.");
        }

        $clearingAccountId = Setting::get('qbo_stripe_clearing_id');
        if (empty($clearingAccountId)) {
            $clearingAccountId = Setting::get('qbo_deposit_account_id');
        }

        if (empty($clearingAccountId)) {
            throw new \Exception("QuickBooks Stripe Holding Account ID is not configured. Please set it in QuickBooks Settings.");
        }

        $qboCustomerId = $order->business->qbo_customer_id;
        if (!$qboCustomerId) {
            // Fallback attempt to find or create customer
            try {
                $qboCustomerId = $this->findOrCreateCustomer($order->business);
            } catch (\Exception $fe) {
                Log::error("DEBUG: Customer ID missing and fallback creation failed", ['error' => $fe->getMessage()]);
                throw new \Exception("QuickBooks Customer ID is missing for this business and could not be created.");
            }
        }

        $paymentData = [
            "CustomerRef" => [
                "value" => $qboCustomerId
            ],
            "TotalAmt" => round($amount, 2),
            "DepositToAccountRef" => [
                "value" => $clearingAccountId
            ],
            "UnappliedAmt" => 0, // Explicitly tell QBO this is NOT unapplied (it's linked below)
            "TxnDate" => date('Y-m-d'),
            "Line" => [
                [
                    "Amount" => round($amount, 2),
                    "LinkedTxn" => [
                        [
                            "TxnId" => $order->qbo_invoice_id,
                            "TxnType" => "Invoice"
                        ]
                    ]
                ]
            ]
        ];

        if ($paymentRef) {
            // QBO DocNumber (PaymentRefNum) has a 21 character limit.
            $paymentData["PaymentRefNum"] = substr($paymentRef, 0, 21);

            $note = "Full Stripe Reference: " . $paymentRef;
            if ($order->paymentInfo && $order->paymentInfo->stripe_charge_id) {
                $note .= "\nStripe Charge ID: " . $order->paymentInfo->stripe_charge_id;
            }
            $paymentData["PrivateNote"] = $note;
        }

        Log::info("DEBUG: Recording QBO Payment to Stripe Clearing", ['order_id' => $order->id, 'amount' => $amount, 'ref' => $paymentRef]);
        $paymentResult = $this->request('POST', 'payment', $paymentData);

        if (isset($paymentResult['error'])) {
            Log::error("DEBUG: Failed to record payment in QBO", ['error' => $paymentResult['body']]);
            throw new \Exception("Failed to record payment in QBO: " . json_encode($paymentResult['body']));
        }

        Log::info("DEBUG: Successfully recorded payment in QBO", ['qbo_payment_id' => $paymentResult['Payment']['Id']]);

        // Clear cache for this business
        if ($order && $order->business_id) {
            Cache::forget('qbo_data_' . $order->business_id);
        }

        // Update PaymentInfo with QBO Payment ID
        if ($order && $order->paymentInfo) {
            $order->paymentInfo->update(['qbo_payment_id' => $paymentResult['Payment']['Id']]);
        }

        return $paymentResult['Payment'];
    }

    public function recordGenericPayment($qboCustomerId, $invoiceId, $amount, $paymentRef = null)
    {
        $clearingAccountId = Setting::get('qbo_stripe_clearing_id');
        if (empty($clearingAccountId)) {
            $clearingAccountId = Setting::get('qbo_deposit_account_id');
        }

        if (empty($clearingAccountId)) {
            throw new \Exception("QuickBooks Stripe Holding Account ID is not configured.");
        }

        $paymentData = [
            "CustomerRef" => [
                "value" => $qboCustomerId
            ],
            "TotalAmt" => round($amount, 2),
            "DepositToAccountRef" => [
                "value" => $clearingAccountId
            ],
            "UnappliedAmt" => 0,
            "TxnDate" => date('Y-m-d'),
            "Line" => [
                [
                    "Amount" => round($amount, 2),
                    "LinkedTxn" => [
                        [
                            "TxnId" => $invoiceId,
                            "TxnType" => "Invoice"
                        ]
                    ]
                ]
            ]
        ];

        if ($paymentRef) {
            $paymentData["PaymentRefNum"] = substr($paymentRef, 0, 21);
            $paymentData["PrivateNote"] = "Full Stripe Reference: " . $paymentRef;
        }

        Log::info("DEBUG: Recording Generic QBO Payment to Stripe Clearing", ['customer_id' => $qboCustomerId, 'invoice_id' => $invoiceId, 'amount' => $amount, 'ref' => $paymentRef]);
        $paymentResult = $this->request('POST', 'payment', $paymentData);

        if (isset($paymentResult['error'])) {
            Log::error("DEBUG: Failed to record generic payment in QBO", ['error' => $paymentResult['body']]);
            throw new \Exception("Failed to record generic payment in QBO: " . json_encode($paymentResult['body']));
        }

        Log::info("DEBUG: Successfully recorded generic payment in QBO", ['qbo_payment_id' => $paymentResult['Payment']['Id']]);

        // Find business by QBO customer ID and clear cache
        $business = \App\Models\Business::where('qbo_customer_id', $qboCustomerId)->first();
        if ($business) {
            Cache::forget('qbo_data_' . $business->id);
        }

        return $paymentResult['Payment'];
    }

    public function recordStripeFee($entry)
    {
        if ($entry->qbo_expense_id) {
            return null; // Already recorded
        }

        // If it's a StripePayoutEntry, check if the associated PaymentInfo already has an expense recorded
        if ($entry instanceof \App\Models\StripePayoutEntry) {
            // Try to find PaymentInfo by dtforder_id OR by stripe_transaction_id (BT ID) OR processor_confirm (PI ID)
            $paymentInfo = null;
            if ($entry->dtfOrder && $entry->dtfOrder->paymentInfo) {
                $paymentInfo = $entry->dtfOrder->paymentInfo;
            } else {
                $paymentInfo = \App\Models\PaymentInfo::where('stripe_charge_id', $entry->stripe_transaction_id)
                    ->orWhere('processor_confirm', $entry->stripe_transaction_id)
                    ->first();
            }

            if ($paymentInfo && $paymentInfo->qbo_fee_expense_id) {
                $expenseId = $paymentInfo->qbo_fee_expense_id;
                $entry->update(['qbo_expense_id' => $expenseId]);
                return null; // Already handled by checkout, mapping updated
            }
        }

        // Search for existing expense in QBO by private note (idempotency)
        // Key fee expense by balance_transaction_id (stored in stripe_transaction_id for Payout Entries)
        $stripeTxId = $entry->stripe_transaction_id;
        try {
            $query = "SELECT * FROM Purchase WHERE PrivateNote LIKE '%{$stripeTxId}%'";
            $existingExpenses = $this->request('GET', "query?query=" . urlencode($query));
            if (isset($existingExpenses['QueryResponse']['Purchase']) && !empty($existingExpenses['QueryResponse']['Purchase'])) {
                $expenseId = $existingExpenses['QueryResponse']['Purchase'][0]['Id'];
                Log::info("Found existing Stripe fee expense in QBO for {$stripeTxId}: {$expenseId}");

                if (is_callable($entry->update)) {
                    ($entry->update)(['qbo_expense_id' => $expenseId]);
                } else {
                    $entry->update(['qbo_expense_id' => $expenseId]);
                }
                return $existingExpenses['QueryResponse']['Purchase'][0];
            }
        } catch (\Exception $e) {
            Log::warning("Failed to check for existing Stripe fee expense in QBO: " . $e->getMessage());
        }

        $feeAccountId = Setting::get('qbo_fee_account_id', Setting::get('QBO_Fee_Account_ID'));
        if ($feeAccountId == 80) {
            Log::info("DEBUG: Fee account ID is 80, which is known to fail. Attempting to find a valid Expense account.");
            // We could try to dynamically find an "Expense" account, but for now let's just log it
            // and maybe the user can update the setting.
        }
        $clearingAccountId = Setting::get('qbo_stripe_clearing_id');
        if (empty($clearingAccountId)) {
            $clearingAccountId = Setting::get('qbo_deposit_account_id');
        }

        if (empty($feeAccountId) || empty($clearingAccountId)) {
            Log::warning("QBO recordStripeFee configuration missing", [
                'feeAccountId' => $feeAccountId,
                'clearingAccountId' => $clearingAccountId
            ]);
            throw new \Exception("QuickBooks Fee Account or Stripe Holding Account ID is not configured.");
        }

        $txnDate = date('Y-m-d');
        if (isset($entry->payout) && $entry->payout->arrival_date) {
            $txnDate = $entry->payout->arrival_date->format('Y-m-d');
        }

        $note = "Stripe Fee for Transaction: " . $entry->stripe_transaction_id;
        if (isset($entry->payout) && $entry->payout->stripe_payout_id) {
            $note .= " (Payout: " . $entry->payout->stripe_payout_id . ")";
        }

        $expenseData = [
            "PaymentType" => "Cash",
            "AccountRef" => [
                "value" => $clearingAccountId
            ],
            "Line" => [
                [
                    "Description" => "Stripe fee for charge " . $entry->stripe_transaction_id,
                    "Amount" => abs((float)$entry->fee),
                    "DetailType" => "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail" => [
                        "AccountRef" => [
                            "value" => $feeAccountId
                        ]
                    ]
                ]
            ],
            "TxnDate" => $txnDate,
            "PrivateNote" => $note
        ];

        Log::info("QBO recordStripeFee request", [
            'stripe_transaction_id' => $entry->stripe_transaction_id,
            'clearingAccountId' => $clearingAccountId,
            'feeAccountId' => $feeAccountId,
            'amount' => $entry->fee
        ]);
        $result = $this->request('POST', 'purchase', $expenseData);

        if (isset($result['error'])) {
            Log::error("QBO recordStripeFee error for transaction {$entry->stripe_transaction_id}: " . json_encode($result['body']));
            throw new \Exception("Failed to create fee expense in QBO: " . json_encode($result['body']));
        }

        $expenseId = $result['Purchase']['Id'];
        Log::info("QBO recordStripeFee success: Expense ID {$expenseId} for transaction {$entry->stripe_transaction_id}");

        if (is_callable($entry->update)) {
            ($entry->update)(['qbo_expense_id' => $expenseId]);
        } else {
            $entry->update(['qbo_expense_id' => $expenseId]);
        }

        return $result['Purchase'];
    }

    public function recordStripePayoutTransfer($payout)
    {
        if ($payout->qbo_transfer_id) {
            return null; // Already recorded
        }

        $clearingAccountId = Setting::get('qbo_stripe_clearing_id');
        if (empty($clearingAccountId)) {
            // Fallback for transition
            $clearingAccountId = Setting::get('qbo_deposit_account_id');
        }
        $bankAccountId = Setting::get('qbo_bank_account_id');

        if (empty($clearingAccountId) || empty($bankAccountId)) {
            throw new \Exception("QuickBooks Stripe Holding or Bank Account ID is not configured.");
        }

        // Before doing the transfer, we NO LONGER record fees here as per guidelines.
        // Fees must be recorded immediately at charge time.

        $transferData = [
            "Amount" => (float)$payout->amount,
            "FromAccountRef" => [
                "value" => $clearingAccountId
            ],
            "ToAccountRef" => [
                "value" => $bankAccountId
            ],
            "TxnDate" => $payout->arrival_date->format('Y-m-d'),
            "PrivateNote" => "Stripe Payout: " . $payout->stripe_payout_id
        ];

        Log::info("QBO recordStripePayoutTransfer request", [
            'stripe_payout_id' => $payout->stripe_payout_id,
            'amount' => $payout->amount,
            'clearingAccountId' => $clearingAccountId,
            'bankAccountId' => $bankAccountId
        ]);
        $result = $this->request('POST', 'transfer', $transferData);

        if (isset($result['error'])) {
            Log::error("QBO recordStripePayoutTransfer error for payout {$payout->stripe_payout_id}: " . json_encode($result['body']));
            throw new \Exception("Failed to create transfer in QBO: " . json_encode($result['body']));
        }

        $transferId = $result['Transfer']['Id'];
        Log::info("QBO recordStripePayoutTransfer success: Transfer ID {$transferId} for payout {$payout->stripe_payout_id}");
        $payout->update(['qbo_transfer_id' => $transferId]);

        return $result['Transfer'];
    }

    public function recordStripeRefund($entry)
    {
        if ($entry->qbo_refund_id) {
            return null; // Already recorded
        }

        $clearingAccountId = Setting::get('qbo_stripe_clearing_id');
        if (empty($clearingAccountId)) {
            $clearingAccountId = Setting::get('qbo_deposit_account_id');
        }
        if (empty($clearingAccountId)) {
            throw new \Exception("QuickBooks Stripe Clearing Account ID is not configured.");
        }

        // For Stripe refunds, we usually want to record it as a Refund Receipt or Credit Memo
        // If we have an associated order/customer, we can use Refund Receipt.
        // If not, we might just record it as a negative deposit or an expense (though expense is usually for outflows).
        // The objective says: "Route through Stripe Clearing, not Checking".

        $qboCustomerId = null;
        if ($entry->dtfOrder && $entry->dtfOrder->business) {
            $qboCustomerId = $entry->dtfOrder->business->qbo_customer_id;
        }

        if (!$qboCustomerId) {
            // Generic refund if customer not found - record as an Expense (debiting income/refund account, crediting clearing)
            // Or just log and skip if we strictly need a customer.
            Log::warning("Stripe refund for transaction {$entry->stripe_transaction_id} has no associated customer. Skipping automatic QBO sync.");
            return null;
        }

        $refundData = [
            "CustomerRef" => [
                "value" => $qboCustomerId
            ],
            "DepositToAccountRef" => [
                "value" => $clearingAccountId
            ],
            "TotalAmt" => abs((float)$entry->gross),
            "TxnDate" => $entry->payout->arrival_date->format('Y-m-d'),
            "Line" => [
                [
                    "Amount" => abs((float)$entry->gross),
                    "DetailType" => "SalesItemLineDetail",
                    "SalesItemLineDetail" => [
                        "ItemRef" => [
                            "value" => Setting::get('qbo_product_id')
                        ],
                        "Qty" => 1,
                        "UnitPrice" => abs((float)$entry->gross)
                    ]
                ]
            ],
            "PrivateNote" => "Stripe Refund: " . $entry->stripe_transaction_id . " (Payout: " . $entry->payout->stripe_payout_id . ")"
        ];

        $result = $this->request('POST', 'refundreceipt', $refundData);

        if (isset($result['error'])) {
            Log::error("Failed to create refund receipt in QBO: " . json_encode($result['body']));
            return null;
        }

        $entry->update(['qbo_refund_id' => $result['RefundReceipt']['Id']]);

        return $result['RefundReceipt'];
    }

    public function recordStripeAdjustment($entry)
    {
        if ($entry->qbo_expense_id) {
            return null; // Already recorded
        }

        $feeAccountId = Setting::get('qbo_fee_account_id');
        $clearingAccountId = Setting::get('qbo_stripe_clearing_id');
        if (empty($clearingAccountId)) {
            $clearingAccountId = Setting::get('qbo_deposit_account_id');
        }

        if (empty($feeAccountId) || empty($clearingAccountId)) {
            throw new \Exception("QuickBooks Fee Account or Stripe Holding Account ID is not configured.");
        }

        // Adjustments are recorded as Expenses (Purchases) from Stripe Holding
        // We use the absolute value of the net amount for the expense
        $amount = abs((float)$entry->net);

        $expenseData = [
            "PaymentType" => "Cash",
            "AccountRef" => [
                "value" => $clearingAccountId
            ],
            "Line" => [
                [
                    "Description" => "Stripe " . $entry->type . ": " . $entry->stripe_transaction_id,
                    "Amount" => $amount,
                    "DetailType" => "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail" => [
                        "AccountRef" => [
                            "value" => $feeAccountId
                        ]
                    ]
                ]
            ],
            "TxnDate" => $entry->payout->arrival_date->format('Y-m-d'),
            "PrivateNote" => "Stripe " . ucfirst($entry->type) . " (Payout: " . $entry->payout->stripe_payout_id . ")"
        ];

        $result = $this->request('POST', 'purchase', $expenseData);

        if (isset($result['error'])) {
            Log::error("QBO recordStripeAdjustment error: " . json_encode($result['body']));
            return null;
        }

        $expenseId = $result['Purchase']['Id'];
        $entry->update(['qbo_expense_id' => $expenseId]);

        return $result['Purchase'];
    }

    public function recordDeposit($payout)
    {
        // DEPRECATED: Replaced by recordStripePayoutTransfer and individual fee expenses
        Log::info("DEPRECATED: recordDeposit called. Use recordStripePayoutTransfer instead.");
        return $this->recordStripePayoutTransfer($payout);
    }
}
