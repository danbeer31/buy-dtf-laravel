<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\StripeSyncLog;
use Illuminate\Http\Request;

class StripeSyncLogController extends Controller
{
    public function index(Request $request)
    {
        $query = StripeSyncLog::orderBy('created_at', 'desc');

        if ($request->filled('type')) {
            $query->where('sync_type', $request->type);
        }

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        $logs = $query->paginate(30);

        return view('admin.payments.stripe_sync_logs', compact('logs'));
    }

    public function show(StripeSyncLog $log)
    {
        return view('admin.payments.stripe_sync_log_show', compact('log'));
    }
}
