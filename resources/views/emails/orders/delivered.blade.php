<x-mail::message>
# Your Order has been Delivered!

Hello {{ $order->business->contact_name }},

Your order #{{ $order->id }} has been delivered. We hope you enjoy your purchase!

**Tracking Number:** {{ $order->tracking_number }}

<x-mail::button :url="'https://www.ups.com/track?tracknum=' . $order->tracking_number">
View Tracking Details
</x-mail::button>

Thanks,<br>
{{ config('app.name') }}
</x-mail::message>
