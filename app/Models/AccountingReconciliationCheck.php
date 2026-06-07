<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;

class AccountingReconciliationCheck extends FuelModel
{
    protected $table = 'accounting_reconciliation_checks';

    protected $fillable = [
        'business_id',
        'provider',
        'scope',
        'as_of_date',
        'currency',
        'expected_holding_amount_cents',
        'actual_holding_amount_cents',
        'difference_amount_cents',
        'status',
        'tolerance_cents',
        'notes',
        'meta',
        'ran_at',
    ];

    protected $casts = [
        'as_of_date' => 'date',
        'meta' => 'array',
        'ran_at' => 'datetime',
    ];

    public function business(): BelongsTo
    {
        return $this->belongsTo(Business::class);
    }
}

