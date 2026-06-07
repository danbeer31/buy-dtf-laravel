<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\AccountingReconciliationCheck;
use App\Services\Accounting\StripeQboReconciliationService;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;

class ReconciliationController extends Controller
{
    public function index(Request $request)
    {
        $query = AccountingReconciliationCheck::with('business')
            ->where('provider', 'stripe')
            ->orderByDesc('ran_at')
            ->orderByDesc('id');

        if ($request->filled('status')) {
            $query->where('status', (string) $request->input('status'));
        }

        if ($request->filled('business_id')) {
            $query->where('business_id', (int) $request->input('business_id'));
        }

        $checks = $query->paginate(25)->withQueryString();

        return view('admin.payments.reconciliation_index', compact('checks'));
    }

    public function show(AccountingReconciliationCheck $check)
    {
        $check->load('business');
        return view('admin.payments.reconciliation_show', compact('check'));
    }

    public function rerun(Request $request, StripeQboReconciliationService $service): RedirectResponse
    {
        $request->validate([
            'business_id' => 'nullable|integer',
            'as_of_date' => 'nullable|date',
        ]);

        $result = $service->run([
            'business_id' => $request->filled('business_id') ? (int) $request->input('business_id') : null,
            'as_of_date' => $request->input('as_of_date'),
            'scope' => $request->filled('as_of_date') ? 'as_of' : 'current',
            'persist' => true,
            'tolerance_cents' => 1,
        ]);

        $msg = "Reconciliation run complete: status={$result['status']} diff_cents={$result['difference_amount_cents']}";
        if ($result['status'] === 'error') {
            return back()->with('error', $msg . ($result['notes'] ? " ({$result['notes']})" : ''));
        }

        return back()->with('success', $msg);
    }
}

