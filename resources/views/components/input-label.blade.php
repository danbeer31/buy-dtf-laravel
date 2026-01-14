@props(['value'])

<label {{ $attributes->merge(['class' => 'form-label fw-semibold text-dark small text-uppercase tracking-wider']) }}>
    {{ $value ?? $slot }}
</label>
