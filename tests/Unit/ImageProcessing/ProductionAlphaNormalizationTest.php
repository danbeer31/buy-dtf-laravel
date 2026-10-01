<?php

namespace Tests\Unit\ImageProcessing;

use App\Helpers\ImageHelper;
use Imagick;
use PHPUnit\Framework\TestCase;

class ProductionAlphaNormalizationTest extends TestCase
{
    private string $temporaryDirectory;

    protected function setUp(): void
    {
        parent::setUp();

        self::assertTrue(extension_loaded('imagick'), 'Imagick is required for the production alpha test matrix.');
        self::assertTrue(extension_loaded('gd'), 'GD is required for the production alpha fallback test matrix.');
        $this->temporaryDirectory = sys_get_temp_dir().'/buy-dtf-alpha-tests-'.bin2hex(random_bytes(6));
        self::assertTrue(mkdir($this->temporaryDirectory, 0700, true));
    }

    protected function tearDown(): void
    {
        foreach (glob($this->temporaryDirectory.'/*') ?: [] as $file) {
            is_file($file) && unlink($file);
        }
        is_dir($this->temporaryDirectory) && rmdir($this->temporaryDirectory);

        parent::tearDown();
    }

    public function test_fixture_hashes_are_frozen(): void
    {
        $expected = [];
        foreach (file($this->fixturePath('SHA256SUMS'), FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
            [$hash, $name] = preg_split('/\s+/', trim($line), 2);
            $expected[$name] = $hash;
        }

        self::assertCount(8, $expected);
        foreach ($expected as $name => $hash) {
            self::assertSame($hash, hash_file('sha256', $this->fixturePath($name)), $name);
        }
    }

    public function test_imagick_and_gd_produce_the_same_thresholded_geometry_and_binary_alpha(): void
    {
        $fixtures = [
            'transparent-padding.png' => ['x' => 3, 'y' => 3, 'width' => 6, 'height' => 4],
            'antialiased-edges.png' => ['x' => 2, 'y' => 2, 'width' => 6, 'height' => 6],
            'shadow-glow.png' => ['x' => 3, 'y' => 2, 'width' => 7, 'height' => 7],
            'hard-edged-opaque.png' => ['x' => 2, 'y' => 1, 'width' => 5, 'height' => 5],
            'no-transparent-padding.png' => ['x' => 0, 'y' => 0, 'width' => 8, 'height' => 6],
        ];

        foreach (['imagick', 'gd'] as $renderer) {
            foreach ($fixtures as $name => $expectedBounds) {
                $source = $this->fixturePath($name);
                $sourceHash = hash_file('sha256', $source);
                $bounds = ImageHelper::productionAlphaBounds($source, 128, $renderer);

                self::assertTrue($bounds['success'] ?? false, "$renderer failed to measure $name");
                self::assertSame($expectedBounds, array_intersect_key($bounds, $expectedBounds), "$renderer bounds differ for $name");

                $output = $this->temporaryDirectory."/$renderer-$name";
                $result = ImageHelper::prepareForProduction(
                    $source,
                    $output,
                    $expectedBounds['width'] / 300,
                    $expectedBounds['height'] / 300,
                    300,
                    128,
                    $renderer,
                );

                self::assertTrue($result['success'] ?? false, "$renderer failed to render $name: ".($result['message'] ?? ''));
                self::assertSame($sourceHash, hash_file('sha256', $source), "$renderer modified source $name");
                self::assertSame(
                    [$expectedBounds['width'], $expectedBounds['height']],
                    array_slice(getimagesize($output), 0, 2),
                    "$renderer output dimensions differ for $name",
                );

                $resolution = ImageHelper::pngResolution($output);
                self::assertNotNull($resolution, "$renderer omitted PNG pHYs for $name");
                self::assertEqualsWithDelta(300.0, $resolution['x_dpi'], 0.02);
                self::assertEqualsWithDelta(300.0, $resolution['y_dpi'], 0.02);

                $alphas = $this->alphaMatrix($output);
                foreach ($alphas as $row) {
                    foreach ($row as $alpha) {
                        self::assertContains($alpha, [0, 255], "$renderer left a partial-alpha output pixel in $name");
                    }
                }
                $visible = $this->visibleBounds($alphas);
                self::assertSame(
                    ['x' => 0, 'y' => 0, 'width' => $expectedBounds['width'], 'height' => $expectedBounds['height']],
                    $visible,
                    "$renderer left transparent perimeter in $name",
                );
                self::assertEqualsWithDelta(
                    $expectedBounds['width'] / $expectedBounds['height'],
                    getimagesize($output)[0] / getimagesize($output)[1],
                    0.000001,
                    "$renderer changed the expected aspect ratio for $name",
                );
            }
        }
    }

    public function test_threshold_cutoff_preserves_128_and_discards_127_for_both_renderers(): void
    {
        $source = $this->fixturePath('antialiased-edges.png');
        self::assertSame(64, $this->alphaAt($source, 1, 3));
        self::assertSame(127, $this->alphaAt($source, 2, 2));
        self::assertSame(128, $this->alphaAt($source, 2, 3));
        self::assertSame(192, $this->alphaAt($source, 3, 2));

        foreach (['imagick', 'gd'] as $renderer) {
            $copy = $this->temporaryDirectory."/threshold-$renderer.png";
            copy($source, $copy);
            $result = ImageHelper::thresholdAlphaMask($copy, 128, $renderer);

            self::assertTrue($result['success'] ?? false);
            self::assertSame(0, $this->alphaAt($copy, 1, 3));
            self::assertSame(0, $this->alphaAt($copy, 2, 2));
            self::assertSame(255, $this->alphaAt($copy, 2, 3));
            self::assertSame(255, $this->alphaAt($copy, 3, 2));
        }
    }

    public function test_shadow_and_glow_cutoff_is_explicit_and_source_is_unchanged(): void
    {
        $source = $this->fixturePath('shadow-glow.png');
        $sourceHash = hash_file('sha256', $source);
        self::assertSame(32, $this->alphaAt($source, 1, 0));
        self::assertSame(96, $this->alphaAt($source, 2, 1));
        self::assertSame(160, $this->alphaAt($source, 3, 2));
        self::assertSame(255, $this->alphaAt($source, 4, 3));

        foreach (['imagick', 'gd'] as $renderer) {
            $output = $this->temporaryDirectory."/glow-$renderer.png";
            $result = ImageHelper::prepareForProduction($source, $output, 7 / 300, 7 / 300, 300, 128, $renderer);

            self::assertTrue($result['success'] ?? false);
            self::assertSame($sourceHash, hash_file('sha256', $source));
            self::assertSame(255, $this->alphaAt($output, 0, 0), "$renderer discarded the retained glow edge");
            self::assertSame(255, $this->alphaAt($output, 1, 1), "$renderer discarded the opaque artwork");
        }
    }

    public function test_fully_transparent_artwork_fails_closed_for_both_renderers(): void
    {
        $source = $this->fixturePath('fully-transparent.png');
        $sourceHash = hash_file('sha256', $source);

        foreach (['imagick', 'gd'] as $renderer) {
            $bounds = ImageHelper::productionAlphaBounds($source, 128, $renderer);
            self::assertFalse($bounds['success'] ?? true);
            self::assertSame('fully_transparent_image', $bounds['reason'] ?? null);

            $output = $this->temporaryDirectory."/transparent-$renderer.png";
            $result = ImageHelper::prepareForProduction($source, $output, 1, 1, 300, 128, $renderer);
            self::assertFalse($result['success'] ?? true);
            self::assertSame('fully_transparent_image', $result['reason'] ?? null);
            self::assertFileDoesNotExist($output);
            self::assertSame($sourceHash, hash_file('sha256', $source));
        }
    }

    public function test_null_threshold_preserves_partial_alpha_for_legacy_and_incoming_derivatives(): void
    {
        $source = $this->fixturePath('antialiased-edges.png');
        $sourceHash = hash_file('sha256', $source);

        foreach (['imagick', 'gd'] as $renderer) {
            $output = $this->temporaryDirectory."/unthresholded-$renderer.png";
            $result = ImageHelper::prepareForProduction($source, $output, 10 / 300, 10 / 300, 300, null, $renderer);

            self::assertTrue($result['success'] ?? false);
            self::assertSame([10, 10], array_slice(getimagesize($output), 0, 2));
            self::assertGreaterThan(0, $this->alphaAt($output, 1, 3));
            self::assertLessThan(255, $this->alphaAt($output, 1, 3));
            self::assertSame($sourceHash, hash_file('sha256', $source));
        }
    }

    private function fixturePath(string $name): string
    {
        return dirname(__DIR__, 2).'/Fixtures/ImageProcessing/'.$name;
    }

    /** @return array<int, array<int, int>> */
    private function alphaMatrix(string $path): array
    {
        $image = new Imagick($path);
        $matrix = [];
        foreach ($image->getPixelIterator() as $y => $row) {
            foreach ($row as $x => $pixel) {
                $matrix[$y][$x] = (int) round($pixel->getColorValue(Imagick::COLOR_ALPHA) * 255);
            }
        }
        $image->clear();
        $image->destroy();

        return $matrix;
    }

    /** @param array<int, array<int, int>> $matrix */
    private function visibleBounds(array $matrix): ?array
    {
        $minX = count($matrix[0] ?? []);
        $minY = count($matrix);
        $maxX = -1;
        $maxY = -1;
        foreach ($matrix as $y => $row) {
            foreach ($row as $x => $alpha) {
                if ($alpha === 0) {
                    continue;
                }
                $minX = min($minX, $x);
                $minY = min($minY, $y);
                $maxX = max($maxX, $x);
                $maxY = max($maxY, $y);
            }
        }

        return $maxX < 0 ? null : [
            'x' => $minX,
            'y' => $minY,
            'width' => $maxX - $minX + 1,
            'height' => $maxY - $minY + 1,
        ];
    }

    private function alphaAt(string $path, int $x, int $y): int
    {
        $image = new Imagick($path);
        $alpha = (int) round($image->getImagePixelColor($x, $y)->getColorValue(Imagick::COLOR_ALPHA) * 255);
        $image->clear();
        $image->destroy();

        return $alpha;
    }
}
