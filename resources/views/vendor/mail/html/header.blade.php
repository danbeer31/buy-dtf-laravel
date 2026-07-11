@props(['url', 'message' => null])
<tr>
<td class="header">
<a href="{{ $url }}" style="display: inline-block;">
@if($message && file_exists(public_path('assets/img/dtf_logo.svg')))
<img src="{{ $message->embed(public_path('assets/img/dtf_logo.svg')) }}" class="logo" alt="{{ config('app.name') }} Logo" style="max-width: 240px; height: auto;">
@else
<img src="{{ config('app.email_host') }}/assets/img/dtf_logo.svg" class="logo" alt="{{ config('app.name') }} Logo" style="max-width: 240px; height: auto;">
@endif
</a>
</td>
</tr>
