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

        $global_colors = CustomColor::where('business_id', 0)
            ->orderBy('name', 'asc')
            ->get();

        $shop_colors = collect();
        if ($business) {
            $shop_colors = CustomColor::where('business_id', $business->id)
                ->orderBy('name', 'asc')
                ->get();
        }

        return view('admin.customcolors.index', compact('global_colors', 'shop_colors', 'business'));
    }

    public function create()
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            return redirect()->route('admin.customcolors.index')->with('error', 'You must have an associated business to add custom colors.');
        }

        return view('admin.customcolors.create');
    }

    public function store(Request $request)
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            return redirect()->route('admin.customcolors.index')->with('error', 'You must have an associated business to add custom colors.');
        }

        $request->validate([
            'name' => 'required|max:100',
            'hex' => ['required', 'regex:/^#([0-9A-Fa-f]{6})$/'],
            'active' => 'nullable|integer',
        ]);

        try {
            CustomColor::create([
                'business_id' => $business->id,
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

        if ($is_global || !$business || (int)$color->business_id !== (int)$business->id) {
            return redirect()->route('admin.customcolors.index')->with('error', 'You cannot edit this color.');
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

        if (!$business) {
            return redirect()->route('admin.customcolors.index')->with('error', 'You must have an associated business to toggle colors.');
        }

        $color = CustomColor::findOrFail($id);

        if ((int)$color->business_id !== (int)$business->id) {
            return redirect()->route('admin.customcolors.index')->with('error', 'You can only toggle colors for your own shop.');
        }

        $color->active = !$color->active;
        $color->save();

        $status = $color->active ? 'Active' : 'Inactive';
        return redirect()->route('admin.customcolors.index')->with('success', 'Color "' . $color->name . '" is now ' . $status . '.');
    }
}
