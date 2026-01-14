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
        $business->load(['user', 'settings', 'dtfOrders.orderStatus']);

        $orders = $business->dtfOrders()->orderBy('created_at', 'desc')->get();

        return view('admin.business.show', compact('business', 'orders'));
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
        if (!$business->user) {
            return back()->with('error', 'This business does not have a linked user.');
        }

        // Check if the business has a "confirmed" status before allowing impersonation if needed
        // but typically admins should be able to impersonate any business user.

        // Store the original admin ID in session to allow "returning"
        session(['admin_impersonator' => Auth::id()]);

        Auth::login($business->user);

        return redirect()->route('dashboard')->with('success', 'You are now logged in as ' . $business->user->name);
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
