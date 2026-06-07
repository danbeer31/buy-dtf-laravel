<x-mail::message>
# Your Order is Out for Delivery!

Hello {{ $order->business->contact_name }},

Your order #{{ $order->id }} is out for delivery and should arrive later today.

**Tracking Number:** {{ $order->tracking_number }}

<x-mail::button :url="'https://www.ups.com/track?tracknum=' . $order->tracking_number">
Track Your Package
</x-mail::button>

Thanks,<br>
{{ config('app.name') }}
</x-mail::message>
