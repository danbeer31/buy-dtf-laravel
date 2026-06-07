<?php

namespace App\Http\Controllers;

use App\Models\DtfImage;
use App\Helpers\ImageHelper;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Log;
use Imagick;
use ImagickPixel;

class ImageEditorController extends Controller
{
    public function edit(DtfImage $image)
    {
        return view('cart.editor', compact('image'));
    }

    public function process(Request $request, DtfImage $image)
    {
        $action = $request->input('action');
        $absPath = public_path(ltrim((string)$image->image, '/'));

        if (!is_file($absPath)) {
            return response()->json(['success' => false, 'message' => 'Image file not found.'], 404);
        }

        try {
            $im = new Imagick($absPath);

            // Create a backup of the original if this is the first edit?
            // Actually the current system seems to overwrite or version.
            // OrderImageController versioned them. Let's do the same.

            $absDir = dirname($absPath);
            $curBase = basename($absPath);
            $dotPos = strrpos($curBase, '.');
            $nameOnly = $dotPos !== false ? substr($curBase, 0, $dotPos) : $curBase;
            $ext = $dotPos !== false ? substr($curBase, $dotPos + 1) : 'png';

            $base = $nameOnly;
            if (preg_match('/^(.*)_edit(\d+)$/i', $nameOnly, $m)) {
                $base = $m[1];
                $n = (int)$m[2] + 1;
            } else {
                $n = 1;
            }

            do {
                $nextBase = $base . '_edit' . $n . '.' . $ext;
                $n++;
            } while (file_exists($absDir . DIRECTORY_SEPARATOR . $nextBase));

            $nextAbs = $absDir . DIRECTORY_SEPARATOR . $nextBase;

            if ($action === 'remove_background') {
                $fuzz = $request->input('fuzz', 10);
                $fuzzValue = ($fuzz / 100) * $im->getQuantum();
                $color = $request->input('color', 'white');
                // Transparent background removal
                $im->transparentPaintImage($color, 0, $fuzzValue, false);
            } elseif ($action === 'change_color') {
                $fromColor = $request->input('from_color');
                $toColor = $request->input('to_color');
                $fuzz = $request->input('fuzz', 10);
                $fuzzValue = ($fuzz / 100) * $im->getQuantum();
                $im->opaquePaintImage($fromColor, $toColor, $fuzzValue, false);
            } elseif ($action === 'mask_color') {
                $toColor = $request->input('to_color');
                $x = $request->input('x');
                $y = $request->input('y');
                $fuzz = $request->input('fuzz', 10);
                $fuzzValue = ($fuzz / 100) * $im->getQuantum();

                // Get the color at the clicked point
                $pixel = $im->getImagePixelColor($x, $y);

                // floodFillPaintImage(fill_color, fuzz, border_color, x, y, invert)
                // We use the pixel color as border_color and invert=false to fill that color region
                $im->floodFillPaintImage($toColor, $fuzzValue, $pixel, $x, $y, false);
            } elseif ($action === 'reduce_colors') {
                $colors = (int)$request->input('colors', 8);
                $im->quantizeImage($colors, Imagick::COLORSPACE_RGB, 0, false, false);
            } elseif ($action === 'revert') {
                $absDir = dirname($absPath);
                $curBase = basename($absPath);

                // Try to find the original
                $base = $curBase;
                if (preg_match('/^(.*)_edit\d+\.(.*)$/i', $curBase, $m)) {
                    $base = $m[1] . '.' . $m[2];
                }

                if ($base !== $curBase && file_exists($absDir . DIRECTORY_SEPARATOR . $base)) {
                    // We found the original!
                    // Delete the current edited file if it's an edit
                    @unlink($absPath);

                    $image->image = '/uploads/images/' . $base;
                    $image->save();

                    return response()->json([
                        'success' => true,
                        'image_url' => $image->image . '?t=' . time(),
                        'reverted' => true
                    ]);
                } else {
                    return response()->json(['success' => false, 'message' => 'Original image not found or already at original.']);
                }
            }

            $im->setImageFormat('png');
            $im->writeImage($nextAbs);
            $im->clear();
            $im->destroy();

            // Update image record
            $image->image = '/uploads/images/' . $nextBase;
            $image->save();

            return response()->json([
                'success' => true,
                'image_url' => $image->image . '?t=' . time(),
                'next_base' => $nextBase
            ]);

        } catch (\Exception $e) {
            return response()->json(['success' => false, 'message' => $e->getMessage()], 500);
        }
    }
}
