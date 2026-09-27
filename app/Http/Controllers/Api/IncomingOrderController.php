<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Services\IncomingOrders\IncomingOrderV1Receiver;
use App\Services\IncomingOrders\JobCardRenderer;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;

class IncomingOrderController extends Controller
{
    public function store(Request $request, IncomingOrderV1Receiver $receiver)
    {
        $rawBody = (string) $request->getContent();
        if ($this->isV1Request($request, $rawBody)) {
            return $receiver->handle($request, $rawBody);
        }

        return $this->storeLegacy($request);
    }

    public function capabilities(JobCardRenderer $jobCardRenderer)
    {
        $receiverEnabled = (bool) config('incoming_order.receiver_enabled', false);
        $rendererReadiness = $jobCardRenderer->readiness();
        $labelEnabled = $receiverEnabled
            && (bool) config('incoming_order.job_label_enabled', false)
            && $rendererReadiness['ready'];

        return response()->json([
            'endpoint' => '/api/incomingorder',
            'capabilities' => [
                'receiver_idempotency_v1' => [
                    'enabled' => $receiverEnabled,
                    'key_max_length' => 128,
                    'key_collation' => 'ascii_bin',
                    'fingerprint' => 'sha256-rfc8785-semantic',
                    'artwork_sha256_required' => true,
                    'conflict_status' => 409,
                    'lease_seconds' => (int) config('incoming_order.lease_seconds', 90),
                    'heartbeat_seconds' => (int) config('incoming_order.heartbeat_seconds', 20),
                    'max_attempts' => (int) config('incoming_order.max_attempts', 10),
                    'fetch_timeout_seconds' => (int) config('incoming_order.fetch.timeout_seconds', 30),
                    'receiver_request_timeout_seconds' => (int) config('incoming_order.request_budget_seconds', 60),
                    'request_max_bytes' => (int) config('incoming_order.request_max_bytes', 131_072),
                    'sender_minimum_timeout_seconds' => 75,
                ],
                'job_label_metadata_v1' => [
                    'enabled' => $labelEnabled,
                    'version' => 1,
                    'supported_modes' => ['metadata_only'],
                    'modes' => $labelEnabled ? ['metadata_only'] : [],
                    'production_artifact' => 'separate_job_card',
                    'artwork_modified' => false,
                    'job_card_quantity' => 1,
                    'production_lease_seconds' => (int) config('incoming_order.job_card.production_lease_seconds', 300),
                    'renderer_version' => (string) config('incoming_order.job_card.renderer_version'),
                    'renderer_font_sha256' => (string) config('incoming_order.job_card.font_sha256'),
                    'renderer_readiness' => $rendererReadiness,
                    'artwork_hosts' => (array) config('incoming_order.allowed_hosts', []),
                    'optional_failure_status' => 'ignored',
                    'dimension_precision_decimals' => 4,
                    'aspect_ratio_max_relative_error' => '0.0010',
                    'limits' => [
                        'download_bytes' => (int) config('incoming_order.fetch.max_bytes', 52_428_800),
                        'decoded_width_px' => (int) config('incoming_order.fetch.max_width_px', 30_000),
                        'decoded_height_px' => (int) config('incoming_order.fetch.max_height_px', 30_000),
                        'decoded_area_px' => (int) config('incoming_order.fetch.max_area_px', 100_000_000),
                        'frames' => 1,
                        'formats' => (array) config('incoming_order.fetch.formats', ['png', 'jpeg', 'webp']),
                        'order_number' => 64,
                        'product_name' => 160,
                        'product_sku' => 80,
                        'color' => 80,
                        'size' => 40,
                        'placement' => 80,
                        'quantity_max' => 10_000,
                        'shop_domain' => 253,
                    ],
                ],
            ],
        ])->header('Cache-Control', 'public, max-age=60');
    }

    private function isV1Request(Request $request, string $rawBody): bool
    {
        $decoded = json_decode($rawBody, true);
        if (is_array($decoded)) {
            return array_key_exists('idempotency_key', $decoded)
                || array_key_exists('job_label', $decoded)
                || (isset($decoded['design'])
                    && is_array($decoded['design'])
                    && array_key_exists('sha256', $decoded['design']));
        }

        if ($request->has('idempotency_key') || $request->has('job_label') || $request->has('design.sha256')) {
            return true;
        }

        return (bool) preg_match('/"(?:idempotency_key|job_label|sha256)"\s*:/', $rawBody);
    }

    private function addHmacCandidate(array &$candidates, string $payload, ?string $secret): void
    {
        if ($payload === '' || $secret === null || $secret === '') {
            return;
        }

        $candidates[] = hash_hmac('sha256', $payload, $secret);
    }

    private function stripSignatureFromRawBody(string $rawBody): string
    {
        if ($rawBody === '') {
            return '';
        }

        $trimmed = ltrim($rawBody);
        if (str_starts_with($trimmed, '{')) {
            // JSON payload variants where signature can appear at start/middle/end.
            $withoutSignature = preg_replace('/,\s*"signature"\s*:\s*"[^"]*"\s*/', '', $rawBody);
            $withoutSignature = preg_replace('/"signature"\s*:\s*"[^"]*"\s*,\s*/', '', (string) $withoutSignature);
            $withoutSignature = preg_replace('/"signature"\s*:\s*"[^"]*"\s*/', '', (string) $withoutSignature);

            return trim((string) $withoutSignature);
        }

        // Form-encoded variants: keep sender ordering by stripping only signature pair from raw string.
        $withoutSignature = preg_replace('/(^|&)signature=[^&]*(&|$)/', '$1', $rawBody);
        $withoutSignature = preg_replace('/&&+/', '&', (string) $withoutSignature);

        return trim((string) $withoutSignature, '&');
    }

    private function storeLegacy(Request $request)
    {
        $rawBody = (string) $request->getContent();
        $decoded = json_decode($rawBody, true);

        // Prefer raw JSON payload when available to keep sender key ordering/typing stable.
        $data = is_array($decoded) ? $decoded : $request->all();

        Log::info('Incoming API Request', [
            'url' => $request->fullUrl(),
            'method' => $request->method(),
            'ip' => $request->ip(),
            'payload' => $data,
        ]);

        $providedSig = (string) ($data['signature'] ?? $request->input('signature', ''));
        unset($data['signature']);

        $sharedSecret = env('BUY_DTF_SECRET');
        $computedCandidates = [];

        // Candidate 1: legacy/default PHP JSON encoding.
        $jsonDefault = json_encode($data);
        if (is_string($jsonDefault)) {
            $this->addHmacCandidate($computedCandidates, $jsonDefault, $sharedSecret);
        }

        // Candidate 2: unescaped slashes/unicode (common in external JSON.stringify senders).
        $jsonUnescaped = json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        if (is_string($jsonUnescaped)) {
            $this->addHmacCandidate($computedCandidates, $jsonUnescaped, $sharedSecret);
        }

        // Candidate 3: form-encoded signing style.
        $queryEncoded = http_build_query($data);
        if (is_string($queryEncoded)) {
            $this->addHmacCandidate($computedCandidates, $queryEncoded, $sharedSecret);
        }

        // Candidate 4: raw request body with signature field removed (keeps sender formatting).
        if ($rawBody !== '') {
            $rawNoSig = $this->stripSignatureFromRawBody($rawBody);
            $this->addHmacCandidate($computedCandidates, $rawNoSig, $sharedSecret);
        }

        $matched = false;
        foreach (array_unique($computedCandidates) as $candidate) {
            if (hash_equals($candidate, $providedSig)) {
                $matched = true;
                break;
            }
        }

        if (! $matched) {
            Log::error('API Signature mismatch', [
                'computed' => $computedCandidates[0] ?? null,
                'computed_candidates' => array_values(array_unique($computedCandidates)),
                'provided' => $providedSig,
                'data' => $data,
            ]);

            return response()->json(['error' => 'Invalid signature'], 401);
        }

        try {
            // --- open/in-progress order
            // The FuelPHP code used find(1), which is hardcoded for a specific business.
            $business = Business::find(1);
            if (! $business) {
                return response()->json(['error' => 'Business not found'], 404);
            }

            $order = $business->open_order();
            if (! $order) {
                $order = new DtfOrder;
                $order->business_id = $business->id;
                $order->status = 1;
                $order->order_date = now();
                $order->save();
            }

            // --- download image
            $fileName = $data['file_name'] ?? '';
            $design = $data['design'] ?? [];
            $url = $design['image_url'] ?? '';

            if (empty($url)) {
                return response()->json(['error' => 'Missing image URL'], 400);
            }

            // Internal path fix: If the URL looks like a local path (starts with /home or /var)
            // and contains 'public_html', try to convert it to a public URL.
            if (Str::startsWith($url, ['/home/', '/var/']) && Str::contains($url, '/public_html/')) {
                Log::info('Attempting to convert local path to URL', ['path' => $url]);

                // Extract domain if possible from /domains/DOMAIN/public_html/
                if (preg_match('/\/domains\/([^\/]+)\/public_html\/(.*)/', $url, $matches)) {
                    $domain = $matches[1];
                    $relativePath = $matches[2];
                    $url = "https://{$domain}/{$relativePath}";
                    Log::info('Converted local path to URL', ['new_url' => $url]);
                } else {
                    // Fallback: just take everything after public_html
                    $parts = explode('/public_html/', $url);
                    $relativePath = end($parts);
                    // We don't have a reliable domain here, but maybe we can guess from the path
                    // or use a hardcoded one if it's always the same shop.
                    // For now, let's try to find a domain in the path even if not in the standard 'domains' folder
                    if (preg_match('/\/([a-z0-9-]+\.(?:com|net|org|store|shop))[\/]/i', $url, $domMatches)) {
                        $url = "https://{$domMatches[1]}/{$relativePath}";
                        Log::info('Converted local path to URL (fallback domain match)', ['new_url' => $url]);
                    }
                }
            }

            Log::info('Fetching image', ['url' => $url]);
            $blob = file_get_contents($url);

            if ($blob === false || $blob === '') {
                return response()->json(['error' => 'Failed to fetch image content', 'url' => $url], 400);
            }

            // --- compute dedupe keys BEFORE writing
            $fileSize = strlen($blob);
            $sha256 = hash('sha256', $blob);

            // --- read pixel dimensions, convert to inches at 300 DPI
            $dims = @getimagesizefromstring($blob);
            if ($dims === false) {
                return response()->json(['error' => 'Invalid image format'], 400);
            }
            $pxW = (int) $dims[0];
            $pxH = (int) $dims[1];

            $DPI = 300;
            $origWidth = $pxW > 0 ? round($pxW / $DPI, 4) : null;
            $origHeight = $pxH > 0 ? round($pxH / $DPI, 4) : null;

            // requested print size from payload (inches)
            $reqW = isset($design['width']) ? (float) $design['width'] : null;
            $reqH = isset($design['height']) ? (float) $design['height'] : null;

            // scale ratios
            $widthRatio = ($reqW && $origWidth > 0) ? round($reqW / $origWidth, 6) : null;
            $heightRatio = ($reqH && $origHeight > 0) ? round($reqH / $origHeight, 6) : null;

            // --- duplicate lookup
            $existing = DtfImage::where('sha256_original', $sha256)
                ->where('file_size', $fileSize)
                ->orderBy('id', 'desc')
                ->first();

            $duplicate = false;
            if ($existing && ! empty($existing->image)) {
                $absExisting = public_path(ltrim($existing->image, '/'));
                if (file_exists($absExisting)) {
                    $relative = ltrim($existing->image, '/');
                    $duplicate = true;
                }
            }

            if (! $duplicate) {
                $relative = 'uploads/images/'.uniqid('DTF_API_'.($data['source_order_id'] ?? 'api').'_').'.png';
                $absPath = public_path($relative);
                $directory = dirname($absPath);

                if (! is_dir($directory)) {
                    @mkdir($directory, 0775, true);
                }

                if (file_put_contents($absPath, $blob) === false) {
                    return response()->json(['error' => 'Failed to store image'], 500);
                }
            }

            // --- persist row
            $dtfImage = new DtfImage;
            $dtfImage->dtforder_id = $order->id;
            $dtfImage->image = '/'.$relative;
            $dtfImage->image_notes = 'Image for Invoice# '.($data['source_order_id'] ?? '');
            $dtfImage->image_name = $data['file_name'] ?? $data['shop'] ?? '';
            $dtfImage->width = $reqW;
            $dtfImage->height = $reqH;
            $dtfImage->quantity = $design['quantity'] ?? 1;
            $dtfImage->date_uploaded = now();
            $dtfImage->production = 0;
            $dtfImage->file_size = $fileSize;
            $dtfImage->sha256_original = $sha256;
            $dtfImage->orig_width = $origWidth;
            $dtfImage->orig_height = $origHeight;
            $dtfImage->width_ratio = $widthRatio;
            $dtfImage->height_ratio = $heightRatio;
            $dtfImage->save();

            Log::info('API Order stored successfully', ['dtfimage_id' => $dtfImage->id]);

            return response()->json([
                'success' => true,
                'duplicate' => $duplicate,
                'file' => '/'.$relative,
                'order_id' => $order->id,
                'dtfimage_id' => $dtfImage->id,
                'job_id' => $data['source_order_id'] ?? null,
                'file_size' => $fileSize,
                'sha256' => $sha256,
                'orig_width_in' => $origWidth,
                'orig_height_in' => $origHeight,
                'width_ratio' => $widthRatio,
                'height_ratio' => $heightRatio,
            ]);
        } catch (\Exception $e) {
            Log::error('API Error', [
                'message' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
            ]);

            return response()->json(['error' => 'Internal Server Error', 'message' => $e->getMessage()], 500);
        }
    }
}
