<?php

namespace App\Http\Controllers;

use App\Helpers\ImageHelper;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\SavedImage;
use App\Services\GangSheetPricingService;
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
                    $extended = $im->get_total();
                } catch (\Exception $e) {
                    $price_err = $e->getMessage();
                }

                $other_sizes_raw = DtfImage::where('image', $im->image)
                    ->selectRaw('width, height, count(*) as count')
                    ->groupBy('width', 'height')
                    ->orderBy('width', 'asc')
                    ->get();

                $filtered_sizes = [];
                foreach ($other_sizes_raw as $os) {
                    $is_duplicate = false;
                    foreach ($filtered_sizes as $fs) {
                        if (abs($os->width - $fs->width) <= 0.10 && abs($os->height - $fs->height) <= 0.10) {
                            $is_duplicate = true;
                            break;
                        }
                    }
                    if (!$is_duplicate) {
                        $filtered_sizes[] = $os;
                    }
                }

                $items[] = [
                    'id' => (int)$im->id,
                    'image' => (string)$im->image,
                    'thumbnail' => $im->thumbnail ?: (string)$im->image,
                    'item_type' => $im->item_type ?: 'standard',
                    'item_meta' => $im->getGangSheetMeta(),
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
                    'other_sizes' => $filtered_sizes
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
            Log::error('Upload processing failed: ' . $e->getMessage(), [
                'user_id' => Auth::id(),
                'business_id' => $business->id ?? null,
                'email' => Auth::user()->email ?? null,
                'mime' => $mime ?? null,
                'filename' => $clientName ?? null,
                'size' => $clientSize ?? null,
                'upload_id' => $upload_id,
            ]);
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
        $skipHeavyCleanup = false;
        $maxCleanupMegapixels = (float) env('UPLOAD_CLEANUP_MAX_MEGAPIXELS', 40);

        if ($mime === 'image/png' || $mime === 'image/x-png') {
            if (!@copy($tmpPath, $workPng)) {
                throw new \RuntimeException('Failed to stage uploaded PNG.');
            }

            // Validate decode early, but treat Imagick cache exhaustion as a "large file" path.
            try {
                $probe = new Imagick();
                $probe->pingImage($workPng);
                $probe->clear();
                $probe->destroy();
            } catch (\Throwable $e) {
                $decodeMessage = (string) $e->getMessage();
                $isCacheError = stripos($decodeMessage, 'cache resources exhausted') !== false;
                if ($isCacheError) {
                    $skipHeavyCleanup = true;
                    Log::warning('Imagick cache exhausted during PNG probe; using lightweight upload path', [
                        'file' => $clientName,
                        'message' => $decodeMessage,
                    ]);
                } else {
                    $sizeProbe = @getimagesize($workPng);
                    if (!is_array($sizeProbe) || !isset($sizeProbe[0], $sizeProbe[1])) {
                        @unlink($workPng);
                        throw new \RuntimeException('Uploaded PNG appears corrupted or incomplete. Please re-export and upload again.');
                    }
                }
            }

            // Avoid cache exhaustion on very large rasters.
            // We still attempt trim on all files; this flag only skips alpha-threshold + DPI rewrite.
            $probe = @getimagesize($workPng);
            if (is_array($probe) && isset($probe[0], $probe[1])) {
                $megapixels = ((float) $probe[0] * (float) $probe[1]) / 1000000;
                if ($megapixels > $maxCleanupMegapixels) {
                    $skipHeavyCleanup = true;
                    Log::warning('Skipping heavy upload cleanup for large PNG', [
                        'file' => $clientName,
                        'width' => (int) $probe[0],
                        'height' => (int) $probe[1],
                        'megapixels' => round($megapixels, 2),
                        'threshold' => $maxCleanupMegapixels,
                    ]);
                }
            }
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

        // Always trim transparent border (required for accurate print dimensions).
        $trimResult = ImageHelper::trimTransparentBorder($workPng);
        if (!($trimResult['success'] ?? false)) {
            throw new \RuntimeException('Failed while trimming transparent border: ' . ($trimResult['message'] ?? 'Unknown error'));
        }

        // Heavy cleanup (alpha threshold) can be skipped for very large rasters.
        if (!$skipHeavyCleanup) {
            $alphaResult = ImageHelper::thresholdAlphaMask($workPng);
            if (!($alphaResult['success'] ?? false)) {
                throw new \RuntimeException('Failed while cleaning PNG alpha channel: ' . ($alphaResult['message'] ?? 'Unknown error'));
            }
        }

        // Always set pHYs/300 DPI metadata so downstream RIP/software dimensions stay correct.
        $dpiResult = ImageHelper::setPngDpi($workPng, 300, 300);
        if (!($dpiResult['success'] ?? false)) {
            throw new \RuntimeException('Failed while setting PNG DPI metadata: ' . ($dpiResult['message'] ?? 'Unknown error'));
        }

        $imgSize = @getimagesize($workPng);
        if (!is_array($imgSize) || !isset($imgSize[0], $imgSize[1])) {
            throw new \RuntimeException('Unable to read image dimensions after processing.');
        }
        $pxW = (int) $imgSize[0];
        $pxH = (int) $imgSize[1];
        $shaBitmap = @hash_file('sha256', $workPng) ?: null;

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

        // Generate thumbnail
        $thumbRelativeName = 'uploads/images/thumbs/' . basename($relativeName);
        $thumbPublicPath = public_path($thumbRelativeName);
        if (!is_dir(dirname($thumbPublicPath))) {
            mkdir(dirname($thumbPublicPath), 0777, true);
        }
        $thumbOk = ImageHelper::generateThumbnail($workPng, $thumbPublicPath);
        if (!($thumbOk['success'] ?? false)) {
            // Fall back to using the original file as thumbnail reference.
            $thumbRelativeName = $relativeName;
        }

        @unlink($workPng);

        $nativeBase = strtolower(basename($clientName));
        if ($clientSize <= 0) $clientSize = (int)@filesize($tmpPath);

        $img = DtfImage::createUsingExistingColumns([
            'dtforder_id' => $order->id,
            'image' => '/' . $relativeName,
            'thumbnail' => '/' . $thumbRelativeName,
            'upload_mime' => $mime,
            'item_type' => 'standard',
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
                'cleanup_skipped' => $skipHeavyCleanup,
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

        $quantity = max(1, (int)$request->input('quantity', $img->quantity));
        $updates = [
            'quantity' => $quantity,
            'image_name' => $request->input('image_name', $img->image_name),
            'image_notes' => $request->input('image_notes', $img->image_notes),
        ];

        if ($img->isGangSheet()) {
            $meta = $img->getGangSheetMeta();
            $sizeKey = (string)($meta['size_key'] ?? '');
            $sizes = app(GangSheetPricingService::class)->sizes();
            if (isset($sizes[$sizeKey])) {
                $updates['width'] = (float)$sizes[$sizeKey]['width'];
                $updates['height'] = (float)$sizes[$sizeKey]['length'];
            }
            $updates['price'] = app(GangSheetPricingService::class)->unitPrice($sizeKey, $quantity);
        } else {
            $updates['width'] = (float)$request->input('width', $img->width);
            $updates['height'] = (float)$request->input('height', $img->height);
        }

        $img->update($updates);
        $img->refresh();

        $price = null;
        $extended = null;
        $priceError = null;
        try {
            $price = (float) $img->get_price();
            $extended = (float) $img->get_total();
        } catch (\Exception $e) {
            $priceError = $e->getMessage();
        }

        if ($request->expectsJson()) {
            return response()->json([
                'success' => true,
                'quantity' => (int) $img->quantity,
                'width' => (float) $img->width,
                'height' => (float) $img->height,
                'price' => $price,
                'extended' => $extended,
                'price_error' => $priceError,
            ]);
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
        $q = $request->input('q');

        // We want to find unique images from both SavedImage and DtfImage tables
        // Deduplicate by the 'image' path, taking the most recent one.

        // 1. Get SavedImages
        $savedQuery = SavedImage::where('business_id', $business->id);
        if ($q) {
            $savedQuery->where('image_name', 'like', "%{$q}%");
        }
        $savedImages = $savedQuery->get()->map(function($img) {
            return [
                'id' => $img->id,
                'dtfimage_id' => null,
                'name' => $img->image_name,
                'image' => $img->image,
                'thumbnail' => $img->thumbnail,
                'date' => $img->created_at,
                'source' => 'saved'
            ];
        });

        // 2. Get DtfImages from all orders of this business
        $dtfQuery = DtfImage::whereHas('dtfOrder', function($query) use ($business) {
            $query->where('business_id', $business->id);
        });
        if ($q) {
            $dtfQuery->where('image_name', 'like', "%{$q}%");
        }
        $dtfImages = $dtfQuery->orderBy('id', 'desc')->get()->map(function($img) {
            return [
                'id' => null,
                'dtfimage_id' => $img->id,
                'name' => $img->image_name,
                'image' => $img->image,
                'thumbnail' => $img->thumbnail,
                'date' => $img->date_uploaded,
                'source' => 'ordered'
            ];
        });

        // 3. Merge and Deduplicate by image path
        $allImages = $savedImages->concat($dtfImages)
            ->sortByDesc(function($item) {
                return $item['date'] ? $item['date']->timestamp : 0;
            })
            ->unique('image')
            ->values();

        // 4. Paginate manually
        $perPage = (int)$request->input('per_page', 10);
        $page = (int)$request->input('page', 1);
        $offset = ($page - 1) * $perPage;

        $pagedItems = $allImages->slice($offset, $perPage);
        $hasMore = $allImages->count() > ($offset + $perPage);

        return response()->json([
            'success' => true,
            'items' => $pagedItems->map(function($img) {
                return [
                    'id' => $img['id'],
                    'dtfimage_id' => $img['dtfimage_id'],
                    'name' => $img['name'],
                    'thumb' => $img['thumbnail'] ?: $img['image'],
                    'image' => $img['image'],
                    'uploaded_fmt' => $img['date'] ? $img['date']->format('M j, Y') : '',
                ];
            }),
            'has_more' => $hasMore,
            'next_page' => $hasMore ? $page + 1 : null,
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

        $newImg = DtfImage::createUsingExistingColumns([
            'dtforder_id' => $order->id,
            'image' => $saved->image,
            'item_type' => 'standard',
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
            'upload_mime' => $sourceImg ? $sourceImg->upload_mime : null,
            'quantity' => 1,
            'production' => 0,
            'date_uploaded' => now(),
        ]);

        if ($request->expectsJson()) {
            return response()->json([
                'success' => true,
                'id' => $newImg->id,
                'order_id' => $order->id,
            ]);
        }

        return redirect()->route('cart.index')->with('success', 'Image added to order.');
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
                'thumbnail' => $img->thumbnail,
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
            'thumbnail' => $img->thumbnail ?: (string)$img->image,
            'item_type' => $img->item_type ?: 'standard',
            'item_meta' => $img->getGangSheetMeta(),
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
            $it['extended'] = $img->get_total();
        } catch (\Exception $e) {
            $it['price_error'] = $e->getMessage();
        }

        $w = (float)$img->width;
        $h = (float)$img->height;

        $other_sizes_raw = DtfImage::where('image', $img->image)
            ->selectRaw('width, height, count(*) as count')
            ->groupBy('width', 'height')
            ->orderBy('width', 'asc')
            ->get();

        $filtered_sizes = [];
        foreach ($other_sizes_raw as $os) {
            $is_duplicate = false;
            foreach ($filtered_sizes as $fs) {
                if (abs($os->width - $fs->width) <= 0.10 && abs($os->height - $fs->height) <= 0.10) {
                    $is_duplicate = true;
                    break;
                }
            }
            if (!$is_duplicate) {
                $filtered_sizes[] = $os;
            }
        }

        $it['other_sizes'] = $filtered_sizes;

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
                    'thumb' => $m->thumbnail ?: $m->image,
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
                    'thumb' => $m->thumbnail ?: $m->image,
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

        $newImg = DtfImage::createUsingExistingColumns([
            'dtforder_id' => $order->id,
            'image' => $img->image,
            'thumbnail' => $img->thumbnail,
            'native_filename' => $img->native_filename,
            'file_size' => $img->file_size,
            'sha256_original' => $img->sha256_original,
            'sha256_bitmap' => $img->sha256_bitmap,
            'image_name' => $img->image_name,
            'width' => $img->width,
            'height' => $img->height,
            'width_ratio' => $img->width_ratio,
            'height_ratio' => $img->height_ratio,
            'orig_width' => $img->orig_width,
            'orig_height' => $img->orig_height,
            'quantity' => 1,
            'date_uploaded' => now(),
            'production' => 0,
        ]);

        if ($request->expectsJson()) {
            return response()->json([
                'success' => true,
                'id' => $newImg->id,
                'order_id' => $order->id,
            ]);
        }

        return redirect()->route('cart.index')->with('success', 'Image added to order.');
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
