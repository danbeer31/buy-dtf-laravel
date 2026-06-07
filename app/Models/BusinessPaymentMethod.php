<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;

class BusinessPaymentMethod extends FuelModel
{
    protected $table = 'business_paymentmethods';

    protected $fillable = [
        'business_id',
        'payment_method_id',
    ];

    public function business(): BelongsTo
    {
        return $this->belongsTo(Business::class);
    }

    public function paymentMethod(): BelongsTo
    {
        return $this->belongsTo(PaymentMethod::class);
    }
}
