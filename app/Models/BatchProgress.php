<?php

namespace App\Models;

class BatchProgress extends FuelModel
{
    protected $table = 'customnames_batch_progress';

    protected $fillable = [
        'batch_id',
        'row_index',
        'stage',
        'message',
        'preview_url',
        'error',
    ];

    public $timestamps = true;

    public static function upsert($batchId, $rowIndex, array $data)
    {
        return static::updateOrCreate(
            ['batch_id' => $batchId, 'row_index' => $rowIndex],
            $data
        );
    }
}
