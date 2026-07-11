<?php

return [
    'enabled' => filter_var(env('AUTH_ENABLE_FUEL_LEGACY', true), FILTER_VALIDATE_BOOL),
    'fuel_salt' => env('FUEL_AUTH_SALT'),
    'fuel_iterations' => (int) env('FUEL_AUTH_ITERATIONS', 10000),
];

