<button {{ $attributes->merge(['type' => 'submit', 'class' => 'btn btn-warning fw-bold text-uppercase tracking-wider shadow-sm']) }}>
    {{ $slot }}
</button>
