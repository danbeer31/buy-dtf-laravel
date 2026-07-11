<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Helpers\ImageHelper;
use Illuminate\Http\Request;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Log;
use Imagick;
use Exception;

class OrderImageController extends Controller
{
    private function probePhysicalSizeInches(string $absolutePath, bool $force300Dpi = false): array
    {
        $result = [
            'width_in' => null,
            'height_in' => null,
            'dpi_x' => null,
            'dpi_y' => null,
            'source' => 'unknown',
        ];

        if (!is_file($absolutePath) || !class_exists('\Imagick')) {
            $imageSize = @getimagesize($absolutePath);
            if (is_array($imageSize) && isset($imageSize[0], $imageSize[1])) {
                $result['width_in'] = round((float)$imageSize[0] / 300, 4);
                $result['height_in'] = round((float)$imageSize[1] / 300, 4);
                $result['dpi_x'] = 300.0;
                $result['dpi_y'] = 300.0;
                $result['source'] = 'getimagesize_300dpi';
            }
            return $result;
        }

        try {
            $im = new Imagick($absolutePath);
            $pxW = (float) $im->getImageWidth();
            $pxH = (float) $im->getImageHeight();

            if ($force300Dpi) {
                $result['width_in'] = round($pxW / 300, 4);
                $result['height_in'] = round($pxH / 300, 4);
                $result['dpi_x'] = 300.0;
                $result['dpi_y'] = 300.0;
                $result['source'] = 'forced_300dpi';
                $im->clear();
                $im->destroy();
                return $result;
            }

            $res = (array) $im->getImageResolution();
            $units = (int) $im->getImageUnits();

            $dpiX = isset($res['x']) ? (float) $res['x'] : 0.0;
            $dpiY = isset($res['y']) ? (float) $res['y'] : 0.0;

            if ($units === Imagick::RESOLUTION_PIXELSPERCENTIMETER) {
                $dpiX *= 2.54;
                $dpiY *= 2.54;
            } elseif ($units !== Imagick::RESOLUTION_PIXELSPERINCH) {
                $dpiX = 0.0;
                $dpiY = 0.0;
            }

            if ($dpiX > 0.0 && $dpiY > 0.0) {
                $result['width_in'] = round($pxW / $dpiX, 4);
                $result['height_in'] = round($pxH / $dpiY, 4);
                $result['dpi_x'] = round($dpiX, 4);
                $result['dpi_y'] = round($dpiY, 4);
                $result['source'] = 'metadata';
            } else {
                // Fallback for files without reliable units/resolution metadata.
                $result['width_in'] = round($pxW / 300, 4);
                $result['height_in'] = round($pxH / 300, 4);
                $result['dpi_x'] = 300.0;
                $result['dpi_y'] = 300.0;
                $result['source'] = 'fallback_300dpi';
            }

            $im->clear();
            $im->destroy();
        } catch (Exception $e) {
            $imageSize = @getimagesize($absolutePath);
            if (is_array($imageSize) && isset($imageSize[0], $imageSize[1])) {
                $result['width_in'] = round((float)$imageSize[0] / 300, 4);
                $result['height_in'] = round((float)$imageSize[1] / 300, 4);
                $result['dpi_x'] = 300.0;
                $result['dpi_y'] = 300.0;
                $result['source'] = 'getimagesize_300dpi';
            } else {
                Log::warning('Compare probe failed: ' . $e->getMessage());
            }
        }

        return $result;
    }

    public function edit(DtfImage $image)
    {
        $order = $image->dtfOrder;

        $probe = [
            'px_w' => null,
            'px_h' => null,
            'dpi_x' => null,
            'dpi_y' => null,
            'units' => 'undefined',
            'units_label' => 'Undefined',
            'size300_w' => null,
            'size300_h' => null,
            'has_phys' => false,
        ];

        try {
            $abs = public_path(ltrim((string)$image->image, '/'));

            if (class_exists('\Imagick') && is_file($abs)) {
                $im = new Imagick($abs);

                $w = (int)$im->getImageWidth();
                $h = (int)$im->getImageHeight();
                $probe['px_w'] = $w;
                $probe['px_h'] = $h;

                $res   = (array)$im->getImageResolution();
                $units = (int)$im->getImageUnits();

                $dpiX = isset($res['x']) ? (float)$res['x'] : 0.0;
                $dpiY = isset($res['y']) ? (float)$res['y'] : 0.0;

                switch ($units) {
                    case Imagick::RESOLUTION_PIXELSPERINCH:
                        $probe['units'] = 'ppi';
                        $probe['units_label'] = 'PixelsPerInch';
                        break;
                    case Imagick::RESOLUTION_PIXELSPERCENTIMETER:
                        $dpiX *= 2.54;
                        $dpiY *= 2.54;
                        $probe['units'] = 'ppi';
                        $probe['units_label'] = 'PixelsPerInch';
                        break;
                    default:
                        $probe['units'] = 'undefined';
                        $probe['units_label'] = 'Undefined';
                        $wIn = (float)$image->width;
                        $hIn = (float)$image->height;
                        if ($wIn > 0 && $hIn > 0) {
                            $dpiX = $w / $wIn;
                            $dpiY = $h / $hIn;
                        }
                        break;
                }

                $probe['dpi_x'] = $dpiX ? round($dpiX, 2) : null;
                $probe['dpi_y'] = $dpiY ? round($dpiY, 2) : null;
                $probe['has_phys'] = ($probe['dpi_x'] && $probe['dpi_y'] && $probe['units'] !== 'undefined');
                $probe['size300_w'] = $w ? round($w / 300, 2) : null;
                $probe['size300_h'] = $h ? round($h / 300, 2) : null;

                $im->clear();
                $im->destroy();
            }
        } catch (Exception $e) {
            Log::warning('Image probe failed: ' . $e->getMessage());
        }

        return view('admin.orders.images.edit', compact('image', 'order', 'probe'));
    }

    public function update(Request $request, DtfImage $image)
    {
        $request->validate([
            'width' => 'required|numeric|min:0.01',
            'height' => 'required|numeric|min:0.01',
        ]);

        $width = (float)$request->width;
        $height = (float)$request->height;

        $image->width = $width;
        $image->height = $height;
        if ($height > 0) {
            $image->width_ratio = round($width / $height, 6);
            $image->height_ratio = round($height / $width, 6);
        } else {
            $image->width_ratio = 0;
            $image->height_ratio = 0;
        }
        $image->save();

        try {
            $abs = public_path(ltrim((string)$image->image, '/'));
            if (is_file($abs)) {
                $im = new Imagick($abs);
                $pxW = $im->getImageWidth();
                $pxH = $im->getImageHeight();
                $im->clear();
                $im->destroy();

                $dpiX = (int)round($pxW / max(0.01, $width));
                $dpiY = (int)round($pxH / max(0.01, $height));

                ImageHelper::setPngDpi($abs, $dpiX, $dpiY);
            } else {
                return back()->with('error', 'Could not update PNG DPI: file not found.');
            }
        } catch (Exception $e) {
            return back()->with('error', 'DPI update failed: ' . $e->getMessage());
        }

        return back()->with('success', 'Size updated and PNG DPI metadata written.');
    }

    public function replace(Request $request, DtfImage $image)
    {
        $request->validate([
            'file' => 'required|image|max:25600', // 25MB
        ]);

        $file = $request->file('file');
        $absPath = public_path(ltrim((string)$image->image, '/'));
        $absDir = dirname($absPath);
        $curBase = basename($absPath);

        // Versioning logic
        $dotPos = strrpos($curBase, '.');
        $nameOnly = $dotPos !== false ? substr($curBase, 0, $dotPos) : $curBase;
        $ext = $file->getClientOriginalExtension() ?: ($dotPos !== false ? substr($curBase, $dotPos + 1) : 'png');

        $base = $nameOnly;
        $n = 1;
        if (preg_match('/^(.*)edit(\d+)$/i', $nameOnly, $m)) {
            $base = $m[1];
            $n = max(1, (int)$m[2] + 1);
        }

        do {
            $newBasename = $base . 'edit' . $n . '.' . $ext;
            $n++;
        } while (file_exists($absDir . DIRECTORY_SEPARATOR . $newBasename));

        // Save new file
        $relativePath = 'uploads/images'; // Assuming this is where they go
        $file->move($absDir, $newBasename);

        // Delete old file if it exists and is different
        if (is_file($absPath)) {
            @unlink($absPath);
        }

        $image->image = '/uploads/images/' . $newBasename;
        $image->image_name = $newBasename;
        $image->save();

        return back()->with('success', 'Artwork replaced (' . $newBasename . ').');
    }

    public function alpha(Request $request, DtfImage $image)
    {
        $threshold = (int)$request->input('threshold', 128);
        $threshold = max(0, min(255, $threshold));

        $absPath = public_path(ltrim((string)$image->image, '/'));
        $absDir = dirname($absPath);
        $curBase = basename($absPath);

        if (!is_file($absPath)) {
            return back()->with('error', 'Image file not found on disk.');
        }

        // Versioning logic (DRY later)
        $dotPos = strrpos($curBase, '.');
        $nameOnly = $dotPos !== false ? substr($curBase, 0, $dotPos) : $curBase;
        $ext = $dotPos !== false ? substr($curBase, $dotPos + 1) : 'png';

        $base = $nameOnly;
        $n = 1;
        if (preg_match('/^(.*)edit(\d+)$/i', $nameOnly, $m)) {
            $base = $m[1];
            $n = max(1, (int)$m[2] + 1);
        }

        do {
            $nextBase = $base . 'edit' . $n . '.' . $ext;
            $n++;
        } while (file_exists($absDir . DIRECTORY_SEPARATOR . $nextBase));

        $nextAbs = $absDir . DIRECTORY_SEPARATOR . $nextBase;

        if (!@copy($absPath, $nextAbs)) {
            return back()->with('error', 'Could not create versioned file.');
        }

        $res = ImageHelper::thresholdAlphaMask($nextAbs, $threshold);
        if (!$res['success']) {
            @unlink($nextAbs);
            return back()->with('error', 'Alpha cleanup failed: ' . ($res['message'] ?? 'Unknown error'));
        }

        @unlink($absPath);

        $image->image = '/uploads/images/' . $nextBase;
        $image->save();

        // Update DPI
        try {
            $im = new Imagick($nextAbs);
            $pxW = $im->getImageWidth();
            $pxH = $im->getImageHeight();
            $im->clear();
            $im->destroy();

            $dpiX = (int)round($pxW / max(0.01, $image->width));
            $dpiY = (int)round($pxH / max(0.01, $image->height));

            ImageHelper::setPngDpi($nextAbs, $dpiX, $dpiY);
        } catch (Exception $e) {
            // DPI update failed but alpha was successful
        }

        return back()->with('success', 'Semi-transparent pixels removed (saved as ' . $nextBase . ').');
    }

    public function download(DtfImage $image)
    {
        $path = public_path(ltrim((string)$image->image, '/'));
        if (!is_file($path)) {
            abort(404);
        }

        $filename = $image->downloadFilename($path);
        return response()->download($path, $filename);
    }

    public function compare(DtfImage $image): JsonResponse
    {
        $originalRelative = '/' . ltrim((string)$image->image, '/');
        $originalAbs = public_path(ltrim((string)$image->image, '/'));

        if (!is_file($originalAbs)) {
            return response()->json([
                'success' => false,
                'message' => 'Original image file not found.',
            ], 404);
        }

        $version = md5(
            implode('|', [
                (string)$image->id,
                (string)$image->width,
                (string)$image->height,
                (string)@filemtime($originalAbs),
                (string)($image->updated_at?->timestamp ?? ''),
            ])
        );

        $compareDirRelative = 'uploads/compare';
        $compareDirAbs = public_path($compareDirRelative);
        if (!is_dir($compareDirAbs)) {
            @mkdir($compareDirAbs, 0777, true);
        }

        $compareBase = 'production_' . $image->id . '_' . $version . '.png';
        $compareAbs = $compareDirAbs . DIRECTORY_SEPARATOR . $compareBase;
        $compareRelative = '/' . trim($compareDirRelative . '/' . $compareBase, '/');

        if (!is_file($compareAbs)) {
            foreach (glob($compareDirAbs . DIRECTORY_SEPARATOR . 'production_' . $image->id . '_*.png') as $oldFile) {
                if (is_file($oldFile)) {
                    @unlink($oldFile);
                }
            }

            $prepared = ImageHelper::prepareForProduction(
                $originalAbs,
                $compareAbs,
                (float)$image->width,
                (float)$image->height,
                300
            );

            if (!($prepared['success'] ?? false)) {
                return response()->json([
                    'success' => false,
                    'message' => 'Failed to build production preview: ' . ($prepared['message'] ?? 'Unknown error'),
                ], 500);
            }
        }

        // Compare view should reflect production sizing rules (300 DPI) on both panes.
        $originalProbe = $this->probePhysicalSizeInches($originalAbs, true);
        $productionProbe = $this->probePhysicalSizeInches($compareAbs, true);

        return response()->json([
            'success' => true,
            'original_url' => $originalRelative,
            'production_url' => $compareRelative,
            'image_name' => $image->image_name ?: basename($originalRelative),
            'original_width_in' => (float) ($originalProbe['width_in'] ?? 0),
            'original_height_in' => (float) ($originalProbe['height_in'] ?? 0),
            'production_width_in' => (float) ($productionProbe['width_in'] ?? $image->width),
            'production_height_in' => (float) ($productionProbe['height_in'] ?? $image->height),
            'original_size_source' => $originalProbe['source'],
            'production_size_source' => $productionProbe['source'],
        ]);
    }
}
