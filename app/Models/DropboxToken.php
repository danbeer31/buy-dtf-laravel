<?php

namespace App\Models;

class DropboxToken extends FuelModel
{
    protected $table = 'dropbox_tokens';

    protected $fillable = [
        'access_token',
        'token_type',
        'uid',
        'account_id',
        'scope',
        'expires_in',
        'refresh_token',
        'updated_at',
    ];

    public $timestamps = false;
}
