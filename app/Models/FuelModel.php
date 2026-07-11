<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

abstract class FuelModel extends Model
{
    protected $dateFormat = 'Y-m-d H:i:s';

    public function __construct(array $attributes = [])
    {
        parent::__construct($attributes);
        $conn = config('database.fuel_connection', env('FUEL_DB_CONNECTION', 'fuelmysql'));

        // Safety check: 'remotefuel' is the legacy connection that lacks schema updates.
        // If it's still being picked up, force it to 'fuelmysql'.
        if ($conn === 'remotefuel') {
            $conn = 'fuelmysql';
        }

        $this->connection = $conn;
    }
}
