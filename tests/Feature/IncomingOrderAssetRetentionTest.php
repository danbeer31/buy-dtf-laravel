<?php

namespace Tests\Feature;

use App\Models\ApiAssetRecord;
use App\Models\Business;
use App\Models\CustomerArtworkRemoval;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\IncomingOrderJob;
use App\Models\SavedImage;
use App\Models\User;
use App\Services\IncomingOrders\CustomerArtworkRemovalService;
use Illuminate\Support\Facades\Artisan;
use Tests\TestCase;

class IncomingOrderAssetRetentionTest extends TestCase
{
    /** @var list<string> */
    private array $files = [];

    protected function tearDown(): void
    {
        foreach ($this->files as $file) {
            if (is_file($file)) {
                unlink($file);
            }
        }

        parent::tearDown();
    }

    public function test_retention_report_selects_only_explicit_future_api_records_and_never_deletes(): void
    {
        $job = $this->incomingJob();
        $legacyFile = $this->publicFixture('retention-legacy.png');
        $candidateFile = $this->publicFixture('retention-api-candidate.png');

        ApiAssetRecord::create([
            'incoming_order_job_id' => $job->id,
            'origin' => 'incoming_order_v1',
            'asset_role' => 'original',
            'storage_scope' => 'public_root',
            'asset_path' => '/uploads/images/retention-api-candidate.png',
            'path_hash' => hash('sha256', '/uploads/images/retention-api-candidate.png'),
            'sha256' => hash_file('sha256', $candidateFile),
            'bytes' => filesize($candidateFile),
            'retention_policy' => 'expirable',
            'retention_enabled' => true,
            'retention_days' => 30,
            'expires_at' => now()->subDay(),
        ]);
        ApiAssetRecord::create([
            'incoming_order_job_id' => $job->id,
            'origin' => 'incoming_order_v1',
            'asset_role' => 'job_card',
            'storage_scope' => 'public_root',
            'asset_path' => '/uploads/images/retention-legacy.png',
            'path_hash' => hash('sha256', '/uploads/images/retention-legacy.png'),
            'sha256' => hash_file('sha256', $legacyFile),
            'bytes' => filesize($legacyFile),
            'retention_policy' => 'forever',
            'retention_enabled' => false,
        ]);

        $this->assertSame(0, Artisan::call('incoming-orders:retention-report', ['--json' => true]));
        $output = Artisan::output();
        $this->assertStringContainsString('"mode": "report_only"', $output);
        $this->assertStringContainsString('"candidate_rows": 1', $output);
        $this->assertStringContainsString('retention-api-candidate.png', $output);

        $this->assertFileExists($candidateFile);
        $this->assertFileExists($legacyFile);
        $this->assertDatabaseCount('api_asset_records', 2, 'fuelmysql');
    }

    public function test_customer_removal_hides_business_artwork_and_saved_copy_but_defaults_to_no_physical_purge(): void
    {
        [$user, $business, $order, $image, $path] = $this->customerArtwork(status: 4);
        SavedImage::create([
            'business_id' => $business->id,
            'image' => $image->image,
            'image_name' => 'Saved copy',
            'date_uploaded' => now(),
        ]);
        config()->set('incoming_order.customer_artwork.deletion_enabled', true);
        config()->set('incoming_order.customer_artwork.physical_purge_enabled', false);

        $this->actingAs($user)
            ->deleteJson(route('account.images.delete', $image))
            ->assertOk()
            ->assertJsonPath('state', 'deferred')
            ->assertJsonPath('deferred_reason', 'physical_purge_disabled');

        $this->assertFileExists($path);
        $this->assertDatabaseMissing('savedimages', [
            'business_id' => $business->id,
            'image' => $image->image,
        ], 'fuelmysql');
        $this->assertDatabaseHas('customer_artwork_removals', [
            'business_id' => $business->id,
            'asset_path' => $image->image,
            'state' => 'deferred',
        ], 'fuelmysql');
        $this->actingAs($user)->getJson(route('account.images'))
            ->assertOk()
            ->assertDontSee('Customer artwork');
        $this->actingAs($user)->getJson(route('cart.my_images'))
            ->assertOk()
            ->assertJsonCount(0, 'items');
        $this->assertDatabaseHas('dtfimages', ['id' => $image->id], 'fuelmysql');
        $this->assertSame(4, (int) $order->fresh()->status);
    }

    public function test_physical_purge_waits_for_active_work_then_deletes_source_after_recheck(): void
    {
        [$user, $business, $order, $image, $path] = $this->customerArtwork(status: 1);
        config()->set('incoming_order.customer_artwork.deletion_enabled', true);
        config()->set('incoming_order.customer_artwork.physical_purge_enabled', true);

        $this->actingAs($user)
            ->deleteJson(route('account.images.delete', $image))
            ->assertOk()
            ->assertJsonPath('state', 'deferred')
            ->assertJsonPath('deferred_reason', 'active_reference');
        $this->assertFileExists($path);

        $order->update(['status' => 4]);
        $removal = CustomerArtworkRemoval::firstOrFail();
        $processed = app(CustomerArtworkRemovalService::class)->attemptPhysicalPurge($removal);

        $this->assertSame('purged', $processed->state);
        $this->assertNotNull($processed->purged_at);
        $this->assertFileDoesNotExist($path);
        $this->assertDatabaseHas('dtfimages', ['id' => $image->id], 'fuelmysql');
    }

    public function test_shared_or_api_managed_path_is_never_physically_deleted_by_customer_removal(): void
    {
        [$user, $business, $order, $image, $path] = $this->customerArtwork(status: 4);
        $other = Business::create([
            'business_name' => 'Other Business',
            'email' => 'other-business@example.test',
            'status' => 1,
        ]);
        $otherOrder = DtfOrder::create([
            'business_id' => $other->id,
            'status' => 4,
            'order_date' => now(),
        ]);
        DtfImage::create([
            'dtforder_id' => $otherOrder->id,
            'image' => $image->image,
            'width' => 1,
            'height' => 1,
            'quantity' => 1,
            'production' => 1,
        ]);
        config()->set('incoming_order.customer_artwork.deletion_enabled', true);
        config()->set('incoming_order.customer_artwork.physical_purge_enabled', true);

        $this->actingAs($user)
            ->deleteJson(route('account.images.delete', $image))
            ->assertOk()
            ->assertJsonPath('state', 'deferred')
            ->assertJsonPath('deferred_reason', 'shared_reference');

        $this->assertFileExists($path);
    }

    public function test_customer_cannot_delete_another_business_artwork(): void
    {
        [$user] = $this->customerArtwork(status: 4);
        [, , , $otherImage] = $this->customerArtwork(status: 4, suffix: 'other');
        config()->set('incoming_order.customer_artwork.deletion_enabled', true);

        $this->actingAs($user)
            ->deleteJson(route('account.images.delete', $otherImage))
            ->assertForbidden();

        $this->assertDatabaseCount('customer_artwork_removals', 0, 'fuelmysql');
    }

    private function incomingJob(): IncomingOrderJob
    {
        return IncomingOrderJob::create([
            'integration_client' => 'shopnltees',
            'idempotency_key' => 'retention-test-key',
            'request_fingerprint' => str_repeat('a', 64),
            'expected_art_sha256' => str_repeat('b', 64),
            'state' => 'completed',
            'attempt_count' => 1,
            'art_width_in' => '1.0000',
            'art_height_in' => '1.0000',
        ]);
    }

    /** @return array{User, Business, DtfOrder, DtfImage, string} */
    private function customerArtwork(int $status, string $suffix = 'primary'): array
    {
        $business = Business::create([
            'business_name' => 'Customer '.$suffix,
            'email' => 'customer-'.$suffix.'-'.uniqid().'@example.test',
            'status' => 1,
        ]);
        $user = User::factory()->create([
            'role' => 'customer',
            'fuel_business_id' => $business->id,
            'email' => $business->email,
        ]);
        $order = DtfOrder::create([
            'business_id' => $business->id,
            'status' => $status,
            'order_date' => now(),
        ]);
        $path = $this->publicFixture('customer-artwork-'.$suffix.'-'.uniqid().'.png');
        $relative = '/'.str_replace('\\', '/', substr($path, strlen(public_path()) + 1));
        $image = DtfImage::create([
            'dtforder_id' => $order->id,
            'image' => $relative,
            'image_name' => 'Customer artwork '.$suffix,
            'width' => 1,
            'height' => 1,
            'quantity' => 1,
            'production' => $status >= 4 ? 1 : 0,
            'date_uploaded' => now(),
        ]);

        return [$user, $business, $order, $image, $path];
    }

    private function publicFixture(string $name): string
    {
        $path = public_path('uploads/images/'.$name);
        if (! is_dir(dirname($path))) {
            mkdir(dirname($path), 0777, true);
        }
        file_put_contents($path, 'retention-fixture-'.$name);
        $this->files[] = $path;

        return $path;
    }
}
