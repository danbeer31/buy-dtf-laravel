<?php

namespace App\Http\Controllers;

use App\Helpers\ImageHelper;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\SavedImage;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Session;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Imagick;
use ImagickPixel;

class CartController extends Controller
{
    public function index()
    {
        $user = Auth::user();
        $business = $user->business;

        if (!$business) {
            return redirect()->route('home')->with('error', 'No business found for the current user.');
        }

        $cfg = [
            'preflight_url' => route('cart.preflight'),
            'put_url' => '/cart/put', // We'll handle the upload_id in the route
            'status_url' => route('cart.status'),
            'csrf_token' => csrf_token(),
            'csrf_token_name' => '_token',
            'accept' => ['image/png', 'image/svg+xml', 'application/pdf'],
            'max_size_mb' => 50,
        ];

        $order = DtfOrder::where('business_id', $business->id)
            ->where('status', 1)
            ->orderBy('id', 'desc')
            ->first();

        $items = [];
        if ($order) {
            $rows = DtfImage::where('dtforder_id', $order->id)
                ->orderBy('id', 'asc')
                ->get();

            foreach ($rows as $im) {
                $w = (float)$im->width;
                $h = (float)$im->height;
                $rat = ($h > 0.0001) ? ($w / $h) : 1.0;

                $price = null;
                $extended = null;
                $price_err = null;
                try {
                    $price = $im->get_price();
                    $extended = round(((float)$price) * max(1, (int)$im->quantity), 2);
                } catch (\Exception $e) {
                    $price_err = $e->getMessage();
                }

                $items[] = [
                    'id' => (int)$im->id,
                    'image' => (string)$im->image,
                    'name' => (string)$im->image_name ?: 'Customer Upload',
                    'notes' => (string)$im->image_notes,
                    'qty' => (int)$im->quantity,
                    'width' => $w,
                    'height' => $h,
                    'ratio' => $rat,
                    'uploaded' => $im->date_uploaded,
                    'saved' => SavedImage::where('business_id', $business->id)->where('image', $im->image)->exists(),
                    'price' => $price,
                    'extended' => $extended,
                    'price_error' => $price_err,
                ];
            }
        }

        return view('cart.index', [
            'items' => $items,
            'cfg' => $cfg,
            'order_id' => $order ? (int)$order->id : 0,
        ]);
    }

    public function preflight(Request $request)
    {
        $name = $request->input('name');
        $size = (int)$request->input('size');
        $mime = $request->input('mime');

        $accept = ['image/png', 'image/x-png', 'image/svg+xml', 'application/pdf'];
        $max_mb = 50; // increased back to 50 as requested

        if (!$name || !$mime || $size <= 0) {
            return response()->json(['success' => false, 'message' => 'Missing file metadata'], 422);
        }
        if (!in_array($mime, $accept)) {
            return response()->json(['success' => false, 'message' => 'Unsupported file type'], 415);
        }
        if ($size > ($max_mb * 1024 * 1024)) {
            return response()->json(['success' => false, 'message' => 'File too large'], 413);
        }

        $upload_id = (string) Str::ulid();
        $pending = Session::get('uploader_pending', []);
        $pending[$upload_id] = [
            'name' => $name,
            'size' => $size,
            'mime' => $mime,
            'business' => Auth::user()->business->id,
            'phase' => 'queued',
            'percent' => 0,
            'error' => null,
        ];
        Session::put('uploader_pending', $pending);

        return response()->json([
            'success' => true,
            'upload_id' => $upload_id,
            'accept' => $accept,
            'max_size_mb' => $max_mb,
            'use_chunked' => false,
        ]);
    }

    public function put(Request $request, $upload_id = null)
    {
        $pending = Session::get('uploader_pending', []);

        $file = $request->file('file');
        if (!$file) {
            return response()->json(['success' => false, 'message' => 'Upload failed'], 400);
        }

        $business = Auth::user()->business;
        $clientName = $request->input('name', $file->getClientOriginalName());
        $clientSize = (int)$request->input('size', $file->getSize());
        $mime = $request->input('mime', $file->getMimeType());
        $sourceOrderId = $request->input('source_order_id', '');

        if ($upload_id) {
            $pending[$upload_id] = array_merge($pending[$upload_id] ?? [], [
                'phase' => 'processing',
                'percent' => 5,
            ]);
            Session::put('uploader_pending', $pending);
        }

        try {
            $result = $this->processAndAttach($file->getRealPath(), $mime, $clientName, $business->id, $sourceOrderId, $clientSize);

            if ($upload_id && isset($pending[$upload_id])) {
                $pending[$upload_id]['phase'] = 'ready';
                $pending[$upload_id]['percent'] = 100;
                $pending[$upload_id]['order_id'] = $result['order_id'];
                $pending[$upload_id]['dtfimage_id'] = $result['dtfimage_id'];
                $pending[$upload_id]['meta'] = $result['meta'];
                Session::put('uploader_pending', $pending);
            }

            return response()->json([
                'success' => true,
                'upload_id' => $upload_id,
                'status' => 'uploaded',
                'processing' => ['started' => true, 'percent' => 100],
                'order_id' => $result['order_id'],
                'dtfimage_id' => $result['dtfimage_id'],
                'meta' => $result['meta'],
            ]);

        } catch (\Throwable $e) {
            Log::error('Upload processing failed: ' . $e->getMessage());
            if ($upload_id && isset($pending[$upload_id])) {
                $pending[$upload_id]['phase'] = 'error';
                $pending[$upload_id]['error'] = $e->getMessage();
                Session::put('uploader_pending', $pending);
            }
            return response()->json(['success' => false, 'message' => $e->getMessage()], 500);
        }
    }

    public function status()
    {
        $pending = Session::get('uploader_pending', []);
        $items = [];
        foreach ($pending as $id => $data) {
            $items[] = [
                'upload_id' => $id,
                'phase' => $data['phase'],
                'percent' => $data['percent'],
                'error' => $data['error'] ?? null,
            ];
        }
        return response()->json(['items' => $items]);
    }

    protected function processAndAttach(string $tmpPath, string $mime, string $clientName, int $business_id, string $sourceOrderId = '', int $clientSize = 0): array
    {
        $order = DtfOrder::where('business_id', $business_id)
            ->where('status', 1)
            ->orderBy('id', 'desc')
            ->first();

        if (!$order) {
            $order = DtfOrder::create([
                'business_id' => $business_id,
                'status' => 1,
                'order_date' => now(),
            ]);
        }

        $shaOriginal = @hash_file('sha256', $tmpPath) ?: null;

        $workPng = storage_path('app/tmp/' . Str::ulid() . '.png');
        if (!is_dir(dirname($workPng))) {
            mkdir(dirname($workPng), 0777, true);
        }

        if ($mime === 'image/png' || $mime === 'image/x-png') {
            copy($tmpPath, $workPng);
        } elseif ($mime === 'image/svg+xml') {
            $im = new Imagick();
            $im->setBackgroundColor(new ImagickPixel('transparent'));
            $im->readImage($tmpPath);
            $im->setImageFormat('png32');
            $im->setImageUnits(Imagick::RESOLUTION_PIXELSPERINCH);
            $im->setImageResolution(300, 300);
            $im->writeImage($workPng);
            $im->clear();
            $im->destroy();
        } elseif ($mime === 'application/pdf') {
            $im = new Imagick();
            $im->setResolution(300, 300);
            $im->readImage($tmpPath . '[0]');
            $im->setImageFormat('png32');
            $im->setImageAlphaChannel(Imagick::ALPHACHANNEL_SET);
            $im->writeImage($workPng);
            $im->clear();
            $im->destroy();
        } else {
            throw new \RuntimeException('Only PNG, SVG, or PDF are allowed.');
        }

        // Cleanup (trim, threshold, set pHYs)
        ImageHelper::thresholdAlphaMask($workPng);
        ImageHelper::trimTransparentBorder($workPng);
        ImageHelper::setPngDpi($workPng, 300, 300);

        $shaBitmap = @hash_file('sha256', $workPng) ?: null;

        $im = new Imagick($workPng);
        $pxW = $im->getImageWidth();
        $pxH = $im->getImageHeight();
        $im->clear();
        $im->destroy();

        $inDpi = 300;
        $widthIn = $pxW > 0 ? round($pxW / $inDpi, 3) : 0.000;
        $heightIn = $pxH > 0 ? round($pxH / $inDpi, 3) : 0.000;

        $prefixId = ($sourceOrderId !== '') ? $sourceOrderId : (string)$order->id;
        $relativeName = 'uploads/images/' . uniqid('DTF_API_' . $prefixId . '_') . '.png';
        $publicPath = public_path($relativeName);

        if (!is_dir(dirname($publicPath))) {
            mkdir(dirname($publicPath), 0777, true);
        }

        copy($workPng, $publicPath);
        @unlink($workPng);

        $nativeBase = strtolower(basename($clientName));
        if ($clientSize <= 0) $clientSize = (int)@filesize($tmpPath);

        $img = DtfImage::create([
            'dtforder_id' => $order->id,
            'image' => '/' . $relativeName,
            'image_name' => $this->deriveImageName($clientName),
            'image_notes' => '',
            'width' => $widthIn,
            'height' => $heightIn,
            'quantity' => 1,
            'production' => 0,
            'date_uploaded' => now(),
            'native_filename' => $nativeBase,
            'file_size' => $clientSize,
            'sha256_original' => $shaOriginal,
            'sha256_bitmap' => $shaBitmap,
        ]);

        return [
            'order_id' => $order->id,
            'dtfimage_id' => $img->id,
            'meta' => [
                'width_px' => $pxW,
                'height_px' => $pxH,
                'width_in' => $widthIn,
                'height_in' => $heightIn,
            ]
        ];
    }

    protected function deriveImageName(string $clientName): string
    {
        $name = basename($clientName);
        $name = preg_replace('/\.(png|svg|pdf)$/i', '', $name);
        return Str::limit($name, 100);
    }

    public function updateImage(Request $request, $id)
    {
        $img = DtfImage::findOrFail($id);
        if ($img->dtfOrder->business_id !== Auth::user()->business->id) {
            abort(403);
        }

        $img->update([
            'quantity' => (int)$request->input('quantity', $img->quantity),
            'width' => (float)$request->input('width', $img->width),
            'height' => (float)$request->input('height', $img->height),
            'image_name' => $request->input('image_name', $img->image_name),
            'image_notes' => $request->input('image_notes', $img->image_notes),
        ]);

        if ($request->expectsJson()) {
            return response()->json(['success' => true]);
        }

        return back()->with('success', 'Image updated.');
    }

    public function delete($id)
    {
        $img = DtfImage::findOrFail($id);
        if ($img->dtfOrder->business_id !== Auth::user()->business->id) {
            abort(403);
        }

        $img->delete();

        if (request()->expectsJson()) {
            return response()->json(['success' => true]);
        }

        return back()->with('success', 'Image removed.');
    }

    public function duplicate($id)
    {
        $img = DtfImage::findOrFail($id);
        if ($img->dtfOrder->business_id !== Auth::user()->business->id) {
            abort(403);
        }

        $newImg = $img->replicate();
        $newImg->date_uploaded = now();
        $newImg->save();

        if (request()->expectsJson()) {
            return response()->json([
                'success' => true,
                'dtfimage_id' => $newImg->id,
                'order_id' => $newImg->dtforder_id,
            ]);
        }

        return back()->with('success', 'Image duplicated.');
    }

    public function myImages(Request $request)
    {
        $business = Auth::user()->business;
        $query = SavedImage::where('business_id', $business->id);

        if ($q = $request->input('q')) {
            $query->where('image_name', 'like', "%{$q}%");
        }

        $images = $query->orderBy('id', 'desc')->paginate(20);

        return response()->json([
            'success' => true,
            'items' => $images->map(function($img) {
                return [
                    'id' => $img->id,
                    'name' => $img->image_name,
                    'thumb' => $img->image,
                    'uploaded_fmt' => $img->created_at ? $img->created_at->format('M j, Y') : '',
                ];
            }),
            'has_more' => $images->hasMorePages(),
        ]);
    }

    public function useSaved(Request $request)
    {
        $business = Auth::user()->business;
        $saved_id = (int)$request->input('saved_id');
        $saved = SavedImage::where('id', $saved_id)->where('business_id', $business->id)->firstOrFail();

        $order = $business->open_order();
        if (!$order) {
            $order = DtfOrder::create([
                'business_id' => $business->id,
                'status' => 1,
                'order_date' => now(),
            ]);
        }

        // FuelPHP logic tries to find an existing DtfImage by path to get metadata
        // For simplicity, we'll try to find any DtfImage with this path or just use defaults
        $sourceImg = DtfImage::where('image', $saved->image)->first();

        $newImg = DtfImage::create([
            'dtforder_id' => $order->id,
            'image' => $saved->image,
            'image_name' => $saved->image_name,
            'image_notes' => $saved->image_notes ?? '',
            'width' => $saved->width ?: ($sourceImg ? $sourceImg->width : 0),
            'height' => $saved->height ?: ($sourceImg ? $sourceImg->height : 0),
            'width_ratio' => $sourceImg ? $sourceImg->width_ratio : null,
            'height_ratio' => $sourceImg ? $sourceImg->height_ratio : null,
            'orig_width' => $sourceImg ? $sourceImg->orig_width : null,
            'orig_height' => $sourceImg ? $sourceImg->orig_height : null,
            'native_filename' => $sourceImg ? $sourceImg->native_filename : basename($saved->image),
            'file_size' => $sourceImg ? $sourceImg->file_size : 0,
            'sha256_original' => $sourceImg ? $sourceImg->sha256_original : null,
            'sha256_bitmap' => $sourceImg ? $sourceImg->sha256_bitmap : null,
            'quantity' => 1,
            'production' => 0,
            'date_uploaded' => now(),
        ]);

        return response()->json([
            'success' => true,
            'id' => $newImg->id,
            'order_id' => $order->id,
        ]);
    }

    public function saveImage(Request $request, $id)
    {
        $img = DtfImage::findOrFail($id);
        $business = Auth::user()->business;

        if ($img->dtfOrder->business_id !== $business->id) {
            abort(403);
        }

        $saved = SavedImage::firstOrCreate(
            ['business_id' => $business->id, 'image' => $img->image],
            [
                'image_name' => $img->image_name,
                'image_notes' => $img->image_notes,
                'width' => $img->width,
                'height' => $img->height,
                'date_uploaded' => now(),
            ]
        );

        return response()->json(['success' => true]);
    }

    public function renderDtfImageCard(Request $request)
    {
        $id = $request->input('dtfimage_id');
        $img = DtfImage::findOrFail($id);

        $it = [
            'id' => (int)$img->id,
            'image' => (string)$img->image,
            'name' => (string)$img->image_name ?: 'Customer Upload',
            'notes' => (string)$img->image_notes,
            'qty' => (int)$img->quantity,
            'width' => (float)$img->width,
            'height' => (float)$img->height,
            'ratio' => $img->height > 0 ? $img->width / $img->height : 1,
            'uploaded' => $img->date_uploaded,
            'saved' => SavedImage::where('business_id', Auth::user()->business->id)->where('image', $img->image)->exists(),
        ];

        try {
            $it['price'] = $img->get_price();
            $it['extended'] = round(((float)$it['price']) * max(1, (int)$img->quantity), 2);
        } catch (\Exception $e) {
            $it['price_error'] = $e->getMessage();
        }

        $html = view('cart._dtfimage_card', ['it' => $it])->render();

        return response()->json([
            'success' => true,
            'html' => $html,
        ]);
    }

    public function dupeCheck(Request $request)
    {
        $business = Auth::user()->business;
        $filename = $request->input('filename');
        $size = (int)$request->input('size');

        $matches = DtfImage::whereHas('dtfOrder', function($q) use ($business) {
            $q->where('business_id', $business->id);
        })
        ->where('native_filename', strtolower(basename($filename)))
        ->where('file_size', $size)
        ->orderBy('id', 'desc')
        ->get()
        ->unique('image');

        return response()->json([
            'success' => true,
            'matches' => $matches->map(function($m) {
                return [
                    'id' => $m->id,
                    'image_name' => $m->image_name,
                    'native_filename' => $m->native_filename,
                    'file_size' => $m->file_size,
                    'path' => $m->image,
                    'thumb' => $m->image,
                    'uploaded' => $m->date_uploaded ? $m->date_uploaded->format('Y-m-d H:i:s') : '',
                    'sha256' => $m->sha256_original,
                ];
            })->values()
        ]);
    }

    public function dupeCheckHash(Request $request)
    {
        $business = Auth::user()->business;
        $sha256 = $request->input('sha256');

        $matches = DtfImage::whereHas('dtfOrder', function($q) use ($business) {
            $q->where('business_id', $business->id);
        })
        ->where('sha256_original', $sha256)
        ->orderBy('id', 'desc')
        ->get()
        ->unique('image');

        return response()->json([
            'success' => true,
            'matches' => $matches->map(function($m) {
                return [
                    'id' => $m->id,
                    'image_name' => $m->image_name,
                    'native_filename' => $m->native_filename,
                    'file_size' => $m->file_size,
                    'path' => $m->image,
                    'thumb' => $m->image,
                    'uploaded' => $m->date_uploaded ? $m->date_uploaded->format('Y-m-d H:i:s') : '',
                    'sha256' => $m->sha256_original,
                ];
            })->values()
        ]);
    }

    public function useExisting(Request $request)
    {
        $business = Auth::user()->business;
        $id = $request->input('dtfimage_id');
        $img = DtfImage::findOrFail($id);

        if ($img->dtfOrder->business_id !== $business->id) {
            abort(403);
        }

        $order = $business->open_order();
        if (!$order) {
            $order = DtfOrder::create([
                'business_id' => $business->id,
                'status' => 1,
                'order_date' => now(),
            ]);
        }

        $newImg = $img->replicate();
        $newImg->dtforder_id = $order->id;
        $newImg->date_uploaded = now();
        $newImg->save();

        return response()->json([
            'success' => true,
            'id' => $newImg->id,
            'order_id' => $order->id,
        ]);
    }

    public function indicator()
    {
        $business = Auth::user()->business;
        if (!$business) return response()->json(['count' => 0]);

        $order = $business->open_order();
        if (!$order) return response()->json(['count' => 0]);

        $count = DtfImage::where('dtforder_id', $order->id)->sum('quantity');
        return response()->json(['count' => (int)$count]);
    }
}
