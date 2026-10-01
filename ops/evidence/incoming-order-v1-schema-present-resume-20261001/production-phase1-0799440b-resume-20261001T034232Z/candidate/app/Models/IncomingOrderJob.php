<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class IncomingOrderJob extends FuelModel
{
    protected $table = 'incoming_order_jobs';

    protected $guarded = [];

    protected $casts = [
        'attempt_count' => 'integer',
        'response_payload' => 'array',
        'job_label_required' => 'boolean',
        'job_label_metadata' => 'array',
        'art_width_in' => 'decimal:4',
        'art_height_in' => 'decimal:4',
        'production_attempt_count' => 'integer',
        'production_result' => 'array',
        'lease_expires_at' => 'datetime',
        'heartbeat_at' => 'datetime',
        'last_attempt_at' => 'datetime',
        'production_started_at' => 'datetime',
        'production_heartbeat_at' => 'datetime',
        'production_lease_expires_at' => 'datetime',
        'production_completed_at' => 'datetime',
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
    ];

    public function dtfImage(): BelongsTo
    {
        return $this->belongsTo(DtfImage::class, 'dtfimage_id');
    }

    public function assets(): HasMany
    {
        return $this->hasMany(ApiAssetRecord::class, 'incoming_order_job_id');
    }

    public function hasAcceptedJobCard(): bool
    {
        return in_array($this->job_label_status, ['accepted', 'rendered'], true)
            && is_array($this->job_label_metadata)
            && $this->job_label_fingerprint !== null;
    }
}
