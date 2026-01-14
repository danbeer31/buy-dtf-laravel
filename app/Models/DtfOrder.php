<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Exception;

class DtfOrder extends FuelModel
{
    protected $table = 'dtforders';

    protected $fillable = [
        'business_id',
        'order_date',
        'shipping_method_id',
        'payment_method_id',
        'weight',
        'price',
        'shipping_cost',
        'total_price',
        'sales_tax',
        'square_inches',
        'linear_inches',
        'status',
        'qbo_invoice_id',
    ];

    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        'weight' => 'float',
        'price' => 'float',
        'shipping_cost' => 'float',
        'total_price' => 'float',
        'sales_tax' => 'float',
        'square_inches' => 'float',
        'linear_inches' => 'float',
    ];

    // FuelPHP model used UNIX timestamps (mysql_timestamp => false)
    public $timestamps = true;
    protected $dateFormat = 'U';

    public function setOrderDateAttribute($value)
    {
        $this->attributes['order_date'] = $value instanceof \DateTimeInterface
            ? $value->format('Y-m-d')
            : $value;
    }

    public function getOrderDateAttribute($value)
    {
        return $value ? \Illuminate\Support\Carbon::parse($value) : null;
    }

    public function business(): BelongsTo
    {
        return $this->belongsTo(Business::class);
    }

    public function dtfImages(): HasMany
    {
        return $this->hasMany(DtfImage::class, 'dtforder_id');
    }

    public function shippingMethod(): BelongsTo
    {
        return $this->belongsTo(ShippingMethod::class, 'shipping_method_id');
    }

    public function paymentMethod(): BelongsTo
    {
        return $this->belongsTo(PaymentMethod::class, 'payment_method_id');
    }

    public function paymentInfo(): HasOne
    {
        return $this->hasOne(PaymentInfo::class, 'dtforder_id');
    }

    public function shippingAddress(): HasOne
    {
        return $this->hasOne(ShippingAddress::class, 'order_id');
    }

    public function orderStatus(): BelongsTo
    {
        return $this->belongsTo(OrderStatus::class, 'status');
    }

    public function get_total()
    {
        if ($this->dtfImages->isEmpty()) {
            return 0;
        }

        $total = 0;
        foreach ($this->dtfImages as $image) {
            $total += $image->get_total();
        }

        return round($total, 2);
    }

    public function get_invoice_total()
    {
        if ($this->dtfImages->isEmpty()) {
            return 0;
        }

        $total = 0;
        foreach ($this->dtfImages as $image) {
            $total += $image->get_total();
        }
        $total += $this->shipping_cost;

        return round($total, 2);
    }

    public function get_image_count()
    {
        return $this->dtfImages->count();
    }

    public function get_total_image_count()
    {
        return $this->dtfImages->sum('quantity');
    }

    public function calculate_weight($film_weight = 0.0003, $core_weight = 1.8)
    {
        $area = $this->calculate_area();
        if ($area === false) {
            return false;
        }

        $total_square_inches = $area['square_inches'];
        return ($total_square_inches * $film_weight) + $core_weight;
    }

    public function calculate_area($width = 22)
    {
        if ($this->dtfImages->isEmpty()) {
            return false;
        }

        $total_square_inches = 0;
        foreach ($this->dtfImages as $img) {
            $total_square_inches += $img->get_square_inches() * $img->quantity;
        }

        $result = [];
        $result['width'] = $width;
        $result['length'] = $total_square_inches / $width;
        $result['square_inches'] = $total_square_inches + ($result['length'] * 2);

        return $result;
    }

    public function isPaid()
    {
        if ($this->paymentInfo && $this->paymentInfo->status === 'complete') {
            return true;
        }

        // Helpers_QBO::isPaid($this) - this will need to be ported or handled later
        return false;
    }
}
