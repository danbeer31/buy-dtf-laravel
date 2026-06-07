<?php

namespace App\Services;

use App\Models\DropboxToken;
use Spatie\Dropbox\Client;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class DropboxService
{
    protected $clientId;
    protected $clientSecret;
    protected $tokenUrl;
    protected $authorizeUrl;
    protected $redirectUri;

    public function __construct()
    {
        $this->clientId = config('services.dropbox.client_id');
        $this->clientSecret = config('services.dropbox.client_secret');
        $this->tokenUrl = config('services.dropbox.token_url');
        $this->authorizeUrl = config('services.dropbox.authorize_url');
        $this->redirectUri = config('services.dropbox.redirect_uri');
    }

    public function getAuthUrl($state)
    {
        $params = [
            'client_id' => $this->clientId,
            'redirect_uri' => $this->redirectUri,
            'response_type' => 'code',
            'state' => $state,
            'token_access_type' => 'offline',
            'scope' => 'files.metadata.read files.metadata.write files.content.read files.content.write'
        ];

        return $this->authorizeUrl . '?' . http_build_query($params);
    }

    public function exchangeCodeForToken($code)
    {
        $response = Http::asForm()
            ->post($this->tokenUrl, [
                'code' => $code,
                'grant_type' => 'authorization_code',
                'client_id' => $this->clientId,
                'client_secret' => $this->clientSecret,
                'redirect_uri' => $this->redirectUri
            ]);

        if ($response->failed()) {
            throw new \Exception('Dropbox OAuth Error: ' . ($response->json()['error_description'] ?? $response->body()));
        }

        $data = $response->json();

        DropboxToken::updateOrCreate([], [
            'access_token' => $data['access_token'],
            'token_type' => $data['token_type'] ?? 'bearer',
            'uid' => $data['uid'] ?? null,
            'account_id' => $data['account_id'] ?? null,
            'scope' => $data['scope'] ?? null,
            'expires_in' => isset($data['expires_in']) ? (int)$data['expires_in'] + time() : 0,
            'refresh_token' => $data['refresh_token'] ?? null,
            'updated_at' => now(),
        ]);

        return $data;
    }

    public function getClient($token = null)
    {
        if ($token) {
            Log::debug("Dropbox getClient: Using provided token override (prefix: " . substr($token, 0, 10) . ")");
            error_log("Dropbox getClient: Using provided token override");
            return new Client($token);
        }

        $tokenRecord = DropboxToken::orderBy('id', 'desc')->first();

        if (!$tokenRecord) {
            Log::error('Dropbox getClient failed: No token record in database');
            throw new \Exception('No Dropbox connection found. Please connect in Admin -> Dropbox.');
        }

        if (empty($tokenRecord->refresh_token)) {
            Log::error('Dropbox getClient failed: No refresh token in database');
            throw new \Exception('No valid Dropbox refresh token found. Please connect first.');
        }

        if ($this->isExpired($tokenRecord)) {
            Log::info('Dropbox token expired or near expiry, refreshing before getClient', [
                'expires_in' => $tokenRecord->expires_in,
                'time' => time(),
                'diff' => $tokenRecord->expires_in - time()
            ]);
            try {
                $tokenRecord = $this->refreshTokens($tokenRecord);
            } catch (\Exception $e) {
                Log::error('Dropbox proactive refresh failed: ' . $e->getMessage());
                // We will still try to use the current access token, it might work if the clock is slightly off
            }
        }

        Log::debug("Dropbox getClient: Using database token (prefix: " . substr($tokenRecord->access_token, 0, 10) . ")");
        return new Client($tokenRecord->access_token);
    }

    public function upload($localFilePath, $dropboxPath)
    {
        $logFile = storage_path('logs/dropbox_debug.log');
        $timestamp = date('Y-m-d H:i:s');

        Log::info("Dropbox upload started for: $dropboxPath");
        error_log("Dropbox upload started for: $dropboxPath");
        file_put_contents($logFile, "[$timestamp] Upload started: $dropboxPath from $localFilePath\n", FILE_APPEND);

        if (!file_exists($localFilePath)) {
            Log::error("Dropbox upload failed: File not found at $localFilePath");
            error_log("Dropbox upload failed: File not found at $localFilePath");
            file_put_contents($logFile, "[$timestamp] File not found: $localFilePath\n", FILE_APPEND);
            throw new \Exception("File not found: $localFilePath");
        }

        try {
            // Initial attempt
            return $this->performUpload($localFilePath, $dropboxPath);
        } catch (\Exception $e) {
            $msg = $e->getMessage();
            $class = get_class($e);
            $timestamp = date('Y-m-d H:i:s');

            file_put_contents($logFile, "[$timestamp] FIRST FAILURE: Caught $class: $msg\n", FILE_APPEND);
            Log::warning("Dropbox upload first failure $class: $msg");
            error_log("Dropbox upload first failure $class: $msg");

            // Check if it's a 401 error or token-related error
            // Scanning the message and the class name for typical unauthorized markers
            $isUnauthorized = str_contains($msg, '401') ||
                             str_contains($msg, 'invalid_access_token') ||
                             str_contains(strtolower($class), 'unauthorized') ||
                             str_contains(strtolower($msg), 'unauthorized');

            if ($isUnauthorized) {
                Log::info('Dropbox upload failed with unauthorized-like error, attempting token refresh and retry');
                error_log('Dropbox: upload failed with unauthorized-like error, attempting token refresh and retry');

                $tokenRecord = DropboxToken::first();
                if ($tokenRecord && !empty($tokenRecord->refresh_token)) {
                    try {
                        $tokenRecord = $this->refreshTokens($tokenRecord);
                        $newToken = $tokenRecord->access_token; // Capture fresh token for retry if needed

                        // Get the fresh token from memory for the retry, bypass potential DB truncation
                        $freshAccessToken = $newToken;

                        Log::info('Dropbox refresh success, retrying upload with forced new client');
                        error_log('Dropbox: refresh success, retrying upload with forced new client');
                        file_put_contents($logFile, "[$timestamp] RETRYING with forced new client and token: " . substr($freshAccessToken, 0, 10) . "...\n", FILE_APPEND);

                        // Retry the upload - FORCE fresh client by using the token explicitly
                        try {
                            // Small delay to allow Dropbox to propagate the new token if needed
                            sleep(2);
                            return $this->performUpload($localFilePath, $dropboxPath, $freshAccessToken);
                        } catch (\Exception $retryEx) {
                            $retryMsg = $retryEx->getMessage();
                            $retryClass = get_class($retryEx);
                            file_put_contents($logFile, "[$timestamp] RETRY FAILED: $retryClass: $retryMsg\n", FILE_APPEND);
                            Log::error("Dropbox upload retry failed $retryClass: $retryMsg");
                            error_log("Dropbox upload retry failed $retryClass: $retryMsg");
                            throw $retryEx;
                        }
                    } catch (\Exception $refreshEx) {
                        Log::error('Dropbox token refresh failed during retry: ' . $refreshEx->getMessage());
                        error_log('Dropbox token refresh failed during retry: ' . $refreshEx->getMessage());
                        file_put_contents($logFile, "[$timestamp] REFRESH FAILED: " . $refreshEx->getMessage() . "\n", FILE_APPEND);
                        throw $refreshEx;
                    }
                } else {
                    $reason = !$tokenRecord ? "No token record" : "No refresh token";
                    error_log("Dropbox: Refresh aborted: $reason");
                    file_put_contents($logFile, "[$timestamp] REFRESH ABORTED: $reason\n", FILE_APPEND);
                }
            }
            throw $e;
        }
    }

    protected function performUpload($localFilePath, $dropboxPath, $token = null)
    {
        $client = $this->getClient($token);

        $tokenToLog = $token ?: (DropboxToken::first()?->access_token ?? 'none');
        Log::debug("Dropbox performUpload: Using token prefix " . substr($tokenToLog, 0, 10) . " (len: " . strlen($tokenToLog) . ")");

        $handle = fopen($localFilePath, 'r');
        try {
            $client->upload($dropboxPath, $handle, 'overwrite');
        } finally {
            if (is_resource($handle)) {
                fclose($handle);
            }
        }
        return $dropboxPath;
    }

    protected function isExpired($tokenRecord)
    {
        // expires_in in DB is a timestamp (stored as expires_in + time() in legacy code and refreshTokens below)
        return ($tokenRecord->expires_in - time()) <= 60; // Refresh if less than a minute left
    }

    public function refreshTokens($tokenRecord)
    {
        $logFile = storage_path('logs/dropbox_debug.log');
        $timestamp = date('Y-m-d H:i:s');

        if (empty($tokenRecord->refresh_token)) {
            file_put_contents($logFile, "[$timestamp] Refresh aborted: No refresh token in record ID: {$tokenRecord->id}\n", FILE_APPEND);
            error_log("Dropbox: Refresh aborted: No refresh token in record ID: {$tokenRecord->id}");
            throw new \Exception('No Dropbox refresh token found to refresh.');
        }

        $oldTokenPrefix = substr($tokenRecord->access_token, 0, 10);
        file_put_contents($logFile, "[$timestamp] Refreshing tokens for ID: {$tokenRecord->id} with refresh_token: " . substr($tokenRecord->refresh_token, 0, 10) . "... (Old access token: $oldTokenPrefix...)\n", FILE_APPEND);
        error_log("Dropbox: Refreshing tokens for ID: {$tokenRecord->id}... (Old access token: $oldTokenPrefix...)");

        // Use Basic Auth + form parameters as seen in FuelPHP version, more robust for some apps
        $response = Http::withHeaders([
                'Authorization' => 'Basic ' . base64_encode($this->clientId . ':' . $this->clientSecret),
            ])
            ->asForm()
            ->timeout(30)
            ->post($this->tokenUrl, [
                'grant_type' => 'refresh_token',
                'refresh_token' => $tokenRecord->refresh_token,
            ]);

        if ($response->failed()) {
            $status = $response->status();
            $errorData = $response->json() ?? $response->body();
            $errorStr = is_array($errorData) ? json_encode($errorData) : $errorData;

            file_put_contents($logFile, "[$timestamp] Refresh failed (Status $status): $errorStr\n", FILE_APPEND);
            Log::error('Dropbox token refresh failed', [
                'status' => $status,
                'response' => $errorData
            ]);
            error_log("Dropbox token refresh failed (Status $status): $errorStr");
            throw new \Exception("Failed to refresh Dropbox tokens (Status $status): " . ($response->json()['error_description'] ?? $errorStr));
        }

        $data = $response->json();
        $newToken = $data['access_token'];
        $newTokenPrefix = substr($newToken, 0, 10);
        $tokenLen = strlen($newToken);

        file_put_contents($logFile, "[$timestamp] Refresh success. New token prefix: $newTokenPrefix, length: $tokenLen\n", FILE_APPEND);
        error_log("Dropbox refresh success. New token starting with: $newTokenPrefix, length: $tokenLen");

        // Update record including new refresh_token if provided (Token Rotation support)
        $updateData = [
            'access_token' => $newToken,
            'token_type' => $data['token_type'] ?? 'bearer',
            'expires_in' => isset($data['expires_in']) ? (int)$data['expires_in'] + time() : 0,
            'updated_at' => now(),
        ];

        if (!empty($data['refresh_token'])) {
            $updateData['refresh_token'] = $data['refresh_token'];
            file_put_contents($logFile, "[$timestamp] Refresh token rotated.\n", FILE_APPEND);
        }

        $tokenRecord->update($updateData);

        // Manually set the full token on the object to ensure it's available even if DB truncated it
        $tokenRecord->access_token = $newToken;

        $tokenRecord->refresh();

        $savedTokenLen = strlen($tokenRecord->access_token);
        if ($savedTokenLen < $tokenLen) {
            $msg = "WARNING: Dropbox access token truncated from $tokenLen to $savedTokenLen characters in database!";
            Log::warning($msg);
            error_log($msg);
            file_put_contents($logFile, "[$timestamp] $msg\n", FILE_APPEND);

            // Re-apply full token to memory object after refresh() pulled truncated one
            $tokenRecord->access_token = $newToken;
        }

        Log::info('Dropbox tokens refreshed successfully', [
            'expires_in' => $tokenRecord->expires_in,
            'current_time' => time(),
            'diff' => $tokenRecord->expires_in - time(),
            'new_token_prefix' => $newTokenPrefix,
            'token_length' => $tokenLen,
            'old_token_prefix' => $oldTokenPrefix
        ]);

        return $tokenRecord;
    }
}
