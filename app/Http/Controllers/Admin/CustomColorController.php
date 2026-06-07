<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\CustomColor;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Log;

class CustomColorController extends Controller
{
    public function index()
    {
        $user = Auth::user();
        $business = $user->business;

        $query = CustomColor::orderBy('name', 'asc');

        // If not superadmin, maybe we should filter?
        // But this is admin panel, usually admins see all or their own business.
        // Given the original code, it separated global and "the" business of the logged in user.

        $global_colors = CustomColor::where('business_id', 0)
            ->orderBy('name', 'asc')
            ->get();

        $shop_colors = collect();
        if ($business) {
            $shop_colors = CustomColor::where('business_id', $business->id)
                ->orderBy('name', 'asc')
                ->get();
        }

        // If it's a superadmin without a business, they might want to see ALL colors?
        // Or maybe they should be able to manage global colors anyway.

        return view('admin.customcolors.index', compact('global_colors', 'shop_colors', 'business'));
    }

    public function create()
    {
        $user = Auth::user();
        $business = $user->business;

        // Allow superadmin to create global colors (business_id = 0)
        if (!$business && $user->role !== 'superadmin') {
            return redirect()->route('admin.customcolors.index')->with('error', 'You must have an associated business to add custom colors.');
        }

        return view('admin.customcolors.create', compact('business'));
    }

    public function store(Request $request)
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business && $user->role !== 'superadmin') {
            return redirect()->route('admin.customcolors.index')->with('error', 'You must have an associated business to add custom colors.');
        }

        $request->validate([
            'name' => 'required|max:100',
            'hex' => ['required', 'regex:/^#([0-9A-Fa-f]{6})$/'],
            'active' => 'nullable|integer',
            'business_id' => 'nullable|integer',
        ]);

        try {
            $target_business_id = $business ? $business->id : 0;

            // If superadmin chooses to make it global
            if ($user->role === 'superadmin' && $request->has('is_global')) {
                $target_business_id = 0;
            }

            CustomColor::create([
                'business_id' => $target_business_id,
                'name' => trim($request->name),
                'hex' => strtoupper(trim($request->hex)),
                'active' => $request->has('active') ? 1 : 0,
            ]);

            return redirect()->route('admin.customcolors.index')->with('success', 'Color created successfully.');
        } catch (\Exception $e) {
            Log::error('Create color error: ' . $e->getMessage());
            return back()->withInput()->with('error', 'Could not create color. Possibly duplicate name or hex for this shop.');
        }
    }

    public function edit($id)
    {
        $user = Auth::user();
        $business = $user->business;

        $color = CustomColor::findOrFail($id);
        $is_global = ((int)$color->business_id === 0);

        if (!$is_global && (!$business || (int)$color->business_id !== (int)$business->id)) {
            return redirect()->route('admin.customcolors.index')->with('error', 'You do not have permission to edit this color.');
        }

        $can_edit = !$is_global && $business && ((int)$color->business_id === (int)$business->id);

        return view('admin.customcolors.edit', compact('color', 'is_global', 'can_edit', 'business'));
    }

    public function update(Request $request, $id)
    {
        $user = Auth::user();
        $business = $user->business;

        $color = CustomColor::findOrFail($id);
        $is_global = ((int)$color->business_id === 0);

        // Permission check: superadmin can edit anything. Admin can edit their own or global?
        // Original code: if ($is_global || !$business || (int)$color->business_id !== (int)$business->id)
        // This meant admins could NOT edit global colors.

        if ($user->role !== 'superadmin') {
            if ($is_global || !$business || (int)$color->business_id !== (int)$business->id) {
                return redirect()->route('admin.customcolors.index')->with('error', 'You cannot edit this color.');
            }
        }

        $request->validate([
            'name' => 'required|max:100',
            'hex' => ['required', 'regex:/^#([0-9A-Fa-f]{6})$/'],
            'active' => 'nullable|integer',
        ]);

        try {
            $color->update([
                'name' => trim($request->name),
                'hex' => strtoupper(trim($request->hex)),
                'active' => $request->has('active') ? 1 : 0,
            ]);

            return redirect()->route('admin.customcolors.index')->with('success', 'Updated color: ' . $color->name);
        } catch (\Exception $e) {
            Log::error('Edit color error: ' . $e->getMessage());
            return back()->withInput()->with('error', 'Could not update color.');
        }
    }

    public function toggle($id)
    {
        $user = Auth::user();
        $business = $user->business;

        $color = CustomColor::findOrFail($id);

        if ($user->role !== 'superadmin') {
            if (!$business || (int)$color->business_id !== (int)$business->id) {
                return redirect()->route('admin.customcolors.index')->with('error', 'You can only toggle colors for your own shop.');
            }
        }

        $color->active = !$color->active;
        $color->save();

        $status = $color->active ? 'Active' : 'Inactive';
        return redirect()->route('admin.customcolors.index')->with('success', 'Color "' . $color->name . '" is now ' . $status . '.');
    }
}
