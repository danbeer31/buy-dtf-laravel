<?php

namespace App\Http\Controllers\Admin;

use App\Http\Controllers\Controller;
use App\Models\DropboxToken;
use App\Services\DropboxService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;

class DropboxController extends Controller
{
    protected $dropbox;

    public function __construct(DropboxService $dropbox)
    {
        $this->dropbox = $dropbox;
    }

    public function status()
    {
        $record = DropboxToken::first();
        $status = [];

        if (!$record || empty($record->access_token)) {
            $status['connected'] = false;
            $status['message'] = "No Dropbox tokens found. Please connect.";
        } else {
            // Check expiration
            $expiresIn = $record->expires_in - time();
            $connected = $expiresIn > 0;
            $status['connected'] = $connected;
            $status['message'] = $connected ? "Connected to Dropbox." : "Token may be expired. Try refreshing.";
            $status['access_token_expires_in'] = $expiresIn;
            $status['refresh_token'] = $record->refresh_token;
            $status['updated_at'] = $record->updated_at;
        }

        return view('admin.dropbox.status', compact('status'));
    }

    public function connect()
    {
        $state = bin2hex(random_bytes(16));
        session(['dropbox_oauth_state' => $state]);

        $authUrl = $this->dropbox->getAuthUrl($state);
        return redirect($authUrl);
    }

    public function callback(Request $request)
    {
        $code = $request->get('code');
        $state = $request->get('state');
        $storedState = session('dropbox_oauth_state');

        if (!$code || !$state || $state !== $storedState) {
            return redirect()->route('admin.dropbox.status')->with('error', 'Missing or invalid code/state.');
        }

        try {
            $this->dropbox->exchangeCodeForToken($code);
            return redirect()->route('admin.dropbox.status')->with('success', 'Dropbox connected successfully.');
        } catch (\Exception $e) {
            Log::error('Dropbox OAuth Error: ' . $e->getMessage());
            return redirect()->route('admin.dropbox.status')->with('error', 'Failed to connect to Dropbox: ' . $e->getMessage());
        }
    }

    public function refresh()
    {
        $record = DropboxToken::first();
        if (!$record || empty($record->refresh_token)) {
            return redirect()->route('admin.dropbox.status')->with('error', 'No refresh token available.');
        }

        try {
            $this->dropbox->refreshTokens($record);
            return redirect()->route('admin.dropbox.status')->with('success', 'Dropbox tokens refreshed successfully.');
        } catch (\Exception $e) {
            Log::error('Dropbox Refresh Token Error: ' . $e->getMessage());
            return redirect()->route('admin.dropbox.status')->with('error', 'Failed to refresh Dropbox tokens: ' . $e->getMessage());
        }
    }
}
