<?php

namespace Tests\Feature\Production;

use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\User;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Mail;
use Mockery;
use PHPUnit\Framework\Attributes\PreserveGlobalState;
use PHPUnit\Framework\Attributes\RunInSeparateProcess;
use Tests\TestCase;

class OrdinaryImageHandoffTest extends TestCase
{
    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_ordinary_duplicate_group_handoff_builds_one_job_and_never_contacts_dropbox(): void
    {
        Mail::fake();

        $admin = User::factory()->create(['role' => 'admin']);
        $business = Business::create([
            'business_name' => 'Production Test Business',
            'contact_name' => 'Production Customer',
            'email' => 'production-'.uniqid().'@example.test',
            'status' => 1,
        ]);
        $order = DtfOrder::create([
            'business_id' => $business->id,
            'status' => 2,
            'order_date' => now(),
        ]);

        $basename = 'handoff-'.uniqid().'.png';
        $relativePath = '/uploads/images/'.$basename;
        $sourcePath = public_path(ltrim($relativePath, '/'));
        if (! is_dir(dirname($sourcePath))) {
            mkdir(dirname($sourcePath), 0777, true);
        }
        file_put_contents($sourcePath, 'isolated-image-fixture');

        $first = DtfImage::create([
            'dtforder_id' => $order->id,
            'image' => $relativePath,
            'item_type' => 'standard',
            'width' => 4,
            'height' => 2,
            'quantity' => 2,
            'production' => 0,
        ]);
        $second = DtfImage::create([
            'dtforder_id' => $order->id,
            'image' => $relativePath,
            'item_type' => 'standard',
            'width' => 4,
            'height' => 2,
            'quantity' => 3,
            'production' => 0,
        ]);

        $capturedUploads = [];
        $previousErrorLog = (string) ini_get('error_log');
        $isolatedErrorLog = tempnam(sys_get_temp_dir(), 'buy-dtf-handoff-log-');
        ini_set('error_log', $isolatedErrorLog);

        $imageHelper = Mockery::mock('alias:App\Helpers\ImageHelper');
        $imageHelper->shouldReceive('prepareForProduction')
            ->once()
            ->withArgs(function (
                string $input,
                string $output,
                float $width,
                float $height,
                int $dpi
            ) use ($sourcePath): bool {
                return realpath($input) === realpath($sourcePath)
                    && str_ends_with($output, '.png')
                    && $width === 4.0
                    && $height === 2.0
                    && $dpi === 300;
            })
            ->andReturnUsing(function (string $input, string $output): array {
                copy($input, $output);

                return ['success' => true];
            });

        $dropbox = Mockery::mock('overload:App\Services\DropboxService');
        $dropbox->shouldReceive('upload')
            ->twice()
            ->andReturnUsing(function (string $localPath, string $remotePath) use (&$capturedUploads): array {
                $this->assertFileExists($localPath);
                $capturedUploads[] = [
                    'remote' => $remotePath,
                    'contents' => file_get_contents($localPath),
                ];

                return ['path' => $remotePath];
            });

        try {
            $response = $this->actingAs($admin)->postJson(
                route('admin.orders.add-to-production'),
                ['image_id' => $first->id]
            );

            $response
                ->assertOk()
                ->assertJsonPath('status', 'success')
                ->assertJsonPath('group_count', 2)
                ->assertJsonPath('quantity', 5);

            $this->assertSame(1, (int) $first->fresh()->production);
            $this->assertSame(1, (int) $second->fresh()->production);
            $this->assertSame(3, (int) $order->fresh()->status);

            $this->assertCount(2, $capturedUploads);
            $this->assertSame(
                "/DTF_Files/coldesi/{$first->id}-".pathinfo($basename, PATHINFO_FILENAME).'.jhdr',
                $capturedUploads[0]['remote']
            );
            $this->assertStringContainsString('<Copies>5</Copies>', $capturedUploads[0]['contents']);
            $this->assertStringContainsString('<Columns>5</Columns>', $capturedUploads[0]['contents']);
            $this->assertSame(
                "/DTF_Files/coldesi/{$first->id}-{$basename}",
                $capturedUploads[1]['remote']
            );
            $this->assertSame('isolated-image-fixture', $capturedUploads[1]['contents']);
            Http::assertNothingSent();
        } finally {
            ini_set('error_log', $previousErrorLog);
            if ($isolatedErrorLog && is_file($isolatedErrorLog)) {
                unlink($isolatedErrorLog);
            }
            if (is_file($sourcePath)) {
                unlink($sourcePath);
            }
        }
    }
}
