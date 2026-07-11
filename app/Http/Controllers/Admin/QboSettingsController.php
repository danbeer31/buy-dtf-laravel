<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\QboToken;
use App\Models\Setting;
use App\Services\QboService;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class QboSettingsController extends Controller
{
    public function index()
    {
        $token = QboToken::getTokenRecord();

        $settings = [
            'qbo_product_id' => Setting::get('qbo_product_id', Setting::get('QBO_Product_ID')),
            'qbo_shipping_id' => Setting::get('qbo_shipping_id', Setting::get('QBO_Shipping_ID')),
            'qbo_stripe_clearing_id' => Setting::get('qbo_stripe_clearing_id', Setting::get('qbo_deposit_account_id')),
            'qbo_deposit_account_id' => Setting::get('qbo_deposit_account_id', Setting::get('QBO_Deposit_Account_ID', '35')),
            'qbo_fee_account_id' => Setting::get('qbo_fee_account_id', Setting::get('QBO_Fee_Account_ID')),
            'qbo_bank_account_id' => Setting::get('qbo_bank_account_id'),
            'qbo_term_id' => Setting::get('qbo_term_id'),
            'qbo_auto_invoice_on_checkout' => Setting::get('qbo_auto_invoice_on_checkout', '1'),
        ];

        return view('admin.qbo.index', compact('token', 'settings'));
    }

    public function updateSettings(Request $request)
    {
        $validated = $request->validate([
            'qbo_product_id' => 'nullable|string',
            'qbo_shipping_id' => 'nullable|string',
            'qbo_stripe_clearing_id' => 'nullable|string',
            'qbo_deposit_account_id' => 'nullable|string',
            'qbo_fee_account_id' => 'nullable|string',
            'qbo_bank_account_id' => 'nullable|string',
            'qbo_term_id' => 'nullable|string',
            'qbo_auto_invoice_on_checkout' => 'nullable|boolean',
        ]);

        foreach ($validated as $key => $value) {
            if ($key === 'qbo_auto_invoice_on_checkout') {
                $value = $request->has('qbo_auto_invoice_on_checkout') ? '1' : '0';
            }
            if ($key === 'qbo_fee_account_id' && $value == '80') {
                // If they explicitly try to set it to 80, we allow it but it might fail.
                // However, we shouldn't let it stay as a default if it's known bad.
            }
            Setting::updateOrCreate(['key' => $key], ['value' => $value]);
        }

        return back()->with('success', 'QuickBooks settings updated successfully.');
    }

    public function connect()
    {
        $clientId = config('services.qbo.client_id');
        $redirectUri = config('services.qbo.redirect_uri') ?: route('admin.qbo.callback');
        $scope = 'com.intuit.quickbooks.accounting openid profile';
        $state = csrf_token();

        $environment = config('services.qbo.environment', 'Development');
        $authUrl = $environment === 'Production'
            ? 'https://appcenter.intuit.com/connect/oauth2'
            : 'https://appcenter.intuit.com/connect/oauth2'; // Same for both actually, but discovery doc is better

        // Intuit OAuth2 Authorization URL
        $url = "https://appcenter.intuit.com/connect/oauth2" .
            "?client_id=" . $clientId .
            "&response_type=code" .
            "&scope=" . urlencode($scope) .
            "&redirect_uri=" . urlencode($redirectUri) .
            "&state=" . $state;

        return redirect($url);
    }

    public function callback(Request $request)
    {
        if ($request->has('error')) {
            return redirect()->route('admin.qbo.index')->with('error', 'QuickBooks connection failed: ' . $request->error);
        }

        $code = $request->code;
        $realmId = $request->realmId;

        $clientId = config('services.qbo.client_id');
        $clientSecret = config('services.qbo.client_secret');
        $redirectUri = config('services.qbo.redirect_uri') ?: route('admin.qbo.callback');

        $response = Http::asForm()->withHeaders([
            'Authorization' => 'Basic ' . base64_encode($clientId . ':' . $clientSecret),
            'Accept' => 'application/json',
        ])->post('https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer', [
            'grant_type' => 'authorization_code',
            'code' => $code,
            'redirect_uri' => $redirectUri,
        ]);

        if ($response->failed()) {
            Log::error('QuickBooks Token Exchange Failed: ' . $response->body());
            return redirect()->route('admin.qbo.index')->with('error', 'Failed to exchange code for tokens.');
        }

        $data = $response->json();

        QboToken::updateOrCreate(
            ['id' => 1], // Usually only one company connection
            [
                'access_token' => $data['access_token'],
                'refresh_token' => $data['refresh_token'],
                'realm_id' => $realmId,
                'expires_in' => time() + $data['expires_in'],
                'x_refresh_token_expires_in' => time() + ($data['x_refresh_token_expires_in'] ?? 8640000),
            ]
        );

        return redirect()->route('admin.qbo.index')->with('success', 'QuickBooks connected successfully.');
    }

    public function disconnect()
    {
        QboToken::truncate(); // Or just delete the record
        return redirect()->route('admin.qbo.index')->with('success', 'QuickBooks disconnected.');
    }

    public function resetMappings()
    {
        \App\Models\Business::whereNotNull('qbo_customer_id')->update(['qbo_customer_id' => null]);
        \App\Models\DtfOrder::whereNotNull('qbo_invoice_id')->update(['qbo_invoice_id' => null]);
        \App\Models\PaymentInfo::whereNotNull('qbo_payment_id')->update(['qbo_payment_id' => null]);
        \App\Models\PaymentInfo::whereNotNull('qbo_fee_expense_id')->update(['qbo_fee_expense_id' => null]);
        \App\Models\StripePayout::whereNotNull('qbo_transfer_id')->update(['qbo_transfer_id' => null]);
        \App\Models\StripePayout::whereNotNull('qbo_deposit_id')->update(['qbo_deposit_id' => null]);
        \App\Models\StripePayoutEntry::whereNotNull('qbo_expense_id')->update(['qbo_expense_id' => null]);
        \App\Models\StripePayoutEntry::whereNotNull('qbo_refund_id')->update(['qbo_refund_id' => null]);

        return redirect()->route('admin.qbo.index')->with('success', 'All QuickBooks customer, invoice, payment, and payout mappings have been reset.');
    }

    public function getItems(QboService $qbo)
    {
        try {
            $items = $qbo->getItems();
            return response()->json($items);
        } catch (\Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    public function getAccounts(QboService $qbo)
    {
        try {
            $accounts = $qbo->getAccounts();
            return response()->json($accounts);
        } catch (\Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    public function getSalesTerms(QboService $qbo)
    {
        try {
            $terms = $qbo->getSalesTerms();
            return response()->json($terms);
        } catch (\Exception $e) {
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    public function downloadItems(QboService $qbo)
    {
        try {
            $items = $qbo->getItems();
            $filename = "qbo_items_" . date('Y-m-d') . ".csv";

            $headers = [
                'Content-Type' => 'text/csv',
                'Content-Disposition' => "attachment; filename=\"$filename\"",
            ];

            $callback = function() use ($items) {
                $file = fopen('php://output', 'w');
                fputcsv($file, ['ID', 'Name', 'Type', 'Description', 'Income Account', 'Expense Account']);

                foreach ($items as $item) {
                    fputcsv($file, [
                        $item['Id'],
                        $item['Name'],
                        $item['Type'],
                        $item['Description'] ?? '',
                        $item['IncomeAccountRef']['name'] ?? ($item['IncomeAccountRef']['value'] ?? ''),
                        $item['ExpenseAccountRef']['name'] ?? ($item['ExpenseAccountRef']['value'] ?? ''),
                    ]);
                }
                fclose($file);
            };

            return response()->stream($callback, 200, $headers);
        } catch (\Exception $e) {
            return back()->with('error', 'Failed to fetch items from QuickBooks: ' . $e->getMessage());
        }
    }

    public function downloadAccounts(QboService $qbo)
    {
        try {
            $accounts = $qbo->getAccounts();
            $filename = "qbo_accounts_" . date('Y-m-d') . ".csv";

            $headers = [
                'Content-Type' => 'text/csv',
                'Content-Disposition' => "attachment; filename=\"$filename\"",
            ];

            $callback = function() use ($accounts) {
                $file = fopen('php://output', 'w');
                fputcsv($file, ['ID', 'Name', 'AccountType', 'AccountSubType', 'Classification', 'Currency']);

                foreach ($accounts as $account) {
                    fputcsv($file, [
                        $account['Id'],
                        $account['Name'],
                        $account['AccountType'],
                        $account['AccountSubType'],
                        $account['Classification'],
                        $account['CurrencyRef']['value'] ?? '',
                    ]);
                }
                fclose($file);
            };

            return response()->stream($callback, 200, $headers);
        } catch (\Exception $e) {
            return back()->with('error', 'Failed to fetch accounts from QuickBooks: ' . $e->getMessage());
        }
    }
}
