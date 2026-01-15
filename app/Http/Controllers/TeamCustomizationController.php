<?php

namespace App\Http\Controllers;

use App\Helpers\ImageHelper;
use App\Models\BatchProgress;
use App\Models\Business;
use App\Models\CustomColor;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\StockFont;
use App\Models\Template;
use App\Services\NameNumberService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Log;

class TeamCustomizationController extends Controller
{
    protected NameNumberService $nameNumberService;

    public function __construct(NameNumberService $nameNumberService)
    {
        $this->nameNumberService = $nameNumberService;
    }

    public function index()
    {
        $templates = Template::where('active', true)->orderBy('sort_order', 'asc')->get();
        return view('team-customization.index', compact('templates'));
    }

    public function getFonts()
    {
        $res = $this->nameNumberService->listFonts();
        $fonts = [];

        if (isset($res['success']) && $res['success'] === false) {
            Log::warning('TeamCustomization: Node font service failed, using local fallback: ' . ($res['message'] ?? 'Unknown error'));

            $localFonts = StockFont::where('active', true)->orderBy('sort_order', 'asc')->orderBy('name', 'asc')->get();
            $fonts = $localFonts->map(function($f) {
                return [
                    'id' => $f->name, // Service uses name as ID usually
                    'name' => $f->name
                ];
            });
        } else {
            // Service returns {success: true, fonts: [{slug, family, ...}]}
            // index.js expects [{id, name}]
            $list = $res['fonts'] ?? $res;
            if (is_array($list)) {
                foreach ($list as $f) {
                    $fonts[] = [
                        'id' => $f['slug'] ?? $f['id'] ?? null,
                        'name' => $f['family'] ?? $f['name'] ?? null
                    ];
                }
            }
        }

        return response()->json($fonts);
    }

    public function preview(Request $request)
    {
        $payload = $request->all();
        $optsIn = $payload['opts'] ?? [];

        $opts = [
            'template_inline' => $optsIn['template_inline'] ?? $payload['template_inline'] ?? $payload['template'] ?? null,
            'dpi' => (int)($optsIn['dpi'] ?? 72),
            'format' => (string)($optsIn['format'] ?? 'svg'),
            'preserveCase' => (bool)($optsIn['preserveCase'] ?? true),
            'allowEmptyTopLevel' => true,
            'data' => $optsIn['data'] ?? $payload['data'] ?? [],
        ];

        $res = $this->nameNumberService->renderTemplateRemote(null, '', '', [], [], $opts);

        if ($res['success'] ?? false) {
            return response()->json($res);
        }

        return response()->json($res, 500);
    }

    public function validateCsv(Request $request)
    {
        if (!$request->hasFile('file')) {
            return response()->json(['success' => false, 'message' => 'No file uploaded'], 400);
        }

        $file = $request->file('file');
        $content = file_get_contents($file->getRealPath());

        // Basic CSV parsing logic
        $lines = explode("\n", str_replace("\r", "", $content));
        $header = str_getcsv(array_shift($lines));
        $rows = [];
        foreach ($lines as $line) {
            if (trim($line)) {
                $rows[] = str_getcsv($line);
            }
        }

        return response()->json([
            'success' => true,
            'headers' => $header,
            'row_count' => count($rows),
            'rows' => $rows,
        ]);
    }

    public function runOne(Request $request)
    {
        $payload = $request->all();
        $optsIn = $payload['opts'] ?? [];

        $inline = $optsIn['template_inline'] ?? $payload['template_inline'] ?? $payload['template'] ?? null;

        if (!$inline) {
            return response()->json(['success' => false, 'message' => 'Missing template'], 400);
        }

        $opts = [
            'template_inline' => $inline,
            'dpi' => (int)($optsIn['dpi'] ?? 300),
            'format' => 'png',
            'preserveCase' => (bool)($optsIn['preserveCase'] ?? true),
            'allowEmptyTopLevel' => true,
            'data' => $optsIn['data'] ?? $payload['data'] ?? [],
        ];

        try {
            $res = $this->nameNumberService->renderTemplateRemote(null, '', '', [], [], $opts);

            if (!($res['success'] ?? false)) {
                return response()->json($res, 500);
            }

            // Attach to order
            $attach = $this->attachToOrder($res, $payload);

            return response()->json([
                'success' => true,
                'image' => $res,
                'attached' => $attach['success'],
                'attach' => $attach,
            ]);

        } catch (\Exception $e) {
            return response()->json(['success' => false, 'message' => $e->getMessage()], 500);
        }
    }

    protected function attachToOrder(array $fileInfo, array $payload): array
    {
        try {
            $user = Auth::user();
            if (!$user || !$user->business) {
                return ['success' => false, 'message' => 'User or business not found'];
            }

            $business = $user->business;
            $order = $business->open_order();
            if (!$order) {
                $order = DtfOrder::create([
                    'business_id' => $business->id,
                    'status' => 1,
                    'order_date' => now(),
                ]);
            }

            $absPath = $fileInfo['full_path'] ?? null;
            $url = $fileInfo['url'] ?? null;
            $path = $fileInfo['path'] ?? null;

            if (!$absPath || !$path) {
                return ['success' => false, 'message' => 'File info incomplete'];
            }

            // Post-process image
            ImageHelper::trimTransparentBorder($absPath);
            ImageHelper::setPngDpi($absPath, 300, 300);
            ImageHelper::thresholdAlphaMask($absPath);

            // Re-read dimensions
            $widthInches = 0;
            $heightInches = 0;
            if (extension_loaded('imagick')) {
                $im = new \Imagick($absPath);
                $widthInches = round($im->getImageWidth() / 300, 3);
                $heightInches = round($im->getImageHeight() / 300, 3);
                $im->clear();
                $im->destroy();
            }

            $data = $payload['data'] ?? ($payload['opts']['data'] ?? []);
            $qty = (int)($payload['__order_quantity'] ?? $payload['opts']['order_quantity'] ?? $data['quantity'] ?? 1);
            $qty = max(1, $qty);

            $dtfImage = DtfImage::create([
                'dtforder_id' => $order->id,
                'image' => $url, // Use the full URL starting with /uploads/images/
                'image_notes' => 'Team Customization Batch Loader',
                'image_name' => 'Team Customization',
                'width' => $widthInches,
                'height' => $heightInches,
                'quantity' => $qty,
                'date_uploaded' => now(),
                'production' => 0,
            ]);

            return ['success' => true, 'id' => $dtfImage->id];

        } catch (\Exception $e) {
            Log::error('AttachToOrder failed: ' . $e->getMessage());
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }

    public function getProgress(Request $request)
    {
        $batch = $request->query('batch', '');
        $row = (int)$request->query('row', 0);

        $progress = BatchProgress::where('batch_id', $batch)->where('row_index', $row)->first();

        return response()->json($progress);
    }

    public function getTemplates()
    {
        $templates = Template::where('active', true)->get(['id', 'name', 'public_name']);

        $list = $templates->map(function($t) {
            return [
                'id' => $t->id,
                'title' => $t->public_name ?: $t->name
            ];
        });

        return response()->json(['success' => true, 'templates' => $list]);
    }

    public function getTemplate(Request $request, $id = null)
    {
        $id = $id ?: $request->query('id');
        if (!$id) {
            return response()->json(['success' => false, 'message' => 'No template ID provided'], 400);
        }

        $template = Template::find($id);
        if (!$template) {
            return response()->json(['success' => false, 'message' => 'Template not found'], 404);
        }

        // Return the JSON config which contains blocks etc.
        $config = $template->json_config;
        if (!is_array($config)) {
            $config = json_decode($config, true) ?: [];
        }

        // Add ID and Name to the config if not present
        $config['id'] = $template->id;
        $config['name'] = $template->name;

        return response()->json([
            'success' => true,
            'template' => $config
        ]);
    }

    public function getColors()
    {
        $user = Auth::user();
        if (!$user || !$user->business) {
            return response()->json(['success' => false, 'colors' => []]);
        }

        $businessId = $user->business->id;

        $colors = CustomColor::where('active', true)
            ->where(function($query) use ($businessId) {
                $query->where('business_id', $businessId)
                    ->orWhere('business_id', 0);
            })
            ->orderBy('business_id', 'asc') // global first or last? index.js just iterates.
            ->orderBy('name', 'asc')
            ->get();

        return response()->json(['success' => true, 'colors' => $colors]);
    }
}
