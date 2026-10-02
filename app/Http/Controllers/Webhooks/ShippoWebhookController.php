<?php

namespace App\Http\Controllers\Webhooks;

use App\Http\Controllers\Controller;
use App\Models\DtfOrder;
use App\Models\OrderStatus;
use App\Mail\OrderShipped;
use App\Mail\OrderOutForDelivery;
use App\Mail\OrderDelivered;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;

class ShippoWebhookController extends Controller
{
    /**
     * Handle Shippo webhooks.
     */
    public function handle(Request $request)
    {
        $event = $request->input('event');
        $data = $request->input('data');

        Log::info('Shippo webhook received', [
            'event' => $event,
        ]);

        if ($event === 'track_updated') {
            return $this->handleTrackUpdated($data);
        }

        return response()->json(['status' => 'ignored']);
    }

    protected function handleTrackUpdated($data)
    {
        $trackingNumber = $data['tracking_number'] ?? null;
        if (!$trackingNumber) {
            return response()->json(['error' => 'No tracking number'], 400);
        }

        $order = DtfOrder::where('tracking_number', $trackingNumber)->first();
        if (!$order) {
            Log::warning('Shippo webhook did not match an order', [
                'event' => 'track_updated',
            ]);
            return response()->json(['error' => 'Order not found'], 404);
        }

        $trackingStatus = $data['tracking_status']['status'] ?? null;

        Log::info('Shippo webhook updating order tracking status', [
            'order_id' => $order->id,
            'tracking_status' => $trackingStatus,
        ]);

        switch ($trackingStatus) {
            case 'TRANSIT':
                // Update to "in transit" (ID 11)
                if ($order->status != 11) {
                    $order->update(['status' => 11]);
                    // Only send shipped email if it was previously not shipped
                    // But usually TRANSIT follows Shipped (ID 4)
                    // We can keep sending the Shipped email if that's what's expected for transit start
                    $this->sendEmail($order, OrderShipped::class);
                }
                break;

            case 'OUT_FOR_DELIVERY':
                // Update to "out for delivery" (ID 12)
                if ($order->status != 12) {
                    $order->update(['status' => 12]);
                    $this->sendEmail($order, OrderOutForDelivery::class);
                }
                break;

            case 'DELIVERED':
                // Update to "delivered" (ID 13)
                if ($order->status != 13) {
                    $order->update(['status' => 13]);
                    $this->sendEmail($order, OrderDelivered::class);
                }
                break;
        }

        return response()->json(['status' => 'success']);
    }

    protected function sendEmail($order, $mailableClass)
    {
        try {
            if ($order->business && $order->business->email) {
                Mail::to($order->business->email)->send(new $mailableClass($order));
                Log::info('Shippo tracking email sent', [
                    'order_id' => $order->id,
                    'mailable' => $mailableClass,
                ]);
            }
        } catch (\Exception $e) {
            Log::error('Shippo tracking email failed', [
                'order_id' => $order->id,
                'exception_type' => $e::class,
                'exception_code' => $e->getCode(),
            ]);
        }
    }
}
