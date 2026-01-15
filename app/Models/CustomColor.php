<?php

namespace App\Models;

class CustomColor extends FuelModel
{
    protected $table = 'custom_colors';

    protected $fillable = [
        'business_id',
        'name',
        'hex',
        'active',
    ];

    public $timestamps = true;

    protected $casts = [
        'active' => 'boolean',
    ];

    public function business()
    {
        return $this->belongsTo(Business::class);
    }
}
