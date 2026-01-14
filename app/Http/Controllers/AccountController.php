<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

use App\Models\DtfOrder;
use App\Models\DtfImage;
use Illuminate\Support\Facades\Auth;

class AccountController extends Controller
{
    public function index()
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            if ($user->role === 'admin') {
                return redirect()->route('admin.dashboard')->with('info', 'You are logged in as admin and do not have a linked business. Use the admin panel to manage businesses.');
            }
            return redirect()->route('home')->with('error', 'No business associated with your account.');
        }

        $orders = DtfOrder::with('orderStatus')
            ->where('business_id', $business->id)
            ->orderBy('id', 'desc')
            ->get();

        $images = DtfImage::whereIn('dtforder_id', $orders->pluck('id'))
            ->orderBy('id', 'desc')
            ->get()
            ->unique('image_name'); // Show unique images based on name as a "gallery"

        return view('account.index', compact('business', 'orders', 'images'));
    }
}
