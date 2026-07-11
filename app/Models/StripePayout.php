<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class StripePayout extends FuelModel
{
    protected $table = 'stripe_payouts';

    protected $fillable = [
        'stripe_payout_id',
        'amount',
        'fee',
        'net',
        'currency',
        'status',
        'arrival_date',
        'description',
        'qbo_deposit_id',
        'qbo_transfer_id',
    ];

    protected $casts = [
        'arrival_date' => 'datetime',
        'amount' => 'decimal:2',
        'fee' => 'decimal:2',
        'net' => 'decimal:2',
    ];

    public function entries()
    {
        return $this->hasMany(StripePayoutEntry::class);
    }
}
