<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ApiAssetRecord extends FuelModel
{
    protected $table = 'api_asset_records';

    protected $guarded = [];

    protected $casts = [
        'bytes' => 'integer',
        'retention_enabled' => 'boolean',
        'retention_days' => 'integer',
        'expires_at' => 'datetime',
        'customer_deleted_at' => 'datetime',
        'purged_at' => 'datetime',
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];

    public function incomingOrderJob(): BelongsTo
    {
        return $this->belongsTo(IncomingOrderJob::class);
    }
}
