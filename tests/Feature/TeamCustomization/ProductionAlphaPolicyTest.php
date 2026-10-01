<?php

namespace Tests\Feature\TeamCustomization;

use App\Http\Controllers\TeamCustomizationController;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\User;
use App\Services\NameNumberService;
use Mockery;
use PHPUnit\Framework\Attributes\PreserveGlobalState;
use PHPUnit\Framework\Attributes\RunInSeparateProcess;
use ReflectionMethod;
use Tests\TestCase;

class ProductionAlphaPolicyTest extends TestCase
{
    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_team_customization_source_is_not_mutated_and_threshold_is_deferred_to_production(): void
    {
        self::assertTrue(extension_loaded('imagick'));
        $email = 'team-alpha-'.bin2hex(random_bytes(5)).'@example.test';
        $business = Business::create([
            'business_name' => 'Team Alpha Test',
            'contact_name' => 'Team Customer',
            'email' => $email,
            'status' => 1,
        ]);
        $user = User::factory()->create([
            'email' => $email,
            'role' => 'customer',
            'fuel_business_id' => $business->id,
        ]);
        $this->actingAs($user);

        $sourceFixture = dirname(__DIR__, 2).'/Fixtures/ImageProcessing/antialiased-edges.png';
        $basename = 'team-alpha-'.bin2hex(random_bytes(5)).'.png';
        $sourcePath = public_path('uploads/images/'.$basename);
        if (! is_dir(dirname($sourcePath))) {
            mkdir(dirname($sourcePath), 0777, true);
        }
        copy($sourceFixture, $sourcePath);
        $sourceHash = hash_file('sha256', $sourcePath);

        try {
            $controller = new TeamCustomizationController(Mockery::mock(NameNumberService::class));
            $method = new ReflectionMethod($controller, 'attachToOrder');
            $result = $method->invoke($controller, [
                'full_path' => $sourcePath,
                'url' => '/uploads/images/'.$basename,
                'path' => 'uploads/images/'.$basename,
            ], [
                '__order_quantity' => 3,
                'data' => [],
            ]);

            self::assertTrue($result['success'] ?? false, $result['message'] ?? 'attach failed');
            $image = DtfImage::findOrFail($result['id']);
            self::assertSame($sourceHash, hash_file('sha256', $sourcePath));
            self::assertSame($sourceHash, $image->sha256_original);
            self::assertSame($sourceHash, $image->sha256_bitmap);
            self::assertSame(128, $image->productionAlphaThreshold());
            self::assertSame('public', data_get($image->item_meta, 'source_artwork.disk'));
            self::assertSame(0.02, (float) $image->width);
            self::assertSame(0.02, (float) $image->height);
            self::assertSame(3, (int) $image->quantity);
        } finally {
            if (is_file($sourcePath)) {
                unlink($sourcePath);
            }
        }
    }
}
