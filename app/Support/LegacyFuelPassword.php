<?php

namespace App\Support;

final class LegacyFuelPassword
{
    public static function check(string $plain, string $storedHash): bool
    {
        $salt = (string) config('auth_legacy.fuel_salt');
        $iterations = (int) config('auth_legacy.fuel_iterations', 10000);

        if ($salt === '' || $iterations <= 0 || $storedHash === '') {
            return false;
        }

        $legacyHash = base64_encode(hash_pbkdf2(
            'sha256',
            $plain,
            $salt,
            $iterations,
            32,
            true
        ));

        return hash_equals($storedHash, $legacyHash);
    }
}

