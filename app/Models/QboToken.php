<?php

namespace App\Models;

class QboToken extends FuelModel
{
    protected $table = 'qbo_tokens';

    protected $fillable = [
        'access_token',
        'refresh_token',
        'realm_id',
        'expires_in',
        'x_refresh_token_expires_in',
    ];

    public $timestamps = true;
    const CREATED_AT = null;

    protected $casts = [
        'expires_in' => 'integer',
        'x_refresh_token_expires_in' => 'integer',
        'updated_at' => 'datetime',
    ];

    public static function getTokenRecord()
    {
        return self::first();
    }

    public function isAccessTokenExpired()
    {
        return ($this->expires_in - time()) <= 0;
    }

    public function isRefreshTokenExpired()
    {
        return ($this->x_refresh_token_expires_in - time()) <= 0;
    }
}
