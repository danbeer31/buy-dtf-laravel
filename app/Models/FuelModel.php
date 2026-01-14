<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

abstract class FuelModel extends Model
{
    protected $dateFormat = 'Y-m-d H:i:s';

    /**
     * The connection name for the model.
     *
     * @var string|null
     */
    protected $connection = 'fuelmysql';
}
