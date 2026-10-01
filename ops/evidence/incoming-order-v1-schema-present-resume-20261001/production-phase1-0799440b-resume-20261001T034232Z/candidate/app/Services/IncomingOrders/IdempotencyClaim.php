<?php

namespace App\Services\IncomingOrders;

use App\Models\IncomingOrderJob;

class IdempotencyClaim
{
    public function __construct(
        public readonly string $outcome,
        public readonly IncomingOrderJob $job,
        public readonly ?string $owner = null,
        public readonly ?string $expiredOwner = null,
        public readonly ?int $retryAfter = null,
    ) {}
}
