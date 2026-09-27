<?php

namespace Tests\Feature\Production;

use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\IncomingOrderJob;
use App\Models\User;
use App\Services\IncomingOrders\JobCardRenderer;
use Illuminate\Support\Facades\Mail;
use Mockery;
use PHPUnit\Framework\Attributes\PreserveGlobalState;
use PHPUnit\Framework\Attributes\RunInSeparateProcess;
use RuntimeException;
use Tests\TestCase;

class ApiJobCardHandoffTest extends TestCase
{
    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_labeled_api_group_uploads_separate_quantity_one_card_before_marking_complete(): void
    {
        [$admin, $order, $first, $second, $sourcePath] = $this->createLabeledGroup();
        $first->update(['width' => 7, 'height' => 7, 'quantity' => 9]);
        $second->update(['width' => 7, 'height' => 7, 'quantity' => 9]);
        $cardPath = $this->fakeCardRenderer();
        [$previousErrorLog, $isolatedErrorLog] = $this->isolateErrorLog();

        $imageHelper = Mockery::mock('alias:App\Helpers\ImageHelper');
        $imageHelper->shouldReceive('prepareForProductionAspectSafe')
            ->once()
            ->andReturnUsing(function (
                string $source,
                string $output,
                float $width,
                float $height,
                int $dpi,
            ): array {
                $this->assertSame(4.0, $width);
                $this->assertSame(2.0, $height);
                $this->assertSame(300, $dpi);
                copy($source, $output);

                return ['success' => true];
            });

        $uploads = [];
        $dropbox = Mockery::mock('overload:App\Services\DropboxService');
        $dropbox->shouldReceive('upload')
            ->andReturnUsing(function (string $local, string $remote) use (&$uploads): array {
                $this->assertFileExists($local);
                $uploads[] = ['remote' => $remote, 'contents' => file_get_contents($local)];

                return ['path' => $remote];
            });

        try {
            $this->actingAs($admin)
                ->postJson(route('admin.orders.add-to-production'), ['image_id' => $first->id])
                ->assertOk()
                ->assertJsonPath('status', 'success')
                ->assertJsonPath('group_count', 2)
                ->assertJsonPath('quantity', 4);

            $this->assertCount(4, $uploads);
            $this->assertStringContainsString("/{$first->id}-api-art--art-", $uploads[0]['remote']);
            $this->assertStringEndsWith('.jhdr', $uploads[0]['remote']);
            $this->assertStringContainsString('<Copies>4</Copies>', $uploads[0]['contents']);
            $this->assertStringContainsString("/{$first->id}-api-art--art-", $uploads[1]['remote']);
            $this->assertStringEndsWith('.png', $uploads[1]['remote']);
            $this->assertStringContainsString('--job-card-', $uploads[2]['remote']);
            $this->assertStringEndsWith('.jhdr', $uploads[2]['remote']);
            $this->assertStringContainsString('<Copies>1</Copies>', $uploads[2]['contents']);
            $this->assertStringContainsString('--job-card-', $uploads[3]['remote']);
            $this->assertStringEndsWith('.png', $uploads[3]['remote']);

            $this->assertSame(1, (int) $first->fresh()->production);
            $this->assertSame(1, (int) $second->fresh()->production);
            $this->assertSame(3, (int) $order->fresh()->status);
            foreach (IncomingOrderJob::orderBy('id')->get() as $job) {
                $this->assertSame('rendered', $job->job_label_status);
                $this->assertSame('completed', $job->production_state);
                $this->assertNotNull($job->production_completed_at);
                $this->assertSame(1, $job->production_result['job_card_quantity']);
            }
            $this->assertDatabaseCount('api_asset_records', 4, 'fuelmysql');
        } finally {
            $this->restoreErrorLog($previousErrorLog, $isolatedErrorLog);
            $this->cleanupFiles([$sourcePath, $cardPath]);
        }
    }

    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_card_upload_failure_leaves_all_rows_retryable_and_out_of_production(): void
    {
        [$admin, $order, $first, $second, $sourcePath] = $this->createLabeledGroup();
        $cardPath = $this->fakeCardRenderer();
        [$previousErrorLog, $isolatedErrorLog] = $this->isolateErrorLog();

        $imageHelper = Mockery::mock('alias:App\Helpers\ImageHelper');
        $imageHelper->shouldReceive('prepareForProductionAspectSafe')
            ->once()
            ->andReturnUsing(function (string $source, string $output): array {
                copy($source, $output);

                return ['success' => true];
            });

        $dropbox = Mockery::mock('overload:App\Services\DropboxService');
        $dropbox->shouldReceive('upload')
            ->andReturnUsing(function (string $local, string $remote): array {
                if (str_contains($remote, '--job-card-')) {
                    throw new RuntimeException('synthetic companion upload failure');
                }

                return ['path' => $remote];
            });

        try {
            $this->actingAs($admin)
                ->postJson(route('admin.orders.add-to-production'), ['image_id' => $first->id])
                ->assertStatus(500);

            $this->assertSame(0, (int) $first->fresh()->production);
            $this->assertSame(0, (int) $second->fresh()->production);
            $this->assertSame(2, (int) $order->fresh()->status);
            foreach (IncomingOrderJob::all() as $job) {
                $this->assertSame('retryable_failure', $job->production_state);
                $this->assertSame('job_card_handoff_failed', $job->last_error_code);
                $this->assertNull($job->production_completed_at);
            }
        } finally {
            $this->restoreErrorLog($previousErrorLog, $isolatedErrorLog);
            $this->cleanupFiles([$sourcePath, $cardPath]);
        }
    }

    public function test_different_card_fingerprints_never_share_a_production_group_key(): void
    {
        [, , $first, $second, $sourcePath] = $this->createLabeledGroup('fingerprint-one', 'fingerprint-two');

        try {
            $this->assertNotSame($first->productionGroupingKey(), $second->productionGroupingKey());
        } finally {
            $this->cleanupFiles([$sourcePath]);
        }
    }

    public function test_active_production_claim_rejects_a_concurrent_handoff_without_changing_state(): void
    {
        [$admin, , $first, $second, $sourcePath] = $this->createLabeledGroup();
        IncomingOrderJob::query()->whereIn('dtfimage_id', [$first->id, $second->id])->update([
            'production_state' => 'processing',
            'production_owner' => '00000000-0000-4000-8000-000000000001',
            'production_group_key' => str_repeat('a', 64),
            'production_started_at' => now(),
            'production_heartbeat_at' => now(),
            'production_lease_expires_at' => now()->addMinutes(5),
        ]);

        try {
            $this->actingAs($admin)
                ->postJson(route('admin.orders.add-to-production'), ['image_id' => $first->id])
                ->assertStatus(500)
                ->assertJsonPath('message', 'Production handoff is already processing.');

            $this->assertSame(0, (int) $first->fresh()->production);
            $this->assertSame(0, (int) $second->fresh()->production);
            foreach (IncomingOrderJob::all() as $job) {
                $this->assertSame('processing', $job->production_state);
                $this->assertSame(0, $job->production_attempt_count);
            }
        } finally {
            $this->cleanupFiles([$sourcePath]);
        }
    }

    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_production_handoff_reverifies_frozen_source_hash_before_any_upload(): void
    {
        [$admin, , $first, $second, $sourcePath] = $this->createLabeledGroup();
        file_put_contents($sourcePath, 'tampered-after-api-receipt');
        [$previousErrorLog, $isolatedErrorLog] = $this->isolateErrorLog();

        $dropbox = Mockery::mock('overload:App\Services\DropboxService');
        $dropbox->shouldNotReceive('upload');

        try {
            $this->actingAs($admin)
                ->postJson(route('admin.orders.add-to-production'), ['image_id' => $first->id])
                ->assertStatus(500)
                ->assertJsonPath('message', 'Immutable source artwork hash does not match the frozen job.');

            foreach (IncomingOrderJob::all() as $job) {
                $this->assertSame('retryable_failure', $job->production_state);
                $this->assertNull($job->production_owner);
                $this->assertNull($job->production_lease_expires_at);
            }
            $this->assertSame(0, (int) $first->fresh()->production);
            $this->assertSame(0, (int) $second->fresh()->production);
        } finally {
            $this->restoreErrorLog($previousErrorLog, $isolatedErrorLog);
            $this->cleanupFiles([$sourcePath]);
        }
    }

    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_stale_owner_cannot_complete_or_fail_after_a_new_owner_reclaims_the_group(): void
    {
        [, , $first, $second, $sourcePath] = $this->createLabeledGroup();
        $replacementOwner = '00000000-0000-4000-8000-000000000099';
        $imageHelper = Mockery::mock('alias:App\Helpers\ImageHelper');
        $imageHelper->shouldReceive('prepareForProductionAspectSafe')
            ->once()
            ->andReturnUsing(function (string $source, string $output) use ($replacementOwner): array {
                copy($source, $output);
                IncomingOrderJob::query()->update([
                    'production_owner' => $replacementOwner,
                    'production_heartbeat_at' => now(),
                    'production_lease_expires_at' => now()->addMinutes(5),
                ]);

                return ['success' => true];
            });
        $renderer = Mockery::mock(JobCardRenderer::class);
        $renderer->shouldNotReceive('render');
        $this->app->instance(JobCardRenderer::class, $renderer);

        try {
            app(\App\Services\IncomingOrders\ApiProductionHandoffService::class)->handoff(
                new \Illuminate\Database\Eloquent\Collection([$first, $second]),
                4,
            );
            $this->fail('A worker that lost its claim must stop.');
        } catch (RuntimeException $exception) {
            $this->assertSame('Production handoff claim was lost.', $exception->getMessage());
        }

        foreach (IncomingOrderJob::all() as $job) {
            $this->assertSame('processing', $job->production_state);
            $this->assertSame($replacementOwner, $job->production_owner);
            $this->assertNotNull($job->production_lease_expires_at);
            $this->assertNull($job->last_error_code);
        }
        $this->cleanupFiles([$sourcePath]);
    }

    /** @return array{User, DtfOrder, DtfImage, DtfImage, string} */
    private function createLabeledGroup(
        string $firstFingerprint = 'same-fingerprint',
        string $secondFingerprint = 'same-fingerprint',
    ): array {
        Mail::fake();
        $admin = User::factory()->create(['role' => 'admin']);
        $business = Business::create([
            'business_name' => 'API Production Test',
            'contact_name' => 'Production',
            'email' => 'api-production-'.uniqid().'@example.test',
            'status' => 1,
        ]);
        $order = DtfOrder::create([
            'business_id' => $business->id,
            'status' => 2,
            'order_date' => now(),
        ]);

        $relative = '/uploads/images/api-art.png';
        $sourcePath = public_path(ltrim($relative, '/'));
        if (! is_dir(dirname($sourcePath))) {
            mkdir(dirname($sourcePath), 0777, true);
        }
        file_put_contents($sourcePath, 'api-production-artwork');

        $first = DtfImage::create([
            'dtforder_id' => $order->id,
            'image' => $relative,
            'item_type' => 'standard',
            'width' => 4,
            'height' => 2,
            'quantity' => 2,
            'production' => 0,
        ]);
        $second = DtfImage::create([
            'dtforder_id' => $order->id,
            'image' => $relative,
            'item_type' => 'standard',
            'width' => 4,
            'height' => 2,
            'quantity' => 2,
            'production' => 0,
        ]);

        $metadata = [
            'version' => 1,
            'required' => false,
            'mode' => 'metadata_only',
            'order_number' => '1725',
            'order_item_id' => 1671,
            'production_print_snapshot_id' => 31,
            'product_name' => 'Urey Cheer Jacket',
            'product_sku' => 'PC78H',
            'color' => 'Black',
            'size' => 'S',
            'placement' => 'Full Back',
            'quantity' => 2,
            'shop_domain' => 'urey.localschoolgear.com',
        ];
        $this->createIncomingJob($first, $metadata, $firstFingerprint, 'dispatch-one');
        $this->createIncomingJob($second, $metadata, $secondFingerprint, 'dispatch-two');

        return [$admin, $order, $first->fresh('incomingOrderJob'), $second->fresh('incomingOrderJob'), $sourcePath];
    }

    private function createIncomingJob(
        DtfImage $image,
        array $metadata,
        string $fingerprint,
        string $key,
    ): void {
        IncomingOrderJob::create([
            'dtfimage_id' => $image->id,
            'integration_client' => 'shopnltees',
            'idempotency_key' => $key,
            'request_fingerprint' => hash('sha256', $key),
            'expected_art_sha256' => hash('sha256', 'api-production-artwork'),
            'actual_art_sha256' => hash('sha256', 'api-production-artwork'),
            'state' => 'completed',
            'attempt_count' => 1,
            'job_label_version' => 1,
            'job_label_required' => false,
            'job_label_mode' => 'metadata_only',
            'job_label_status' => 'accepted',
            'job_label_metadata' => $metadata,
            'job_label_fingerprint' => hash('sha256', $fingerprint),
            'art_width_in' => '4.0000',
            'art_height_in' => '2.0000',
            'renderer_version' => 'separate-job-card-v2',
            'production_state' => 'pending',
        ]);
    }

    private function fakeCardRenderer(): string
    {
        $cardPath = storage_path('app/private/testing/job-card-'.uniqid().'.png');
        if (! is_dir(dirname($cardPath))) {
            mkdir(dirname($cardPath), 0777, true);
        }
        file_put_contents($cardPath, 'separate-job-card');

        $renderer = Mockery::mock(JobCardRenderer::class);
        $renderer->shouldReceive('render')
            ->once()
            ->withArgs(fn (int $jobId, string $fingerprint, array $metadata, int $quantity, string $rendererVersion, ?string $expectedHash, callable $heartbeat): bool => $jobId > 0
                && strlen($fingerprint) === 64
                && $metadata['order_number'] === '1725'
                && $quantity === 4
                && $rendererVersion === 'separate-job-card-v2'
                && $expectedHash === null)
            ->andReturn([
                'relative_path' => 'testing/'.basename($cardPath),
                'absolute_path' => $cardPath,
                'sha256' => hash_file('sha256', $cardPath),
                'bytes' => filesize($cardPath),
                'width_in' => '5.0000',
                'height_in' => '3.0000',
                'renderer_version' => 'separate-job-card-v2',
                'dpi' => 300,
                'x_ppm' => 11811,
                'y_ppm' => 11811,
                'font_sha256' => 'ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280',
            ]);
        $this->app->instance(JobCardRenderer::class, $renderer);

        return $cardPath;
    }

    /** @return array{string, string} */
    private function isolateErrorLog(): array
    {
        $previous = (string) ini_get('error_log');
        $temporary = (string) tempnam(sys_get_temp_dir(), 'buy-dtf-api-handoff-log-');
        ini_set('error_log', $temporary);

        return [$previous, $temporary];
    }

    private function restoreErrorLog(string $previous, string $temporary): void
    {
        ini_set('error_log', $previous);
        if (is_file($temporary)) {
            unlink($temporary);
        }
    }

    /** @param list<string> $paths */
    private function cleanupFiles(array $paths): void
    {
        foreach ($paths as $path) {
            if (is_file($path)) {
                unlink($path);
            }
        }
        $productionRoot = storage_path('app/private/incoming-orders/production');
        if (is_dir($productionRoot)) {
            $iterator = new \RecursiveIteratorIterator(
                new \RecursiveDirectoryIterator($productionRoot, \FilesystemIterator::SKIP_DOTS),
                \RecursiveIteratorIterator::CHILD_FIRST,
            );
            foreach ($iterator as $item) {
                $item->isDir() ? rmdir($item->getPathname()) : unlink($item->getPathname());
            }
            rmdir($productionRoot);
        }
    }
}
