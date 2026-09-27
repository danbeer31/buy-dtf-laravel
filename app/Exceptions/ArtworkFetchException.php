<?php

namespace App\Exceptions;

use RuntimeException;

class ArtworkFetchException extends RuntimeException
{
    public function __construct(
        public readonly string $reason,
        public readonly bool $retryable = false,
    ) {
        parent::__construct($reason);
    }
}
