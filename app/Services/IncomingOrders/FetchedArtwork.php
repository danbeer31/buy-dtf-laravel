<?php

namespace App\Services\IncomingOrders;

class FetchedArtwork
{
    public function __construct(
        public readonly string $temporaryPath,
        public readonly string $approvedHost,
        public readonly int $bytes,
        public readonly ?string $declaredContentType,
    ) {}
}
