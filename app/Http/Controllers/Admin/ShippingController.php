<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\DtfOrder;
use App\Models\Setting;
use App\Services\ShippoService;
use App\Mail\OrderShipped;
use App\Mail\OrderReadyForPickup;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;

class ShippingController extends Controller
{
    protected $shippo;

    public function __construct(ShippoService $shippo)
    {
        $this->shippo = $shippo;
    }

    /**
     * Display shipping management for a specific order.
     */
    public function orderShipping(DtfOrder $order)
    {
        $order->load(['business', 'shippingAddress', 'orderStatus']);

        // If it's a pickup order, we might handle it differently
        $isPickup = ($order->shipping_method === Setting::get('shipping_pickup_message', 'Local Pick-up'));

        return view('admin.shipping.order', compact('order', 'isPickup'));
    }

    /**
     * Fetch live rates for an order.
     */
    public function getRates(Request $request, DtfOrder $order)
    {
        try {
            $order->load('shippingAddress');
            $address = $order->shippingAddress;

            if (!$address) {
                return response()->json(['error' => 'No shipping address found for this order.'], 422);
            }

            $toAddr = [
                'name' => $address->name,
                'street1' => $address->address1,
                'street2' => $address->address2,
                'city' => $address->city,
                'state' => $address->state,
                'zip' => $address->zip,
                'country' => 'US',
            ];

            // Weight is in lbs from user input/DB, Shippo expects oz
            $weightLbs = $request->query('weight', $order->weight ?: 1);
            $weightOz = $weightLbs * 16;

            $rates = $this->shippo->quoteUpsRates($toAddr, $weightOz);

            return response()->json([
                'rates' => $rates['rates'] ?? [],
                'shipment_id' => $rates['shippo_shipment_id'] ?? null
            ]);

        } catch (\Exception $e) {
            Log::error('Admin Shipping Rates Error: ' . $e->getMessage());
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    /**
     * Purchase a label (create transaction).
     */
    public function createLabel(Request $request, DtfOrder $order)
    {
        $validated = $request->validate([
            'rate_id' => 'required|string',
        ]);

        try {
            $transaction = $this->shippo->createTransaction($validated['rate_id'], [
                'async' => false,
            ]);

            if ($transaction['status'] === 'SUCCESS') {
                $order->update([
                    'shippo_transaction_id' => $transaction['object_id'],
                    'tracking_number' => $transaction['tracking_number'],
                    'label_url' => $transaction['label_url'],
                    'status' => 4, // Status 4 = Shipped
                ]);

                // Send Shipped Email
                try {
                    if ($order->business && $order->business->email) {
                        Mail::to($order->business->email)->send(new OrderShipped($order));
                    }
                } catch (\Exception $e) {
                    Log::error('Admin Shipping: Failed to send shipped email for order #' . $order->id . ': ' . $e->getMessage());
                }

                return response()->json([
                    'success' => true,
                    'tracking_number' => $transaction['tracking_number'],
                    'label_url' => $transaction['label_url']
                ]);
            } else {
                return response()->json([
                    'success' => false,
                    'message' => 'Shippo transaction failed: ' . json_encode($transaction['messages'])
                ], 422);
            }

        } catch (\Exception $e) {
            Log::error('Admin Shipping Label Error: ' . $e->getMessage());
            return response()->json(['error' => $e->getMessage()], 500);
        }
    }

    /**
     * Mark order as ready for pickup.
     */
    public function readyForPickup(DtfOrder $order)
    {
        // Update status to "pickup ready" (ID 5)
        $order->update(['status' => 5]);

        // Trigger email notification
        try {
            if ($order->business && $order->business->email) {
                Mail::to($order->business->email)->send(new OrderReadyForPickup($order));
            }
        } catch (\Exception $e) {
            Log::error('Admin Shipping: Failed to send ready for pickup email for order #' . $order->id . ': ' . $e->getMessage());
        }

        return back()->with('success', 'Order marked as Ready for Pickup and notification sent.');
    }

    /**
     * Mark order as picked up (complete).
     */
    public function markAsPickedUp(DtfOrder $order)
    {
        // Update status to "pickup complete" (ID 14)
        $order->update(['status' => 14]);

        return back()->with('success', 'Order marked as Picked Up.');
    }
}
