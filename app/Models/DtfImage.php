<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Exception;

class DtfImage extends FuelModel
{
    protected $table = 'dtfimages';

    protected $fillable = [
        'dtforder_id',
        'image',
        'native_filename',
        'file_size',
        'sha256_original',
        'sha256_bitmap',
        'image_name',
        'image_notes',
        'width',
        'height',
        'width_ratio',
        'height_ratio',
        'orig_width',
        'orig_height',
        'quantity',
        'price',
        'date_uploaded',
        'production',
    ];

    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        'file_size' => 'integer',
        'width' => 'float',
        'height' => 'float',
        'width_ratio' => 'float',
        'height_ratio' => 'float',
        'orig_width' => 'float',
        'orig_height' => 'float',
        'quantity' => 'integer',
        'price' => 'float',
        'production' => 'integer',
    ];

    // FuelPHP model used UNIX timestamps (mysql_timestamp => false)
    public $timestamps = true;
    protected $dateFormat = 'U';

    public function setDateUploadedAttribute($value)
    {
        $this->attributes['date_uploaded'] = $value instanceof \DateTimeInterface
            ? $value->format('Y-m-d H:i:s')
            : (is_numeric($value) ? date('Y-m-d H:i:s', $value) : (is_string($value) ? $value : null));
    }

    public function getDateUploadedAttribute($value)
    {
        return $value ? \Illuminate\Support\Carbon::parse($value) : null;
    }

    public function dtfOrder(): BelongsTo
    {
        return $this->belongsTo(DtfOrder::class, 'dtforder_id');
    }

    public function get_price()
    {
        if (!$this->dtfOrder || !$this->dtfOrder->business || !$this->dtfOrder->business->settings) {
            throw new Exception('Unable to calculate price: Missing related business or rate information.');
        }

        $rate = $this->dtfOrder->business->settings->rate;

        if (!$rate) {
            throw new Exception('Unable to calculate price: Business rate is not set.');
        }

        $square_inches = $this->get_square_inches();
        $price = $square_inches * $rate;
        $this->price = $price;
        $this->save();

        return round($price, 2);
    }

    public function get_square_inches()
    {
        return ($this->width + 0.25) * ($this->height + 0.25);
    }

    public function get_total()
    {
        if (!$this->quantity || $this->quantity <= 0) {
            throw new Exception('Unable to calculate total: Quantity must be greater than zero.');
        }

        $price_per_image = $this->get_price();
        $total = $price_per_image * $this->quantity;

        return round($total, 2);
    }
}
