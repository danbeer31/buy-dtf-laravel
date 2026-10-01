<?php

namespace Tests\Unit\Helpers;

use App\Helpers\ProductionHelper;
use App\Models\DtfImage;
use App\Services\DropboxService;
use Mockery;
use PHPUnit\Framework\Attributes\PreserveGlobalState;
use PHPUnit\Framework\Attributes\RunInSeparateProcess;
use ReflectionMethod;
use Tests\TestCase;

class ProductionAlphaPolicyTest extends TestCase
{
    #[RunInSeparateProcess]
    #[PreserveGlobalState(false)]
    public function test_new_upload_policy_changes_only_the_temporary_production_derivative(): void
    {
        $basename = 'alpha-policy-'.bin2hex(random_bytes(5)).'.png';
        $relativePath = '/uploads/images/'.$basename;
        $sourcePath = public_path(ltrim($relativePath, '/'));
        if (! is_dir(dirname($sourcePath))) {
            mkdir(dirname($sourcePath), 0777, true);
        }
        $sourceBytes = "immutable-alpha-source\x00bytes";
        file_put_contents($sourcePath, $sourceBytes);
        $sourceHash = hash_file('sha256', $sourcePath);

        $image = new DtfImage([
            'image' => $relativePath,
            'item_meta' => [
                'alpha_processing' => [
                    'version' => 1,
                    'scope' => 'production_derivative',
                    'threshold' => 128,
                ],
            ],
        ]);

        $imageHelper = Mockery::mock('alias:App\Helpers\ImageHelper');
        $imageHelper->shouldReceive('prepareForProduction')
            ->once()
            ->withArgs(function (
                string $input,
                string $output,
                float $width,
                float $height,
                int $dpi,
                int $threshold
            ) use ($sourcePath): bool {
                return realpath($input) === realpath($sourcePath)
                    && str_ends_with($output, '.png')
                    && $width === 2.0
                    && $height === 1.0
                    && $dpi === 300
                    && $threshold === 128;
            })
            ->andReturnUsing(function (string $input, string $output): array {
                file_put_contents($output, 'thresholded-production-copy');

                return ['success' => true];
            });

        $uploaded = null;
        $dropbox = Mockery::mock(DropboxService::class);
        $dropbox->shouldReceive('upload')
            ->once()
            ->andReturnUsing(function (string $localPath, string $remotePath) use (&$uploaded): array {
                $uploaded = [
                    'remote' => $remotePath,
                    'bytes' => file_get_contents($localPath),
                ];

                return ['path' => $remotePath];
            });

        try {
            $method = new ReflectionMethod(ProductionHelper::class, 'uploadProductionImage');
            $result = $method->invoke(
                null,
                $dropbox,
                $image,
                '/DTF_Files/coldesi/'.$basename,
                null,
                false,
                2.0,
                1.0,
                null,
            );

            self::assertTrue($result);
            self::assertSame([
                'remote' => '/DTF_Files/coldesi/'.$basename,
                'bytes' => 'thresholded-production-copy',
            ], $uploaded);
            self::assertSame($sourceHash, hash_file('sha256', $sourcePath));
            self::assertSame($sourceBytes, file_get_contents($sourcePath));
        } finally {
            if (is_file($sourcePath)) {
                unlink($sourcePath);
            }
        }
    }
}
