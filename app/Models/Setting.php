<?php

namespace App\Models;

class Setting extends FuelModel
{
    protected $table = 'settings';

    protected $fillable = [
        'key',
        'value',
    ];

    public static function get(string $key, $default = null)
    {
        $setting = self::where('key', $key)->first();
        return $setting ? $setting->value : $default;
    }
}
