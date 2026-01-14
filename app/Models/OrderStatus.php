<?php

namespace App\Models;

class OrderStatus extends FuelModel
{
    protected $table = 'order_statuses';

    protected $fillable = [
        'name',
        'color',
        'sort_order',
        'locked',
        'email',
    ];

    // FuelPHP model used MySQL timestamps (mysql_timestamp => true)
    public $timestamps = true;

    public static function get_sorted()
    {
        return self::orderBy('sort_order', 'asc')->get();
    }
}
