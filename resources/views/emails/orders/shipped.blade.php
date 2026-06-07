<x-mail::message>
# Your Order has Shipped!

Hello {{ $order->business->contact_name }},

Good news! Your order #{{ $order->id }} from {{ config('app.name') }} has been shipped.

**Tracking Number:** {{ $order->tracking_number }}

<x-mail::button :url="'https://www.ups.com/track?tracknum=' . $order->tracking_number">
Track Your Package
</x-mail::button>

Thanks,<br>
{{ config('app.name') }}
</x-mail::message>
