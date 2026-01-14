<?php

namespace App\Models;

class BusinessSetting extends FuelModel
{
    protected $fillable = [
        'business_id',
        'rate',
    ];

    public function business()
    {
        return $this->belongsTo(Business::class);
    }
}
