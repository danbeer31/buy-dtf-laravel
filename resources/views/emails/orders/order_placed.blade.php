<x-mail::message>
# Order Received

Thanks for your order. We received **Order #{{ $order->id }}** and it is now in our queue.

**Order total:** ${{ number_format((float) ($order->total_price ?? 0), 2) }}  
**Date:** {{ optional($order->order_date)->format('M d, Y') ?? now()->format('M d, Y') }}

You will receive another update when your order moves into production.

Thanks,  
{{ config('app.name') }}
</x-mail::message>
