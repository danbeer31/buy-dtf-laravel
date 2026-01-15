<?php

namespace App\Services;

use App\Helpers\ImageHelper;
use App\Models\BatchProgress;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\Template;
use Illuminate\Support\Facades\Config;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

class NameNumberService
{
    protected string $baseUrl;
    protected string $token;

    public function __construct()
    {
        $this->baseUrl = rtrim((string)config('services.namenumber.url', 'http://127.0.0.1:3000'), '/');
        $this->token = (string)config('services.namenumber.token', '');
    }

    /**
     * Render a template via the Node.js service.
     */
    public function renderTemplateRemote(
        ?string $templateSlug,
        string  $name,
        string  $number,
        array   $nameStyle = [],
        array   $numberStyle = [],
        array   $opts = []
    ): array {
        $url = $this->baseUrl . '/render-name-number';

        $preserveCase = (bool)($opts['preserveCase'] ?? false);
        $allowEmptyTop = (bool)($opts['allowEmptyTopLevel'] ?? false);

        $safeNameInput = $preserveCase ? (string)$name : strtoupper((string)$name);
        $safeNameSan = trim(preg_replace('/[^A-Za-z0-9 \-]/', '', $safeNameInput));
        $safeNumberSan = trim(preg_replace('/[^0-9]/', '', (string)$number));

        $safeName = $allowEmptyTop ? $safeNameSan : ($safeNameSan !== '' ? $safeNameSan : 'NAME');
        $safeNumber = $allowEmptyTop ? $safeNumberSan : ($safeNumberSan !== '' ? $safeNumberSan : '00');

        $payload = [
            'name' => $safeName,
            'number' => $safeNumber,
            'dpi' => (int)($opts['dpi'] ?? 300),
            'preserveCase' => $preserveCase,
            'nameStyle' => $this->normalizeStyle($nameStyle),
            'numberStyle' => $this->normalizeStyle($numberStyle),
        ];

        if (!empty($templateSlug)) {
            $payload['template'] = $templateSlug;
        }

        // Inline template (private, per request)
        if (!empty($opts['template_inline'])) {
            $tplInline = is_string($opts['template_inline'])
                ? json_decode($opts['template_inline'], true)
                : $opts['template_inline'];
            if (is_array($tplInline)) {
                $payload['template_inline'] = $this->normalizeInlineTemplate($tplInline);
                unset($payload['template']);
            }
        }

        // Pass-through options
        foreach (['gapAdjustPx', 'format', 'embedFonts', 'alphaThreshold', 'trackingMinPx', 'squeezeToFit', 'squeezeMode'] as $opt) {
            if (isset($opts[$opt])) {
                $payload[$opt] = $opts[$opt];
            }
        }

        if (isset($opts['scaling'])) {
            $payload['scaling'] = $opts['scaling'];
        }

        // Pass-through data (maps placeholders to values)
        if (isset($opts['data']) && is_array($opts['data'])) {
            $payload['data'] = $opts['data'];
        }

        try {
            // Log::info('NameNumberService rendering payload', [
            //     'url' => $url,
            //     'payload' => $payload
            // ]);
            $response = Http::withHeaders(['X-Api-Token' => $this->token])
                ->timeout(60)
                ->post($url, $payload);

            if (!$response->successful()) {
                return ['success' => false, 'message' => 'Renderer error: ' . $response->body()];
            }

            $body = $response->body();
            $contentType = $response->header('Content-Type');

            if (str_starts_with($body, "\x89PNG\r\n\x1A\n")) {
                return $this->savePngAndFinalize($body, $safeName, $safeNumber);
            }

            if (str_contains($contentType, 'image/svg') || str_contains($body, '<svg') || str_starts_with(ltrim($body), '<?xml')) {
                return ['success' => true, 'format' => 'svg', 'data' => $body];
            }

            return $response->json() ?? ['success' => false, 'message' => 'Unexpected response from renderer'];

        } catch (\Exception $e) {
            Log::error('NameNumberService error: ' . $e->getMessage());
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    public function listFonts(): array
    {
        return $this->getJson('/fonts');
    }

    public function listTemplates(): array
    {
        return $this->getJson('/templates/');
    }

    public function getTemplate(string $slug): array
    {
        return $this->getJson('/templates/' . rawurlencode($slug));
    }

    /**
     * Generic Node action (POST, PUT, DELETE)
     */
    public function nodeAction(string $method, string $endpoint, array $payload = []): array
    {
        try {
            $method = strtolower($method);
            $response = Http::withHeaders(['X-Api-Token' => $this->token])
                ->timeout(60)
                ->{$method}($this->baseUrl . $endpoint, $payload);

            if (!$response->successful()) {
                return ['success' => false, 'message' => 'Node service error: ' . $response->status() . ' ' . $response->body()];
            }

            return $response->json() ?? ['success' => true];
        } catch (\Exception $e) {
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    /**
     * Upload a font to the Node service
     */
    public function uploadFont(string $fullPath): array
    {
        try {
            $response = Http::withHeaders(['X-Api-Token' => $this->token])
                ->attach('font', file_get_contents($fullPath), basename($fullPath))
                ->post($this->baseUrl . '/fonts/upload');

            if (!$response->successful()) {
                return ['success' => false, 'message' => 'Node service error: ' . $response->status() . ' ' . $response->body()];
            }

            return $response->json();
        } catch (\Exception $e) {
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    protected function getJson(string $endpoint): array
    {
        try {
            $response = Http::withHeaders(['X-Api-Token' => $this->token])
                ->get($this->baseUrl . $endpoint);

            if (!$response->successful()) {
                return ['success' => false, 'message' => 'Node service error'];
            }

            return $response->json();
        } catch (\Exception $e) {
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    protected function normalizeStyle(array $s): array
    {
        // Ported from Helpers_NameNumber::normalize_style
        $out = [
            'fontFamily' => $s['fontFamily'] ?? 'Impact',
            'fill' => $s['fill'] ?? '#ffffff',
            'stroke' => $s['stroke'] ?? '#000000',
            'strokeWidth' => (float)($s['strokeWidth'] ?? 0),
            'fontSize' => (float)($s['fontSize'] ?? 60),
        ];

        if (!empty($s['font'])) {
            $out['font'] = (string)$s['font'];
        }

        if (isset($s['letterSpacing'])) {
            $out['letterSpacing'] = (float)$s['letterSpacing'];
        }

        // outline2
        if (!empty($s['outline2']) && is_array($s['outline2'])) {
            $o = $s['outline2'];
            $o2 = [];
            if (isset($o['color'])) $o2['color'] = $o['color'];
            if (isset($o['widthPx'])) $o2['widthPx'] = max(0, (int)$o['widthPx']);
            if (!empty($o['font'])) $o2['font'] = (string)$o['font'];
            if ($o2) $out['outline2'] = $o2;
        }

        // separatedOutline (ring)
        if (!empty($s['separatedOutline']) && is_array($s['separatedOutline'])) {
            $sep = $s['separatedOutline'];
            $se = [];
            if (isset($sep['outerColor'])) $se['outerColor'] = $sep['outerColor'];
            if (isset($sep['outerWidthPx'])) $se['outerWidthPx'] = max(0, (int)$sep['outerWidthPx']);
            if (isset($sep['gapPx'])) $se['gapPx'] = max(0, (int)$sep['gapPx']);
            if ($se) $out['separatedOutline'] = $se;
        }

        return $out;
    }

    protected function normalizeInlineTemplate(array $tpl): array
    {
        $out = [
            'widthIn' => (float)($tpl['widthIn'] ?? 0),
            'heightIn' => (float)($tpl['heightIn'] ?? 0),
            'dpi' => (int)($tpl['dpi'] ?? 300),
            'defaults' => (array)($tpl['defaults'] ?? []),
            'blocks' => [],
        ];

        $blocks = is_array($tpl['blocks'] ?? null) ? $tpl['blocks'] : [];

        foreach ($blocks as $b) {
            $type = strtolower((string)($b['type'] ?? 'text'));
            if ($type === 'straight') $type = 'text';

            $blk = [
                'type' => $type,
                'slot' => (string)($b['slot'] ?? ''),
                'align' => (string)($b['align'] ?? 'center'),
                'x' => (float)($b['x'] ?? 0),
                'y' => (float)($b['y'] ?? 0),
            ];

            if (isset($b['widthPx'])) $blk['widthPx'] = (float)$b['widthPx'];
            if (isset($b['heightPx'])) $blk['heightPx'] = (float)$b['heightPx'];
            if (isset($b['fontSizePx'])) $blk['fontSizePx'] = (float)$b['fontSizePx'];
            if (isset($b['rotationDeg'])) $blk['rotationDeg'] = (float)$b['rotationDeg'];
            if (isset($b['letterSpacing'])) $blk['letterSpacing'] = (float)$b['letterSpacing'];

            // Styles
            foreach (['fill', 'stroke', 'strokeWidth', 'font'] as $key) {
                if (isset($b[$key])) $blk[$key] = $b[$key];
            }

            // Complex styles
            if (isset($b['outline2'])) $blk['outline2'] = $b['outline2'];
            if (isset($b['separatedOutline'])) $blk['separatedOutline'] = $b['separatedOutline'];

            // Arc specific
            if ($type === 'arc') {
                $blk['cx'] = (float)($b['cx'] ?? 0);
                $blk['cy'] = (float)($b['cy'] ?? 0);
                $blk['radiusPx'] = (float)($b['radiusPx'] ?? 0);
                $blk['startAngleDeg'] = (float)($b['startAngleDeg'] ?? 0);
                $blk['endAngleDeg'] = (float)($b['endAngleDeg'] ?? 0);
            }

            // SVG specific
            if ($type === 'svg') {
                if (isset($b['href'])) $blk['href'] = $b['href'];
                if (isset($b['svgMarkup'])) $blk['svgMarkup'] = $b['svgMarkup'];
            }

            $out['blocks'][] = $blk;
        }

        return $out;
    }

    protected function savePngAndFinalize(string $pngData, string $safeName, string $safeNumber): array
    {
        $dirName = 'uploads/images';
        $publicPath = public_path($dirName);

        if (!file_exists($publicPath)) {
            @mkdir($publicPath, 0775, true);
        }

        if (!is_writable($publicPath)) {
            Log::error("NameNumberService: Directory {$publicPath} is not writable.");
        }

        $filename = 'TEAM_CUSTOM_' . strtoupper(Str::random(10)) . '.png';
        $fullPath = $publicPath . '/' . $filename;

        file_put_contents($fullPath, $pngData);

        // Basic clean up if needed (DPI, etc)
        ImageHelper::setPngDpi($fullPath, 300, 300);

        return [
            'success' => true,
            'format' => 'png',
            'path' => $dirName . '/' . $filename,
            'url' => '/' . $dirName . '/' . $filename,
            'full_path' => $fullPath
        ];
    }
}
