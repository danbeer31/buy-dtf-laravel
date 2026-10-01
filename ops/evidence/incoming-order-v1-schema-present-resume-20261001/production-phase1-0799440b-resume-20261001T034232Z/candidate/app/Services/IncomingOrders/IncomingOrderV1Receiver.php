<?php

namespace App\Services\IncomingOrders;

use App\Exceptions\ArtworkFetchException;
use App\Exceptions\ArtworkValidationException;
use App\Exceptions\DuplicateJsonKeyException;
use App\Exceptions\IncomingOrderValidationException;
use App\Models\ApiAssetRecord;
use App\Models\Business;
use App\Models\DtfImage;
use App\Models\DtfOrder;
use App\Models\IncomingOrderJob;
use App\Support\JsonCanonicalizer;
use App\Support\StrictJson;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use JsonException;
use RuntimeException;
use stdClass;
use Throwable;

class IncomingOrderV1Receiver
{
    public function __construct(
        private readonly JsonCanonicalizer $canonicalizer,
        private readonly IncomingOrderV1Validator $validator,
        private readonly IncomingOrderIdempotency $idempotency,
        private readonly BoundedArtworkFetcher $fetcher,
        private readonly ArtworkInspector $inspector,
        private readonly IncomingOrderAssetStore $assetStore,
    ) {}

    public function handle(Request $request, string $rawBody): JsonResponse
    {
        $deadlineNs = hrtime(true)
            + (max(1, (int) config('incoming_order.request_budget_seconds', 60)) * 1_000_000_000);
        $correlationId = (string) Str::uuid();

        if (! $this->isJsonContentType((string) $request->header('Content-Type'))) {
            return $this->error(415, 'unsupported_media_type', 'application_json_required');
        }
        if (strlen($rawBody) > max(1024, (int) config('incoming_order.request_max_bytes', 128 * 1024))) {
            return $this->error(413, 'request_too_large', 'request_body_too_large');
        }

        try {
            $decoded = StrictJson::decode($rawBody);
        } catch (DuplicateJsonKeyException) {
            return $this->error(400, 'malformed_json', 'duplicate_json_key');
        } catch (JsonException) {
            return $this->error(400, 'malformed_json', 'invalid_json');
        }

        if (! $decoded instanceof stdClass) {
            return $this->error(400, 'malformed_json', 'object_required');
        }

        $providedSignature = $decoded->signature ?? null;
        if (! is_string($providedSignature) || ! preg_match('/^[a-f0-9]{64}$/D', $providedSignature)) {
            return $this->error(401, 'authentication_failed', 'invalid_signature');
        }

        $signingObject = clone $decoded;
        unset($signingObject->signature);
        $secret = (string) config('incoming_order.shared_secret', '');
        if ($secret === '') {
            Log::warning('Incoming order v1 rejected because receiver secret is unavailable.', [
                'correlation_id' => $correlationId,
            ]);

            return $this->error(503, 'receiver_unavailable', 'receiver_secret_unavailable');
        }

        try {
            $signingBytes = $this->canonicalizer->canonicalize($signingObject);
        } catch (Throwable) {
            return $this->error(400, 'malformed_json', 'canonicalization_failed');
        }
        $computedSignature = hash_hmac('sha256', $signingBytes, $secret);
        if (! hash_equals($computedSignature, $providedSignature)) {
            Log::notice('Incoming order v1 signature mismatch.', [
                'correlation_id' => $correlationId,
            ]);

            return $this->error(401, 'authentication_failed', 'invalid_signature');
        }

        if (! (bool) config('incoming_order.receiver_enabled', false)) {
            return $this->error(503, 'capability_disabled', 'receiver_idempotency_v1_disabled');
        }

        try {
            $data = StrictJson::toAssociative($decoded);
            if (! is_array($data)) {
                throw new IncomingOrderValidationException('validation_failed', 'object_required');
            }
            $validated = $this->validator->validate($data);
            $this->assertBeforeDeadline($deadlineNs);
        } catch (ArtworkFetchException $exception) {
            return $this->error(503, 'receiver_unavailable', $exception->reason)
                ->header('Retry-After', '5');
        } catch (IncomingOrderValidationException $exception) {
            return $this->error($exception->status, $exception->errorCode, $exception->reason);
        } catch (Throwable) {
            return $this->error(422, 'validation_failed', 'invalid_value');
        }

        $keyHash = hash('sha256', $validated['idempotency_key']);
        $initial = $this->initialJobAttributes($validated);
        $claim = $this->idempotency->claim(
            (string) config('incoming_order.integration_client', 'shopnltees'),
            $validated['idempotency_key'],
            $validated['request_fingerprint'],
            $initial,
        );

        if ($claim->outcome === 'conflict') {
            return response()->json([
                'success' => false,
                'error' => [
                    'code' => 'idempotency_conflict',
                    'message' => 'This idempotency key was already used with a different payload.',
                ],
                'receiver' => $this->receiverSummary($validated, $claim->job, false),
            ], 409);
        }
        if ($claim->outcome === 'replay') {
            $response = $claim->job->response_payload;
            if (! is_array($response)) {
                return $this->error(503, 'receiver_unavailable', 'frozen_response_unavailable');
            }
            $response['receiver']['replayed'] = true;
            $response['receiver']['attempt_count'] = (int) $claim->job->attempt_count;

            return response()->json($response);
        }
        if ($claim->outcome === 'processing') {
            return response()->json([
                'success' => false,
                'receiver' => $this->receiverSummary($validated, $claim->job, false, 'processing'),
            ], 202)->header('Retry-After', (string) ($claim->retryAfter ?? 5));
        }
        if ($claim->outcome === 'permanent_failure') {
            if ($claim->job->last_error_code === 'idempotency_attempts_exhausted') {
                return $this->attemptsExhaustedResponse();
            }
            if (is_array($claim->job->response_payload)) {
                return response()->json($claim->job->response_payload, 422);
            }

            return $this->error(422, 'artwork_invalid', (string) ($claim->job->last_error_code ?: 'permanent_failure'));
        }
        if ($claim->outcome === 'attempts_exhausted') {
            return $this->attemptsExhaustedResponse();
        }

        $owner = (string) $claim->owner;
        $this->idempotency->cleanupOwnerTemporaryFiles($claim->expiredOwner);
        $fetched = null;

        try {
            $this->assertBeforeDeadline($deadlineNs);
            $heartbeat = function () use ($claim, $owner): void {
                if (! $this->idempotency->heartbeat((int) $claim->job->id, $owner)) {
                    throw new RuntimeException('Incoming-order processing lease was lost.');
                }
            };

            $fetched = $this->fetcher->fetch(
                $validated['design']['image_url'],
                $owner,
                $heartbeat,
                $deadlineNs,
            );
            $heartbeat();
            $this->assertBeforeDeadline($deadlineNs);
            $artwork = $this->inspector->inspect($fetched);
            $this->assertBeforeDeadline($deadlineNs);
            if (! hash_equals($validated['design']['sha256'], $artwork->sha256)) {
                throw new ArtworkValidationException('artwork_hash_mismatch');
            }
            $this->inspector->assertRequestedAspect(
                $artwork,
                $validated['design']['width_in'],
                $validated['design']['height_in'],
            );
            $this->assertBeforeDeadline($deadlineNs);
            $promoted = $this->assetStore->promoteOriginal($artwork);
            $fetched = null;
            $heartbeat();
            $this->assertBeforeDeadline($deadlineNs);

            $response = $this->completeJob(
                $claim->job,
                $owner,
                $validated,
                $artwork,
                $promoted,
                $deadlineNs,
            );
            Log::info('Incoming order v1 completed.', [
                'correlation_id' => $correlationId,
                'idempotency_key_hash' => $keyHash,
                'request_fingerprint' => $validated['request_fingerprint'],
                'incoming_order_job_id' => $claim->job->id,
                'status' => 'completed',
            ]);

            return response()->json($response);
        } catch (ArtworkValidationException $exception) {
            $this->removeTemporary($fetched);
            $response = [
                'success' => false,
                'error' => [
                    'code' => 'artwork_invalid',
                    'reason' => $exception->reason,
                ],
                'receiver' => $this->receiverSummary($validated, $claim->job, false, 'permanent_failure'),
            ];
            $this->idempotency->fail((int) $claim->job->id, $owner, $exception->reason, false, $response);

            return response()->json($response, 422);
        } catch (ArtworkFetchException $exception) {
            $this->removeTemporary($fetched);
            $status = $exception->retryable ? 503 : 422;
            $response = [
                'success' => false,
                'error' => [
                    'code' => $exception->retryable ? 'artwork_fetch_retryable' : 'artwork_invalid',
                    'reason' => $exception->reason,
                ],
                'receiver' => $this->receiverSummary(
                    $validated,
                    $claim->job,
                    false,
                    $exception->retryable ? 'retryable_failure' : 'permanent_failure',
                ),
            ];
            $this->idempotency->fail(
                (int) $claim->job->id,
                $owner,
                $exception->reason,
                $exception->retryable,
                $exception->retryable ? null : $response,
            );

            $json = response()->json($response, $status);

            return $exception->retryable ? $json->header('Retry-After', '5') : $json;
        } catch (Throwable $exception) {
            $this->removeTemporary($fetched);
            $this->idempotency->fail((int) $claim->job->id, $owner, 'receiver_processing_failed', true);
            Log::error('Incoming order v1 processing failed.', [
                'correlation_id' => $correlationId,
                'idempotency_key_hash' => $keyHash,
                'request_fingerprint' => $validated['request_fingerprint'],
                'incoming_order_job_id' => $claim->job->id,
                'exception_class' => $exception::class,
            ]);

            return $this->error(503, 'receiver_unavailable', 'receiver_processing_failed')
                ->header('Retry-After', '5');
        }
    }

    /** @return array<string, mixed> */
    private function initialJobAttributes(array $validated): array
    {
        $label = $validated['job_label'];

        return [
            'expected_art_sha256' => $validated['design']['sha256'],
            'art_width_in' => $validated['design']['width_in'],
            'art_height_in' => $validated['design']['height_in'],
            'job_label_version' => $label['status'] !== null ? 1 : null,
            'job_label_required' => $label['required'],
            'job_label_mode' => $label['mode'],
            'job_label_status' => $label['status'],
            'job_label_reason' => $label['reason'],
            'job_label_metadata' => $label['metadata'],
            'job_label_fingerprint' => $label['fingerprint'],
            'renderer_version' => $label['status'] === 'accepted'
                ? JobCardRenderer::RENDERER_VERSION
                : null,
            'production_state' => $label['status'] === 'accepted' ? 'pending' : null,
        ];
    }

    /**
     * @param  array<string, mixed>  $promoted
     * @return array<string, mixed>
     */
    private function completeJob(
        IncomingOrderJob $reservedJob,
        string $owner,
        array $validated,
        InspectedArtwork $artwork,
        array $promoted,
        int $deadlineNs,
    ): array {
        $connection = (string) config('database.fuel_connection');

        return DB::connection($connection)->transaction(function () use (
            $reservedJob,
            $owner,
            $validated,
            $artwork,
            $promoted,
            $deadlineNs,
        ): array {
            $this->assertBeforeDeadline($deadlineNs);
            $job = IncomingOrderJob::query()->whereKey($reservedJob->id)->lockForUpdate()->firstOrFail();
            if ($job->state !== 'processing' || ! hash_equals((string) $job->lease_owner, $owner)) {
                throw new RuntimeException('Incoming-order processing lease was lost before completion.');
            }
            if (! is_file($promoted['absolute_path'])
                || ! hash_equals($artwork->sha256, (string) hash_file('sha256', $promoted['absolute_path']))) {
                throw new RuntimeException('Immutable artwork verification failed before database completion.');
            }
            $this->assertBeforeDeadline($deadlineNs);

            $business = Business::query()
                ->whereKey((int) config('incoming_order.business_id', 1))
                ->lockForUpdate()
                ->first();
            if ($business === null) {
                throw new RuntimeException('Configured incoming-order business is unavailable.');
            }
            $order = DtfOrder::query()
                ->where('business_id', $business->id)
                ->where('status', 1)
                ->lockForUpdate()
                ->first();
            if ($order === null) {
                $order = DtfOrder::query()->create([
                    'business_id' => $business->id,
                    'status' => 1,
                    'order_date' => now(),
                ]);
            }
            $this->assertBeforeDeadline($deadlineNs);

            $origWidth = round($artwork->widthPx / 300, 4);
            $origHeight = round($artwork->heightPx / 300, 4);
            $requestWidth = (float) $validated['design']['width_in'];
            $requestHeight = (float) $validated['design']['height_in'];
            $image = DtfImage::query()->create([
                'dtforder_id' => $order->id,
                'image' => $promoted['relative_path'],
                'native_filename' => $validated['file_name'],
                'image_notes' => 'Image for Invoice# '.$validated['source_order_id'],
                'image_name' => $validated['file_name'],
                'width' => $requestWidth,
                'height' => $requestHeight,
                'quantity' => $validated['design']['quantity'],
                'date_uploaded' => now(),
                'production' => 0,
                'file_size' => $artwork->bytes,
                'sha256_original' => $artwork->sha256,
                'upload_mime' => $artwork->mime,
                'item_type' => 'standard',
                'orig_width' => $origWidth,
                'orig_height' => $origHeight,
                'width_ratio' => $origWidth > 0 ? round($requestWidth / $origWidth, 6) : null,
                'height_ratio' => $origHeight > 0 ? round($requestHeight / $origHeight, 6) : null,
            ]);

            $response = [
                'success' => true,
                'duplicate' => (bool) $promoted['duplicate'],
                'file' => $promoted['relative_path'],
                'order_id' => $order->id,
                'dtfimage_id' => $image->id,
                'job_id' => $validated['source_order_id'],
                'file_size' => $artwork->bytes,
                'sha256' => $artwork->sha256,
                'orig_width_in' => $origWidth,
                'orig_height_in' => $origHeight,
                'width_ratio' => $origWidth > 0 ? round($requestWidth / $origWidth, 6) : null,
                'height_ratio' => $origHeight > 0 ? round($requestHeight / $origHeight, 6) : null,
                'receiver' => $this->receiverSummary($validated, $job, false, 'completed'),
            ];
            if ($validated['job_label']['status'] !== null) {
                $response['job_label'] = $this->labelResponse($validated);
            }

            $job->forceFill([
                'dtfimage_id' => $image->id,
                'actual_art_sha256' => $artwork->sha256,
                'original_asset_path' => $promoted['relative_path'],
                'original_asset_sha256' => $artwork->sha256,
                'state' => 'completed',
                'lease_owner' => null,
                'lease_expires_at' => null,
                'heartbeat_at' => null,
                'response_payload' => $response,
                'last_error_code' => null,
            ])->save();

            ApiAssetRecord::query()->create([
                'incoming_order_job_id' => $job->id,
                'dtfimage_id' => $image->id,
                'origin' => 'incoming_order_v1',
                'asset_role' => 'original',
                'storage_scope' => 'public_root',
                'asset_path' => $promoted['relative_path'],
                'path_hash' => hash('sha256', $promoted['relative_path']),
                'sha256' => $artwork->sha256,
                'bytes' => $artwork->bytes,
                'retention_policy' => 'forever',
                'retention_enabled' => false,
                'retention_days' => null,
                'expires_at' => null,
            ]);
            $this->assertBeforeDeadline($deadlineNs);

            return $response;
        }, 3);
    }

    /** @return array<string, mixed> */
    private function receiverSummary(
        array $validated,
        IncomingOrderJob $job,
        bool $replayed,
        ?string $status = null,
    ): array {
        return [
            'contract' => 'incoming_order_v1',
            'idempotency_key' => $validated['idempotency_key'],
            'request_fingerprint' => $validated['request_fingerprint'],
            'status' => $status ?? (string) $job->state,
            'attempt_count' => (int) $job->attempt_count,
            'replayed' => $replayed,
        ];
    }

    /** @return array<string, mixed> */
    private function labelResponse(array $validated): array
    {
        $label = $validated['job_label'];

        return [
            'status' => $label['status'],
            'version' => 1,
            'mode' => $label['mode'],
            'reason' => $label['reason'],
            'art_width_in' => $validated['design']['width_in'],
            'art_height_in' => $validated['design']['height_in'],
            'artwork_modified' => false,
            'job_card' => [
                'artifact' => 'separate',
                'status' => $label['status'] === 'accepted' ? 'pending_production' : 'not_requested',
                'quantity' => $label['status'] === 'accepted' ? 1 : 0,
            ],
        ];
    }

    private function assertBeforeDeadline(int $deadlineNs): void
    {
        if (hrtime(true) >= $deadlineNs) {
            throw new ArtworkFetchException('receiver_request_budget_exceeded', true);
        }
    }

    private function isJsonContentType(string $contentType): bool
    {
        return preg_match(
            '/^\s*application\/json(?:\s*;\s*[!#$%&\'*+.^_`|~0-9A-Za-z-]+=(?:"[^"\r\n]*"|[!#$%&\'*+.^_`|~0-9A-Za-z-]+))*\s*$/Di',
            $contentType,
        ) === 1;
    }

    private function attemptsExhaustedResponse(): JsonResponse
    {
        return $this->error(503, 'receiver_unavailable', 'idempotency_attempts_exhausted')
            ->header('Retry-After', '60');
    }

    private function removeTemporary(?FetchedArtwork $fetched): void
    {
        if ($fetched === null) {
            return;
        }
        @unlink($fetched->temporaryPath);
        $directory = dirname($fetched->temporaryPath);
        if (@scandir($directory) === ['.', '..']) {
            @rmdir($directory);
        }
    }

    private function error(int $status, string $code, string $reason): JsonResponse
    {
        return response()->json([
            'success' => false,
            'error' => [
                'code' => $code,
                'reason' => $reason,
            ],
        ], $status);
    }
}
