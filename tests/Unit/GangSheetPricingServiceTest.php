<?php

namespace Tests\Unit;

use App\Services\GangSheetPricingService;
use InvalidArgumentException;
use PHPUnit\Framework\TestCase;

class GangSheetPricingServiceTest extends TestCase
{
    public function test_non_22x96_uses_fixed_price(): void
    {
        $svc = new GangSheetPricingService();
        $this->assertSame(22.0, $svc->unitPrice('22x36', 1));
        $this->assertSame(22.0, $svc->unitPrice('22x36', 50));
    }

    public function test_22x96_tiers_are_applied(): void
    {
        $svc = new GangSheetPricingService();
        $this->assertSame(55.0, $svc->unitPrice('22x96', 1));
        $this->assertSame(55.0, $svc->unitPrice('22x96', 2));
        $this->assertSame(52.0, $svc->unitPrice('22x96', 3));
        $this->assertSame(52.0, $svc->unitPrice('22x96', 5));
        $this->assertSame(50.0, $svc->unitPrice('22x96', 6));
        $this->assertSame(50.0, $svc->unitPrice('22x96', 9));
        $this->assertSame(48.0, $svc->unitPrice('22x96', 10));
    }

    public function test_invalid_size_throws(): void
    {
        $this->expectException(InvalidArgumentException::class);
        (new GangSheetPricingService())->unitPrice('24x24', 1);
    }
}

