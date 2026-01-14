<button {{ $attributes->merge(['type' => 'button', 'class' => 'btn btn-outline-secondary fw-bold text-uppercase tracking-wider shadow-sm']) }}>
    {{ $slot }}
</button>
