<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\Template;
use App\Services\NameNumberService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

class CustomNamesController extends Controller
{
    protected NameNumberService $nameNumberService;

    public function __construct(NameNumberService $nameNumberService)
    {
        $this->nameNumberService = $nameNumberService;
    }

    /**
     * Display a listing of templates.
     */
    public function index(Request $request)
    {
        $q = trim((string)$request->input('q', ''));
        $limit = max(10, min(200, (int)$request->input('limit', 50)));

        $query = Template::query()->orderBy('updated_at', 'desc');

        if ($q !== '') {
            $query->where(function($query) use ($q) {
                $query->where('id', 'like', "%{$q}%")
                    ->orWhere('slug', 'like', "%{$q}%")
                    ->orWhere('name', 'like', "%{$q}%");
            });
        }

        $templates = $query->paginate($limit)->withQueryString();

        return view('admin.customnames.index', compact('templates', 'q', 'limit'));
    }

    /**
     * Show the templates page (for JS consumption).
     */
    public function templates()
    {
        return view('admin.customnames.templates');
    }

    /**
     * Show the template builder.
     */
    public function templateBuilder(Request $request)
    {
        $slug = (string)$request->input('slug', '');

        $vars = [
            'ajaxGetUrl' => route('admin.customnames.template.get'),
            'ajaxSaveUrl' => route('admin.customnames.template.save'),
            'ajaxCreateUrl' => route('admin.customnames.template.create'),
            'ajaxDeleteUrl' => route('admin.customnames.template.delete'),
            'ajaxReloadUrl' => route('admin.customnames.templates.reload'),
            'ajaxFontsUrl' => route('admin.customnames.fonts.list'),
            'ajaxPreviewUrl' => route('admin.customnames.preview'),
            'initialSlug' => $slug,
        ];

        return view('admin.customnames.templatebuilder', $vars);
    }

    /**
     * Show the fonts management page.
     */
    public function fonts()
    {
        return view('admin.customnames.fonts');
    }

    /**
     * GET /admin/customnames/template/get?slug=__list__ | ?slug={slug}
     */
    public function getTemplate(Request $request)
    {
        $slug = (string)$request->input('slug', '');
        $id = $request->input('id');

        // LIST
        if ($slug === '__list__') {
            // User requested list of templates. Let's return local templates from DB.
            $templates = Template::orderBy('updated_at', 'desc')->get();
            $rows = [];
            foreach ($templates as $t) {
                $rows[] = [
                    'id' => $t->id,
                    'slug' => $t->slug,
                    'title' => $t->public_name ?: $t->name ?: $t->slug,
                    'updated' => $t->updated_at ? $t->updated_at->toDateTimeString() : null,
                    'updatedAt' => $t->updated_at ? $t->updated_at->toDateTimeString() : null,
                    'width' => $t->json_config['widthIn'] ?? null,
                    'height' => $t->json_config['heightIn'] ?? null,
                    'widthIn' => $t->json_config['widthIn'] ?? null,
                    'heightIn' => $t->json_config['heightIn'] ?? null,
                    'dpi' => $t->json_config['dpi'] ?? null,
                ];
            }

            return response()->json([
                'success' => true,
                'message' => 'OK',
                'templates' => $rows,
                'items' => $rows,
                'list' => $rows,
                'rows' => $rows,
                'count' => count($rows),
                'data' => ['templates' => $rows, 'count' => count($rows)],
            ]);
        }

        // SINGLE
        if ($id) {
            $template = Template::find($id);
        } else {
            if ($slug === '') return response()->json(['success' => false, 'message' => 'Missing slug or id'], 400);
            $template = Template::where('slug', $slug)->first();
        }

        if (!$template) {
            return response()->json(['success' => false, 'message' => 'Template not found in local database'], 404);
        }

        $tpl = $template->json_config;
        if (!is_array($tpl)) {
            $tpl = json_decode($tpl, true) ?: [];
        }

        // Ensure key fields exist
        $tpl['id'] = $template->id;
        $tpl['slug'] = $template->slug;
        $tpl['name'] = $template->name;
        $tpl['updated_at'] = $template->updated_at ? $template->updated_at->toDateTimeString() : null;

        return response()->json([
            'success' => true,
            'message' => 'OK',
            'template' => $tpl,
            'data' => ['template' => $tpl]
        ]);
    }

    /**
     * POST /admin/customnames/template/create
     */
    public function createTemplate(Request $request)
    {
        $slug = (string)$request->input('slug', '');
        $tpl = $request->input('template');

        if ($slug === '') {
            $raw = $request->json()->all();
            if (isset($raw['slug'])) $slug = (string)$raw['slug'];
            if ($tpl === null && isset($raw['template'])) $tpl = $raw['template'];
        }

        if ($slug === '') return response()->json(['success' => false, 'message' => 'Missing slug'], 400);

        if (is_string($tpl)) {
            $tpl = json_decode($tpl, true);
        }

        if (!is_array($tpl)) {
            return response()->json(['success' => false, 'message' => 'Missing or invalid template payload'], 400);
        }

        // Save to local database
        $template = Template::updateOrCreate(
            ['slug' => $slug],
            [
                'name' => $tpl['name'] ?? $slug,
                'json_config' => $tpl,
                'active' => true
            ]
        );

        return response()->json(['success' => true, 'message' => 'Created/Updated locally', 'slug' => $slug, 'id' => $template->id]);
    }

    /**
     * POST /admin/customnames/template/save
     */
    public function saveTemplate(Request $request)
    {
        $id = $request->input('id');
        $slug = (string)$request->input('slug', '');
        $tpl = $request->input('template');

        if ($slug === '' || $tpl === null) {
            $raw = $request->json()->all();
            if ($id === null && isset($raw['id'])) $id = $raw['id'];
            if ($slug === '' && isset($raw['slug'])) $slug = (string)$raw['slug'];
            if ($tpl === null && isset($raw['template'])) $tpl = $raw['template'];
        }

        if ($id) {
            $template = Template::find($id);
        } else {
            if ($slug === '') return response()->json(['success' => false, 'message' => 'Missing slug or id'], 400);
            $template = Template::where('slug', $slug)->first();
        }

        if (!$template) {
            return response()->json(['success' => false, 'message' => 'Template not found'], 404);
        }

        if (is_string($tpl)) {
            $tpl = json_decode($tpl, true);
        }

        if (!is_array($tpl)) {
            return response()->json(['success' => false, 'message' => 'Missing or invalid template payload'], 400);
        }

        // Update local database
        $template->json_config = $tpl;
        if (isset($tpl['name'])) $template->name = $tpl['name'];
        if (isset($tpl['slug'])) $template->slug = $tpl['slug'];
        $template->save();

        return response()->json(['success' => true, 'message' => 'Saved locally', 'slug' => $template->slug, 'id' => $template->id]);
    }

    /**
     * POST /admin/customnames/template/delete
     */
    public function deleteTemplate(Request $request)
    {
        $id = $request->input('id');
        $slug = (string)$request->input('slug', '');

        if ($id === null && $slug === '') {
            $raw = $request->json()->all();
            if (isset($raw['id'])) $id = $raw['id'];
            if (isset($raw['slug'])) $slug = $raw['slug'];
        }

        if ($id) {
            $template = Template::find($id);
        } else {
            if ($slug === '') return response()->json(['success' => false, 'message' => 'Missing slug or id'], 400);
            $template = Template::where('slug', $slug)->first();
        }

        if (!$template) {
            return response()->json(['success' => false, 'message' => 'Template not found'], 404);
        }

        $template->delete();

        return response()->json(['success' => true, 'message' => 'Deleted locally']);
    }

    /**
     * POST /admin/customnames/templates/reload
     */
    public function reloadTemplates()
    {
        $res = $this->nameNumberService->nodeAction('post', '/templates/reload');
        if (!($res['success'] ?? false)) {
            return response()->json(['success' => false, 'message' => $res['message'] ?? 'Reload failed'], 400);
        }
        return response()->json(['success' => true, 'message' => 'Reloaded']);
    }

    /**
     * POST /admin/customnames/preview
     */
    public function preview(Request $request)
    {
        $payload = $request->all();
        $slug = (string)($payload['slug'] ?? '');
        $templateInline = $payload['template_inline'] ?? null;
        $name = (string)($payload['name'] ?? 'HERNANDEZ');
        $number = (string)($payload['number'] ?? '72');
        $format = (string)($payload['format'] ?? 'png');

        // Path A: From database ID (used by index.blade.php)
        if (isset($payload['id']) && is_numeric($payload['id'])) {
            $template = Template::find($payload['id']);
            if ($template) {
                $templateInline = $template->json_config;
            }
        }

        if (is_array($templateInline) && !empty($templateInline)) {
            $res = $this->nameNumberService->renderTemplateRemote(null, $name, $number, [], [], [
                'template_inline' => $templateInline,
                'format' => $format,
                'dpi' => (int)($payload['dpi'] ?? $templateInline['dpi'] ?? 300),
                'preserveCase' => (bool)($payload['preserveCase'] ?? true),
                'data' => $payload['data'] ?? [],
            ]);

            if (!($res['success'] ?? false)) {
                return response()->json(['success' => false, 'message' => $res['message'] ?? 'Preview failed'], 400);
            }

            return response()->json(['success' => true, 'message' => 'OK', 'url' => $res['url'] ?? null]);
        }

        if ($slug === '') return response()->json(['success' => false, 'message' => 'Missing slug'], 400);

        $res = $this->nameNumberService->renderTemplateRemote($slug, $name, $number, [], [], ['format' => $format]);

        if (!($res['success'] ?? false)) {
            return response()->json(['success' => false, 'message' => $res['message'] ?? 'Preview failed'], 400);
        }

        return response()->json(['success' => true, 'message' => 'OK', 'url' => $res['url'] ?? null]);
    }

    /**
     * GET /admin/customnames/fonts/list
     */
    public function listFonts()
    {
        $res = $this->nameNumberService->listFonts();
        if (!($res['success'] ?? false)) return response()->json(['success' => false, 'message' => $res['message'] ?? 'Failed to list fonts'], 400);
        return response()->json(['success' => true, 'message' => 'OK', 'fonts' => $res['fonts'] ?? $res]);
    }

    /**
     * POST /admin/customnames/fonts/reload
     */
    public function reloadFonts()
    {
        $res = $this->nameNumberService->nodeAction('post', '/font/reload');
        if (!($res['success'] ?? false)) return response()->json(['success' => false, 'message' => $res['message'] ?? 'Reload failed'], 400);
        return response()->json(['success' => true, 'message' => 'Reloaded']);
    }

    /**
     * POST /admin/customnames/fonts/upload
     */
    public function uploadFont(Request $request)
    {
        if (!$request->hasFile('font')) {
            return response()->json(['success' => false, 'message' => 'No file uploaded'], 400);
        }

        $file = $request->file('font');
        $path = $file->store('tmp/uploads');
        $fullPath = storage_path('app/' . $path);

        $res = $this->nameNumberService->uploadFont($fullPath);
        @unlink($fullPath);

        if (!($res['success'] ?? false)) {
            return response()->json(['success' => false, 'message' => $res['message'] ?? 'Node upload failed'], 400);
        }

        return response()->json(['success' => true, 'message' => 'Uploaded', 'data' => $res]);
    }

    /**
     * GET /admin/customnames/fontsmap
     */
    public function fontsMap()
    {
        $vars = [
            'ajaxFontsUrl' => route('admin.customnames.fonts.list'),
            'ajaxGetMapUrl' => route('admin.customnames.fontsmap.get'),
            'ajaxSaveMapUrl' => route('admin.customnames.fontsmap.save'),
            'ajaxSetUrl' => route('admin.customnames.fonts.set'),
            'ajaxReloadUrl' => route('admin.customnames.fonts.reload'),
        ];

        return view('admin.customnames.fontsmap', $vars);
    }

    /**
     * GET /admin/customnames/fontsmap/get
     */
    public function getFontsMap()
    {
        $res = $this->nameNumberService->nodeAction('get', '/fonts/map');
        if (!($res['success'] ?? false)) return response()->json(['success' => false, 'message' => $res['message'] ?? 'Failed'], 400);
        return response()->json(['success' => true, 'message' => 'OK', 'map' => $res['map'] ?? $res]);
    }

    /**
     * POST /admin/customnames/fontsmap/save
     */
    public function saveFontsMap(Request $request)
    {
        $map = $request->input('map');
        if (is_string($map)) {
            $map = json_decode($map, true);
        }

        if (!is_array($map)) {
            return response()->json(['success' => false, 'message' => 'Invalid map data'], 400);
        }

        $res = $this->nameNumberService->nodeAction('post', '/fonts/map', ['map' => $map]);
        if (!($res['success'] ?? false)) return response()->json(['success' => false, 'message' => $res['message'] ?? 'Save failed'], 400);

        return response()->json(['success' => true, 'message' => 'Saved']);
    }

    /**
     * POST /admin/customnames/fonts/set
     */
    public function setFont(Request $request)
    {
        $payload = $request->all();
        $slug = (string)($payload['slug'] ?? '');
        $family = (string)($payload['family'] ?? '');

        if ($slug === '' || $family === '') {
            return response()->json(['success' => false, 'message' => 'Missing slug or family'], 400);
        }

        $data = [
            'slug' => $slug,
            'family' => $family,
        ];
        if (isset($payload['pxPerInch'])) $data['pxPerInch'] = (int)$payload['pxPerInch'];
        if (isset($payload['trackingMinPx'])) $data['trackingMinPx'] = (float)$payload['trackingMinPx'];

        $res = $this->nameNumberService->nodeAction('post', '/fonts/set-family', $data);
        if (!($res['success'] ?? false)) return response()->json(['success' => false, 'message' => $res['message'] ?? 'Failed'], 400);

        return response()->json(['success' => true, 'message' => 'Updated']);
    }
}
