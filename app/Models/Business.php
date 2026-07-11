<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Relations\HasOne;

class Business extends FuelModel
{
    protected $fillable = [
        'user_id',
        'business_name',
        'contact_name',
        'email',
        'phone',
        'address',
        'address2',
        'city',
        'state',
        'zip',
        'qbo_customer_id',
        'status',
        'tax_exempt',
        'tax_number',
        'confirmation_code',
    ];

    public $timestamps = true;

    protected $casts = [
        'created_at' => 'datetime',
        'updated_at' => 'datetime',
        'tax_exempt' => 'boolean',
    ];

    public function user(): HasOne
    {
        return $this->hasOne(User::class, 'fuel_business_id', 'id');
    }

    public function users(): Builder
    {
        $ids = BusinessUser::query()
            ->where('business_id', $this->id)
            ->where('is_active', true)
            ->pluck('user_id');

        if ($ids->isEmpty()) {
            return User::query()->whereRaw('1=0');
        }

        return User::query()->whereIn('id', $ids);
    }

    public function settings()
    {
        return $this->hasOne(BusinessSetting::class);
    }

    public function dtfOrders()
    {
        return $this->hasMany(DtfOrder::class);
    }

    public function open_order()
    {
        return $this->dtfOrders()->where('status', 1)->first();
    }

    public function paymentMethods()
    {
        return $this->belongsToMany(PaymentMethod::class, 'business_paymentmethods');
    }
}
