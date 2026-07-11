<?php

namespace App\Http\Controllers;

use App\Helpers\ImageHelper;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Services\GangSheetPricingService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Str;
use Imagick;
use ImagickPixel;

class GangSheetController extends Controller
{
    public function index(GangSheetPricingService $pricing)
    {
        return view('gang-sheet.index', [
            'sizes' => $pricing->sizes(),
        ]);
    }

    public function store(Request $request, GangSheetPricingService $pricing)
    {
        $validated = $request->validate([
            'sheet_size' => 'required|string',
            'quantity' => 'required|integer|min:1|max:500',
            'notes' => 'nullable|string|max:1000',
            'file' => 'required|file|max:51200|mimes:png,pdf|mimetypes:image/png,image/x-png,application/pdf,application/x-pdf',
        ]);

        $sizeKey = strtolower($validated['sheet_size']);
        $sizes = $pricing->sizes();
        if (!isset($sizes[$sizeKey])) {
            return back()->withErrors(['sheet_size' => 'Invalid gang sheet size selected.'])->withInput();
        }

        $business = Auth::user()->business;
        if (!$business) {
            return redirect()->route('home')->with('error', 'No business found for the current user.');
        }

        $order = DtfOrder::where('business_id', $business->id)
            ->where('status', 1)
            ->orderBy('id', 'desc')
            ->first();

        if (!$order) {
            $order = DtfOrder::create([
                'business_id' => $business->id,
                'status' => 1,
                'order_date' => now(),
            ]);
        }

        $upload = $validated['file'];
        $clientName = $upload->getClientOriginalName();
        $clientMime = (string)$upload->getMimeType();
        $clientSize = (int)$upload->getSize();

        $workPng = storage_path('app/tmp/' . Str::ulid() . '.png');
        if (!is_dir(dirname($workPng))) {
            mkdir(dirname($workPng), 0777, true);
        }

        if ($clientMime === 'image/png' || $clientMime === 'image/x-png') {
            copy($upload->getRealPath(), $workPng);
        } else {
            $im = new Imagick();
            $im->setResolution(300, 300);
            $im->setBackgroundColor(new ImagickPixel('transparent'));
            $im->readImage($upload->getRealPath() . '[0]');
            $im->setImageFormat('png32');
            $im->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            $im->writeImage($workPng);
            $im->clear();
            $im->destroy();
        }

        ImageHelper::setPngDpi($workPng, 300, 300);

        $relativeName = 'uploads/images/' . uniqid('DTF_GANG_' . $order->id . '_') . '.png';
        $publicPath = public_path($relativeName);
        if (!is_dir(dirname($publicPath))) {
            mkdir(dirname($publicPath), 0777, true);
        }
        copy($workPng, $publicPath);

        $thumbRelative = 'uploads/images/thumbs/' . basename($relativeName);
        $thumbPath = public_path($thumbRelative);
        if (!is_dir(dirname($thumbPath))) {
            mkdir(dirname($thumbPath), 0777, true);
        }
        ImageHelper::generateThumbnail($workPng, $thumbPath);

        @unlink($workPng);

        $quantity = (int)$validated['quantity'];
        $unitPrice = $pricing->unitPrice($sizeKey, $quantity);
        $sizeInfo = $sizes[$sizeKey];
        $originalBase = pathinfo($clientName, PATHINFO_FILENAME);

        DtfImage::createUsingExistingColumns([
            'dtforder_id' => $order->id,
            'image' => '/' . $relativeName,
            'thumbnail' => '/' . $thumbRelative,
            'native_filename' => strtolower($clientName),
            'file_size' => $clientSize,
            'sha256_original' => @hash_file('sha256', $upload->getRealPath()) ?: null,
            'sha256_bitmap' => @hash_file('sha256', $publicPath) ?: null,
            'upload_mime' => $clientMime,
            'item_type' => 'gang_sheet',
            'item_meta' => [
                'size_key' => $sizeKey,
                'width' => $sizeInfo['width'],
                'length' => $sizeInfo['length'],
                'upload_path' => '/' . $relativeName,
                'original_file_name' => $clientName,
                'mime_type' => $clientMime,
                'file_size' => $clientSize,
                'notes' => trim((string)($validated['notes'] ?? '')),
                'pricing_version' => GangSheetPricingService::PRICING_VERSION,
                'unit_price_snapshot' => $unitPrice,
            ],
            'image_name' => 'Gang Sheet ' . strtoupper($sizeKey) . ' - ' . Str::limit($originalBase, 80),
            'image_notes' => trim((string)($validated['notes'] ?? '')),
            'width' => (float)$sizeInfo['width'],
            'height' => (float)$sizeInfo['length'],
            'quantity' => $quantity,
            'price' => $unitPrice,
            'production' => 0,
            'date_uploaded' => now(),
        ]);

        return redirect()->route('cart.index')->with('success', 'Gang sheet added to cart.');
    }
}
