<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;

class PaymentInfo extends FuelModel
{
    protected $table = 'paymentinfos';

    protected $fillable = [
        'dtforder_id',
        'processor',
        'processor_confirm',
        'amount',
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

    public function dtfOrder(): BelongsTo
    {
        return $this->belongsTo(DtfOrder::class, 'dtforder_id');
    }
}
