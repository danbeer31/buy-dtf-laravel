<?php

namespace App\Http\Controllers;

use App\Models\Business;
use App\Models\DtfOrder;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;

class OrderController extends Controller
{
    public function index()
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            if ($user->role === 'admin') {
                return redirect()->route('admin.dashboard')->with('info', 'Admin access: Please use the admin panel to manage businesses.');
            }
            \Log::warning('Order index access: No business found for user: ' . $user->email . ' (ID: ' . $user->id . ')');
            return redirect()->route('home')->with('error', 'No business associated with your account. Please contact support.');
        }

        $orders = DtfOrder::where('business_id', $business->id)
            ->orderBy('id', 'desc')
            ->get();

        return view('orders.index', compact('business', 'orders'));
    }

    public function newOrder()
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            if ($user->role === 'admin') {
                return redirect()->route('admin.dashboard')->with('info', 'Admin access: Please use the admin panel to manage businesses.');
            }
            \Log::warning('New order access: No business found for user: ' . $user->email . ' (ID: ' . $user->id . ')');
            return redirect()->route('home')->with('error', 'No business associated with your account. Please contact support.');
        }

        if ($openOrder = $business->open_order()) {
            return redirect()->route('orders.show', $openOrder->id);
        }

        $order = DtfOrder::create([
            'business_id' => $business->id,
            'order_date' => now(),
            'status' => 1, // Status 1 is 'open' based on FuelPHP logic
        ]);

        return redirect()->route('orders.show', $order->id);
    }

    public function show($id)
    {
        $user = Auth::user();
        $business = $user->business;
        $order = DtfOrder::with(['dtfImages', 'orderStatus', 'shippingMethod'])->findOrFail($id);

        if ($order->business_id !== $business->id) {
            abort(403);
        }

        return view('orders.show', compact('business', 'order'));
    }

    public function placeOrder($id)
    {
        $user = Auth::user();
        $business = $user->business;
        $order = DtfOrder::findOrFail($id);

        if ($order->business_id !== $business->id) {
            abort(403);
        }

        // For now, redirect to a placeholder or back with info
        return back()->with('info', 'Place order functionality (checkout) is being migrated.');
    }
}
