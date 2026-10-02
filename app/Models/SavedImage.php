<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SavedImage extends FuelModel
{
    protected $table = 'savedimages';

    protected $fillable = [
        'business_id',
        'image',
        'thumbnail',
        'image_name',
        'image_notes',
        'item_meta',
        'width',
        'height',
        'date_uploaded',
    ];

    protected $casts = [
        'item_meta' => 'array',
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

    public function hasItemMetadataSnapshot(): bool
    {
        return $this->getRawOriginal('item_meta') !== null;
    }

    public function getItemMetadata(): array
    {
        $meta = $this->item_meta;

        if (is_array($meta)) {
            return $meta;
        }

        if (is_string($meta) && $meta !== '') {
            $decoded = json_decode($meta, true);

            return is_array($decoded) ? $decoded : [];
        }

        return [];
    }
}
