<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;

class PaymentInfo extends FuelModel
{
    protected $table = 'paymentinfos';

    protected $fillable = [
        'dtforder_id',
        'business_id',
        'processor',
        'processor_confirm',
        'stripe_charge_id',
        'qbo_payment_id',
        'qbo_invoice_numbers',
        'qbo_fee_expense_id',
        'amount',
        'stripe_fee',
        'notes',
        'status',
    ];

    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        'amount' => 'float',
    ];

    // FuelPHP model used UNIX timestamps (mysql_timestamp => false)
    public $timestamps = true;
    protected $dateFormat = 'U';

    public function stripePayoutEntries(): \Illuminate\Database\Eloquent\Relations\HasMany
    {
        return $this->hasMany(StripePayoutEntry::class, 'dtforder_id', 'dtforder_id');
    }

    public function dtfOrder(): BelongsTo
    {
        return $this->belongsTo(DtfOrder::class, 'dtforder_id');
    }

    public function business(): BelongsTo
    {
        return $this->belongsTo(Business::class, 'business_id');
    }
}
