<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class StripePayoutEntry extends FuelModel
{
    protected $table = 'stripe_payout_entries';

    protected $fillable = [
        'stripe_payout_id',
        'stripe_transaction_id',
        'type',
        'gross',
        'fee',
        'net',
        'dtforder_id',
        'qbo_expense_id',
        'qbo_refund_id',
        'notes',
    ];

    protected $casts = [
        'gross' => 'decimal:2',
        'fee' => 'decimal:2',
        'net' => 'decimal:2',
    ];

    public function payout()
    {
        return $this->belongsTo(StripePayout::class, 'stripe_payout_id');
    }

    public function dtfOrder()
    {
        return $this->belongsTo(DtfOrder::class, 'dtforder_id');
    }
}
