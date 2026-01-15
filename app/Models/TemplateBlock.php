<?php

namespace App\Models;

class TemplateBlock extends FuelModel
{
    protected $table = 'template_blocks';

    protected $fillable = [
        'template_id',
        'slot_name',
        'type',
        'sort_order',
    ];

    public $timestamps = true;

    public function template()
    {
        return $this->belongsTo(Template::class);
    }
}
