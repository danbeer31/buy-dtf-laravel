<?php

namespace App\Models;

use Illuminate\Contracts\Auth\MustVerifyEmail;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Foundation\Auth\User as Authenticatable;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Notifications\Notifiable;

class User extends Authenticatable implements MustVerifyEmail
{
    /** @use HasFactory<\Database\Factories\UserFactory> */
    use HasFactory, Notifiable;

    /**
     * The connection name for the model.
     *
     * @var string|null
     */
    protected $connection = 'mysql';

    /**
     * The attributes that are mass assignable.
     *
     * @var list<string>
     */
    protected $fillable = [
        'name',
        'email',
        'password',
        'role',
        'fuel_business_id',
        'password_reset_required',
    ];

    /**
     * The attributes that should be hidden for serialization.
     *
     * @var list<string>
     */
    protected $hidden = [
        'password',
        'remember_token',
    ];

    /**
     * Get the attributes that should be cast.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'email_verified_at' => 'datetime',
            'password' => 'hashed',
            'password_reset_required' => 'boolean',
        ];
    }

    public function business()
    {
        if (!empty($this->fuel_business_id)) {
            return $this->belongsTo(Business::class, 'fuel_business_id');
        }

        // Backward compatibility while migrating away from email linkage.
        return $this->hasOne(Business::class, 'email', 'email');
    }

    public function businessMemberships(): HasMany
    {
        return $this->hasMany(BusinessUser::class);
    }

    public function businesses(): Builder
    {
        $ids = $this->businessMemberships()
            ->where('is_active', true)
            ->pluck('business_id');

        if ($ids->isEmpty()) {
            return Business::query()->whereRaw('1=0');
        }

        return Business::query()->whereIn('id', $ids);
    }

    public function isAdmin(): bool
    {
        return $this->role === 'admin' || $this->role === 'superadmin';
    }
}
