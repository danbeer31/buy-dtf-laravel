<x-mail::message>
# New Order Placed

A new order was placed.

**Order ID:** #{{ $order->id }}  
**Business:** {{ optional($order->business)->business_name ?? 'Unknown' }}  
**Customer Email:** {{ optional($order->business)->email ?? 'Unknown' }}  
**Total:** ${{ number_format((float) ($order->total_price ?? 0), 2) }}

<x-mail::button :url="url('/admin/orders/' . $order->id)">
View Order
</x-mail::button>

</x-mail::message>
