<?php

namespace App\Services\IncomingOrders;

class InspectedArtwork
{
    public function __construct(
        public readonly string $path,
        public readonly string $sha256,
        public readonly int $bytes,
        public readonly string $format,
        public readonly string $mime,
        public readonly int $widthPx,
        public readonly int $heightPx,
    ) {}
}
