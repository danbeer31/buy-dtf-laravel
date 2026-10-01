<?php

namespace App\Exceptions;

use RuntimeException;

class IncomingOrderValidationException extends RuntimeException
{
    public function __construct(
        public readonly string $errorCode,
        public readonly string $reason,
        public readonly int $status = 422,
    ) {
        parent::__construct($reason);
    }
}
