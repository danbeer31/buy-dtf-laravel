<?php

namespace App\Models;

class Template extends FuelModel
{
    protected $table = 'templates';

    protected $fillable = [
        'name',
        'public_name',
        'preview_image',
        'description',
        'slug',
        'json_config',
        'active',
    ];

    public $timestamps = true;

    protected $casts = [
        'active' => 'boolean',
        'json_config' => 'array',
    ];

    public function blocks()
    {
        return $this->hasMany(TemplateBlock::class);
    }
}
