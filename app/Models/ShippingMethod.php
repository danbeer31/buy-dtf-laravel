<?php

namespace App\Models;

class ShippingMethod extends FuelModel
{
    protected $table = 'shippingmethods';

    protected $fillable = [
        'shipping_method',
        'shipping_class',
        'description',
        'message',
    ];

    // FuelPHP model used MySQL timestamps (mysql_timestamp => true)
    public $timestamps = true;
}
