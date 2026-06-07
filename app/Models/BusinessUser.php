<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class BusinessUser extends Model
{
    protected $connection = 'mysql';

    protected $table = 'business_user';

    protected $fillable = [
        'business_id',
        'user_id',
        'role',
        'is_active',
        'invited_by',
    ];

    protected $casts = [
        'is_active' => 'boolean',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
