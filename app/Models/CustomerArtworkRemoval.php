<?php

namespace App\Models;

class CustomerArtworkRemoval extends FuelModel
{
    protected $table = 'customer_artwork_removals';

    protected $guarded = [];

    protected $casts = [
        'business_id' => 'integer',
        'customer_deleted_at' => 'datetime',
        'purged_at' => 'datetime',
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];
}
