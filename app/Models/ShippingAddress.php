<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ShippingAddress extends FuelModel
{
    protected $table = 'shippingaddresses';

    protected $fillable = [
        'order_id',
        'name',
        'address1',
        'address2',
        'city',
        'state',
        'zip',
    ];

    // FuelPHP model used MySQL timestamps (mysql_timestamp => true)
    public $timestamps = true;

    public function order(): BelongsTo
    {
        return $this->belongsTo(DtfOrder::class, 'order_id');
    }
}
