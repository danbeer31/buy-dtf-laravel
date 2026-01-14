<?php

namespace App\Models;

class PaymentMethod extends FuelModel
{
    protected $table = 'paymentmethods';

    protected $fillable = [
        'method_name',
        'payment_controller',
        'description',
        'message',
    ];

    // FuelPHP model used MySQL timestamps (mysql_timestamp => true)
    public $timestamps = true;
}
