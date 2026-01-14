<button {{ $attributes->merge(['type' => 'submit', 'class' => 'btn btn-danger fw-bold text-uppercase tracking-wider shadow-sm']) }}>
    {{ $slot }}
</button>
