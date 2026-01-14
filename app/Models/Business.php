<?php

namespace App\Models;

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

    public function user()
    {
        return $this->belongsTo(User::class, 'email', 'email');
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
}
