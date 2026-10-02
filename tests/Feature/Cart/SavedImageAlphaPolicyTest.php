<?php

namespace Tests\Feature\Cart;

use App\Http\Controllers\CartController;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\SavedImage;
use App\Models\User;
use PHPUnit\Framework\Attributes\PreserveGlobalState;
use PHPUnit\Framework\Attributes\RunInSeparateProcess;
use Tests\TestCase;

class SavedImageAlphaPolicyTest extends TestCase
{
    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_uploaded_policy_survives_save_and_deletion_of_the_only_source_row(): void
    {
        self::assertTrue(extension_loaded('imagick'));
        [$user, $business] = $this->customerWithBusiness('durable');
        $controller = new class extends CartController
        {
            public function attachFixture(string $path, int $businessId): array
            {
                return $this->processAndAttach(
                    $path,
                    'image/png',
                    'antialiased-edges.png',
                    $businessId,
                    'saved-policy-durable',
                    (int) filesize($path),
                );
            }
        };
        $sourcePath = dirname(__DIR__, 2).'/Fixtures/ImageProcessing/antialiased-edges.png';
        $createdPaths = [];

        try {
            $result = $controller->attachFixture($sourcePath, $business->id);
            $source = DtfImage::findOrFail($result['dtfimage_id']);
            $sourceMetadata = $source->getItemMetadata();
            $createdPaths = [
                public_path(ltrim((string) $source->image, '/')),
                public_path(ltrim((string) $source->thumbnail, '/')),
                storage_path('app/private/'.data_get($sourceMetadata, 'source_artwork.path')),
            ];

            $this->actingAs($user)
                ->postJson(route('cart.save', ['id' => $source->id]))
                ->assertOk()
                ->assertJsonPath('success', true);

            $saved = SavedImage::where('business_id', $business->id)
                ->where('image', $source->image)
                ->firstOrFail();
            $this->assertTrue($saved->hasItemMetadataSnapshot());
            $this->assertSame($sourceMetadata, $saved->getItemMetadata());
            $this->assertSame(128, data_get($saved->getItemMetadata(), 'alpha_processing.threshold'));
            $this->assertSame(
                data_get($sourceMetadata, 'source_artwork.sha256'),
                data_get($saved->getItemMetadata(), 'source_artwork.sha256'),
            );

            $this->actingAs($user)
                ->postJson(route('cart.delete', ['id' => $source->id]))
                ->assertOk()
                ->assertJsonPath('success', true);
            $this->assertSame(0, DtfImage::where('image', $saved->image)->count());

            $reuse = $this->actingAs($user)
                ->postJson(route('cart.use_saved'), ['saved_id' => $saved->id])
                ->assertOk()
                ->assertJsonPath('success', true);
            $reused = DtfImage::findOrFail((int) $reuse->json('id'));

            $this->assertSame(128, $reused->productionAlphaThreshold());
            $this->assertSame($sourceMetadata, $reused->getItemMetadata());
            $this->assertSame($business->id, (int) $reused->dtfOrder->business_id);
            $this->assertSame(data_get($sourceMetadata, 'source_artwork.sha256'), $reused->sha256_original);
            $this->assertSame(data_get($sourceMetadata, 'source_artwork.mime'), $reused->upload_mime);
            $this->assertSame((int) data_get($sourceMetadata, 'source_artwork.bytes'), (int) $reused->file_size);
        } finally {
            foreach (array_unique(array_filter($createdPaths)) as $path) {
                if (is_file($path)) {
                    unlink($path);
                }
            }
        }
    }

    public function test_legacy_fallback_is_owner_scoped_and_selects_the_newest_matching_source(): void
    {
        [$owner, $ownerBusiness] = $this->customerWithBusiness('owner');
        [, $otherBusiness] = $this->customerWithBusiness('other');
        $sharedPath = '/uploads/images/shared-across-businesses.png';

        $ownerOld = $this->sourceImage($ownerBusiness, $sharedPath, 128, 'owner-old');
        $other = $this->sourceImage($otherBusiness, $sharedPath, 200, 'other');
        $ownerNewest = $this->sourceImage($ownerBusiness, $sharedPath, 144, 'owner-newest');
        $saved = SavedImage::create([
            'business_id' => $ownerBusiness->id,
            'image' => $sharedPath,
            'thumbnail' => '/uploads/images/thumbs/saved.png',
            'image_name' => 'Owner Saved Image',
            'width' => 2,
            'height' => 1,
            'item_meta' => null,
            'date_uploaded' => now(),
        ]);

        $response = $this->actingAs($owner)
            ->postJson(route('cart.use_saved'), ['saved_id' => $saved->id])
            ->assertOk()
            ->assertJsonPath('success', true);
        $reused = DtfImage::findOrFail((int) $response->json('id'));

        $this->assertSame(144, $reused->productionAlphaThreshold());
        $this->assertSame('owner-newest', data_get($reused->item_meta, 'source_artwork.path'));
        $this->assertSame($ownerNewest->thumbnail, $reused->thumbnail);
        $this->assertNotSame(data_get($other->item_meta, 'source_artwork.path'), data_get($reused->item_meta, 'source_artwork.path'));
        $this->assertNotSame($ownerOld->id, $ownerNewest->id);
    }

    public function test_legacy_saved_image_without_metadata_or_source_keeps_legacy_production_behavior(): void
    {
        [$user, $business] = $this->customerWithBusiness('legacy');
        $saved = SavedImage::create([
            'business_id' => $business->id,
            'image' => '/uploads/images/legacy-no-policy.png',
            'thumbnail' => '/uploads/images/legacy-no-policy.png',
            'image_name' => 'Legacy Saved Image',
            'width' => 3,
            'height' => 2,
            'item_meta' => null,
            'date_uploaded' => now(),
        ]);

        $this->assertFalse($saved->hasItemMetadataSnapshot());
        $response = $this->actingAs($user)
            ->postJson(route('cart.use_saved'), ['saved_id' => $saved->id])
            ->assertOk()
            ->assertJsonPath('success', true);
        $reused = DtfImage::findOrFail((int) $response->json('id'));

        $this->assertNull($reused->productionAlphaThreshold());
        $this->assertSame([], $reused->getItemMetadata());
        $this->assertSame('legacy', $reused->productionAlphaPolicyIdentity());
    }

    /** @return array{User, Business} */
    private function customerWithBusiness(string $suffix): array
    {
        $email = 'saved-policy-'.$suffix.'-'.uniqid().'@example.test';
        $business = Business::create([
            'business_name' => 'Saved Policy '.ucfirst($suffix),
            'contact_name' => 'Saved Policy Customer',
            'email' => $email,
            'status' => 1,
        ]);
        $user = User::factory()->create([
            'email' => $email,
            'role' => 'customer',
            'fuel_business_id' => $business->id,
        ]);

        return [$user, $business];
    }

    private function sourceImage(Business $business, string $path, int $threshold, string $sourceMarker): DtfImage
    {
        $order = DtfOrder::create([
            'business_id' => $business->id,
            'status' => 2,
            'order_date' => now(),
        ]);

        return DtfImage::create([
            'dtforder_id' => $order->id,
            'image' => $path,
            'thumbnail' => '/uploads/images/thumbs/'.$sourceMarker.'.png',
            'item_type' => 'standard',
            'item_meta' => [
                'source_artwork' => [
                    'version' => 1,
                    'disk' => 'local_private',
                    'path' => $sourceMarker,
                ],
                'alpha_processing' => [
                    'version' => 1,
                    'scope' => 'production_derivative',
                    'threshold' => $threshold,
                ],
            ],
            'image_name' => $sourceMarker,
            'width' => 2,
            'height' => 1,
            'quantity' => 1,
            'production' => 0,
        ]);
    }
}
