<?php

namespace App\Exceptions;

use RuntimeException;

class JobLabelValidationException extends RuntimeException
{
    public function __construct(public readonly string $reason)
    {
        parent::__construct($reason);
    }
}
