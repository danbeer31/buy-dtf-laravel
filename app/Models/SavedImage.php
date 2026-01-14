<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SavedImage extends FuelModel
{
    protected $table = 'savedimages';

    protected $fillable = [
        'business_id',
        'image',
        'image_name',
        'image_notes',
        'width',
        'height',
        'date_uploaded',
    ];

    protected $casts = [
        'width' => 'float',
        'height' => 'float',
    ];

    public $timestamps = true;

    public function setDateUploadedAttribute($value)
    {
        $this->attributes['date_uploaded'] = $value instanceof \DateTimeInterface
            ? $value->format('Y-m-d H:i:s')
            : (is_numeric($value) ? date('Y-m-d H:i:s', $value) : $value);
    }

    public function getDateUploadedAttribute($value)
    {
        return $value ? \Illuminate\Support\Carbon::parse($value) : null;
    }

    public function business(): BelongsTo
    {
        return $this->belongsTo(Business::class);
    }
}
