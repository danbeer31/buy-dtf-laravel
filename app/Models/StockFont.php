<?php

namespace App\Models;

class StockFont extends FuelModel
{
    protected $table = 'stock_fonts';

    protected $fillable = [
        'name',
        'file_name',
        'active',
        'sort_order',
    ];

    public $timestamps = true;

    protected $casts = [
        'active' => 'boolean',
    ];
}
