<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\Business;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;

class BusinessController extends Controller
{
    public function index(Request $request)
    {
        $query = Business::query();

        if ($request->filled('search')) {
            $search = $request->search;
            $query->where(function ($q) use ($search) {
                $q->where('business_name', 'like', "%{$search}%")
                  ->orWhere('contact_name', 'like', "%{$search}%")
                  ->orWhere('email', 'like', "%{$search}%");
            });
        }

        if ($request->filled('filter_status')) {
            $query->where('status', $request->filter_status);
        }

        $businesses = $query->orderBy('created_at', 'desc')->paginate(15)->withQueryString();

        return view('admin.business.index', compact('businesses'));
    }

    public function show(Business $business)
    {
        // For now, just load the business. Later we can add orders and settings.
        $business->load(['user', 'settings', 'dtfOrders.orderStatus', 'paymentMethods']);

        $orders = $business->dtfOrders()->orderBy('created_at', 'desc')->get();
        $paymentMethods = \App\Models\PaymentMethod::all();

        // Get recent payouts for this business
        $payouts = \App\Models\StripePayout::whereHas('entries', function($q) use ($business) {
            $q->whereHas('dtfOrder', function($oq) use ($business) {
                $oq->where('business_id', $business->id);
            });
        })->orderBy('arrival_date', 'desc')->take(10)->get();

        return view('admin.business.show', compact('business', 'orders', 'paymentMethods', 'payouts'));
    }

    public function updatePaymentMethods(Request $request, Business $business)
    {
        $fuelDb = env('FUEL_DB_CONNECTION', 'fuelmysql');
        $request->validate([
            'payment_methods' => 'nullable|array',
            'payment_methods.*' => "exists:{$fuelDb}.paymentmethods,id",
        ]);

        $business->paymentMethods()->sync($request->input('payment_methods', []));

        return back()->with('success', 'Business payment methods updated successfully.');
    }

    public function updateRate(Request $request, Business $business)
    {
        $request->validate([
            'rate' => 'required|numeric|min:0',
        ]);

        $business->settings()->updateOrCreate(
            ['business_id' => $business->id],
            ['rate' => $request->rate]
        );

        return back()->with('success', 'Business rate updated successfully.');
    }

    public function toggleTaxExempt(Business $business)
    {
        $business->update([
            'tax_exempt' => !$business->tax_exempt
        ]);

        return back()->with('success', 'Tax exempt status updated successfully.');
    }

    public function impersonate(Business $business)
    {
        $targetUser = $business->user ?: User::where('email', $business->email)->first();

        if (!$targetUser) {
            return back()->with('error', 'This business does not have a linked user.');
        }

        // Check if the business has a "confirmed" status before allowing impersonation if needed
        // but typically admins should be able to impersonate any business user.

        // Store the original admin ID in session to allow "returning"
        session(['admin_impersonator' => Auth::id()]);

        Auth::login($targetUser);

        return redirect()->route('dashboard')->with('success', 'You are now logged in as ' . $targetUser->name);
    }

    public function stopImpersonating()
    {
        if (!session()->has('admin_impersonator')) {
            return redirect()->route('dashboard');
        }

        $adminId = session()->pull('admin_impersonator');
        $admin = User::find($adminId);

        if ($admin) {
            Auth::login($admin);
            return redirect()->route('admin.businesses.index')->with('success', 'You have returned to your admin account.');
        }

        Auth::logout();
        return redirect()->route('login');
    }
}
