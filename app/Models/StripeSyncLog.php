<?php

namespace App\Models;

class StripeSyncLog extends FuelModel
{
    protected $table = 'stripe_sync_logs';

    protected $fillable = [
        'sync_type',
        'event_type',
        'stripe_id',
        'status',
        'message',
        'payload',
    ];

    protected $casts = [
        'payload' => 'json',
    ];

    public static function log($type, $status, $message = null, $stripeId = null, $eventType = null, $payload = null)
    {
        return self::create([
            'sync_type' => $type,
            'status' => $status,
            'message' => $message,
            'stripe_id' => $stripeId,
            'event_type' => $eventType,
            'payload' => $payload,
        ]);
    }
}
