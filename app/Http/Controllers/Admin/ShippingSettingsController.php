<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\Setting;
use Illuminate\Http\Request;

class ShippingSettingsController extends Controller
{
    public function index()
    {
        $ups_services = [
            'ups_ground' => 'UPS Ground',
            'ups_ground_saver' => 'UPS Ground Saver',
            'ups_2_day' => 'UPS 2nd Day Air (Token 1)',
            'ups_2nd_day_air' => 'UPS 2nd Day Air (Token 2)',
            'ups_second_day_air' => 'UPS 2nd Day Air (Token 3)',
            'ups_next_day_air' => 'UPS Next Day Air',
            'ups_next_day_air_saver' => 'UPS Next Day Air Saver',
        ];

        $allowed_services = json_decode(Setting::get('ups_allowed_services', '[]'), true);
        if (empty($allowed_services)) {
            $allowed_services = array_keys($ups_services);
        }

        $free_shipping_threshold = Setting::get('free_shipping_threshold', 500);
        $free_shipping_services = json_decode(Setting::get('free_shipping_services', '["ups_ground", "ups_ground_saver"]'), true);

        $pickup_enabled = Setting::get('shipping_pickup_enabled', '0');
        $pickup_message = Setting::get('shipping_pickup_message', 'Local Pick-up');

        return view('admin.shipping.index', compact(
            'ups_services',
            'allowed_services',
            'free_shipping_threshold',
            'free_shipping_services',
            'pickup_enabled',
            'pickup_message'
        ));
    }

    public function update(Request $request)
    {
        $validated = $request->validate([
            'allowed_services' => 'array',
            'free_shipping_threshold' => 'required|numeric|min:0',
            'free_shipping_services' => 'array',
            'pickup_enabled' => 'boolean',
            'pickup_message' => 'nullable|string',
        ]);

        $this->setSetting('ups_allowed_services', json_encode($validated['allowed_services'] ?? []));
        $this->setSetting('free_shipping_threshold', $validated['free_shipping_threshold']);
        $this->setSetting('free_shipping_services', json_encode($validated['free_shipping_services'] ?? []));
        $this->setSetting('shipping_pickup_enabled', $request->has('pickup_enabled') ? '1' : '0');
        $this->setSetting('shipping_pickup_message', $validated['pickup_message'] ?? 'Local Pick-up');

        return redirect()->back()->with('success', 'Shipping settings updated successfully.');
    }

    private function setSetting($key, $value)
    {
        Setting::updateOrCreate(['key' => $key], ['value' => $value]);
    }
}
