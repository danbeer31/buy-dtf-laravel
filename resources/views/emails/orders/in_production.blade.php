<x-mail::message>
# Order In Production

Good news. **Order #{{ $order->id }}** is now in production.

We will send another update when it is ready for pickup or shipped.

Thanks,  
{{ config('app.name') }}
</x-mail::message>
