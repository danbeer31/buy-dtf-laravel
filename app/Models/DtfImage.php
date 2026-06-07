<?php

namespace App\Models;

use App\Services\GangSheetPricingService;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Facades\Schema;
use Exception;

class DtfImage extends FuelModel
{
    /**
     * Create a row using only columns that exist on the active connection/table.
     * This protects uploads when environments have schema drift.
     */
    public static function createUsingExistingColumns(array $attributes): self
    {
        $instance = new static();
        $columns = $instance->existingColumnsForTable();

        $filtered = array_filter(
            $attributes,
            static fn ($value, $key) => in_array($key, $columns, true),
            ARRAY_FILTER_USE_BOTH
        );

        return static::query()->create($filtered);
    }

    protected function existingColumnsForTable(): array
    {
        static $cache = [];

        $connection = $this->getConnectionName() ?: $this->getConnection()->getName();
        $table = $this->getTable();
        $cacheKey = $connection . '.' . $table;

        if (!isset($cache[$cacheKey])) {
            $cache[$cacheKey] = Schema::connection($connection)->getColumnListing($table);
        }

        return $cache[$cacheKey];
    }

    protected $table = 'dtfimages';

    protected $fillable = [
        'dtforder_id',
        'image',
        'thumbnail',
        'native_filename',
        'file_size',
        'sha256_original',
        'sha256_bitmap',
        'upload_mime',
        'item_type',
        'item_meta',
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
        'admin_unit_price',
        'admin_price_locked',
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
        'item_meta' => 'array',
        'width' => 'float',
        'height' => 'float',
        'width_ratio' => 'float',
        'height_ratio' => 'float',
        'orig_width' => 'float',
        'orig_height' => 'float',
        'quantity' => 'integer',
        'price' => 'float',
        'admin_unit_price' => 'float',
        'admin_price_locked' => 'integer',
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
        if ((int)($this->admin_price_locked ?? 0) === 1 && $this->admin_unit_price !== null) {
            return round((float)$this->admin_unit_price, 2);
        }

        if ($this->isGangSheet()) {
            $meta = $this->getGangSheetMeta();
            $sizeKey = (string)($meta['size_key'] ?? '');
            $qty = max(1, (int)$this->quantity);

            $price = app(GangSheetPricingService::class)->unitPrice($sizeKey, $qty);
            $this->price = $price;
            $this->save();

            return round($price, 2);
        }

        if (!$this->dtfOrder || !$this->dtfOrder->business || !$this->dtfOrder->business->settings) {
            throw new Exception('Unable to calculate price: Missing related business or rate information.');
        }

        $rate = $this->dtfOrder->business->settings->rate;

        if ($rate === null) {
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
        return (float)$this->width * (float)$this->height;
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

    public function isGangSheet(): bool
    {
        return $this->item_type === 'gang_sheet';
    }

    public function getGangSheetMeta(): array
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
