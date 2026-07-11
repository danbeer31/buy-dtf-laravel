<?php

namespace App\Services;

use InvalidArgumentException;

class GangSheetPricingService
{
    public const PRICING_VERSION = 'gang_sheet_v1_2026_03_23';

    /**
     * @var array<string, array{width: float, length: float, base_price: float}>
     */
    private const SIZE_MAP = [
        '22x24' => ['width' => 22.0, 'length' => 24.0, 'base_price' => 15.0],
        '22x36' => ['width' => 22.0, 'length' => 36.0, 'base_price' => 22.0],
        '22x48' => ['width' => 22.0, 'length' => 48.0, 'base_price' => 29.0],
        '22x60' => ['width' => 22.0, 'length' => 60.0, 'base_price' => 36.0],
        '22x72' => ['width' => 22.0, 'length' => 72.0, 'base_price' => 42.0],
        '22x84' => ['width' => 22.0, 'length' => 84.0, 'base_price' => 48.0],
        '22x96' => ['width' => 22.0, 'length' => 96.0, 'base_price' => 55.0],
    ];

    /**
     * @return array<string, array{width: float, length: float, base_price: float}>
     */
    public function sizes(): array
    {
        return self::SIZE_MAP;
    }

    public function unitPrice(string $sizeKey, int $quantity): float
    {
        $sizeKey = strtolower(trim($sizeKey));
        if (!isset(self::SIZE_MAP[$sizeKey])) {
            throw new InvalidArgumentException('Unsupported gang sheet size.');
        }

        $quantity = max(1, $quantity);
        if ($sizeKey !== '22x96') {
            return self::SIZE_MAP[$sizeKey]['base_price'];
        }

        if ($quantity >= 10) {
            return 48.0;
        }
        if ($quantity >= 6) {
            return 50.0;
        }
        if ($quantity >= 3) {
            return 52.0;
        }

        return 55.0;
    }
}

