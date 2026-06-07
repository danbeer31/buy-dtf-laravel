<x-mail::message>
# Your Order is Ready for Pickup!

Hello {{ $order->business->contact_name }},

Great news! Your order #{{ $order->id }} is ready for local pickup.

You can pick up your order at our location during business hours.

**Location:**
{{ config('services.shippo.from_address.street1') }}
{{ config('services.shippo.from_address.city') }}, {{ config('services.shippo.from_address.state') }} {{ config('services.shippo.from_address.zip') }}

Thanks,<br>
{{ config('app.name') }}
</x-mail::message>
