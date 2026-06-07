<?php

namespace App\Http\Controllers\Webhook;

use App\Http\Controllers\Controller;
use App\Models\StripeWebhookEvent;
use App\Models\StripeSyncLog;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Stripe\Exception\SignatureVerificationException;
use Stripe\Webhook;

class StripeWebhookController extends Controller
{
    public function handle(Request $request)
    {
        $payload = $request->getContent();
        $sigHeader = $request->header('Stripe-Signature');
        Log::info('Stripe webhook inbound metadata', [
            'signature_header_present' => !empty($sigHeader),
            'payload_length' => strlen((string) $payload),
        ]);
        $primarySecret = (string) config('services.stripe.webhook_secret');
        $extraSecrets = config('services.stripe.webhook_secrets', []);
        $prodSecret = (string) env('STRIPE_WEBHOOK_SECRET_PROD', '');
        $devSecret = (string) env('STRIPE_WEBHOOK_SECRET_DEV', '');
        $legacySecret = (string) env('STRIPE_WEBHOOK_SECRET', '');
        $candidateSecrets = array_values(array_unique(array_filter(array_merge(
            [$primarySecret, $prodSecret, $devSecret, $legacySecret],
            is_array($extraSecrets) ? $extraSecrets : []
        ))));

        try {
            $event = null;

            if (empty($candidateSecrets)) {
                Log::error('Stripe Webhook Error: No webhook secret configured');
                return response()->json(['error' => 'Webhook secret not configured'], 500);
            }

            foreach ($candidateSecrets as $secret) {
                try {
                    $event = Webhook::constructEvent(
                        $payload,
                        $sigHeader,
                        $secret
                    );
                    break;
                } catch (SignatureVerificationException $e) {
                    // Try next configured secret (rotation/fallback support).
                    continue;
                }
            }

            if (!$event) {
                Log::error('Stripe Webhook Error: Invalid signature', [
                    'error' => 'No signatures found matching the expected signature for payload',
                    'candidate_secret_count' => count($candidateSecrets),
                ]);
                return response()->json(['error' => 'Invalid signature'], 400);
            }
        } catch (\UnexpectedValueException $e) {
            // Invalid payload
            Log::error('Stripe Webhook Error: Invalid payload', ['error' => $e->getMessage()]);
            return response()->json(['error' => 'Invalid payload'], 400);
        }

        // Idempotency check
        $existingEvent = StripeWebhookEvent::where('stripe_event_id', $event->id)->first();
        if ($existingEvent) {
            return response()->json(['message' => 'Event already processed'], 200);
        }

        // Store event
        $webhookEvent = StripeWebhookEvent::create([
            'stripe_event_id' => $event->id,
            'type' => $event->type,
            'payload' => $event->toArray(),
        ]);

        StripeSyncLog::log('webhook', 'success', "Received {$event->type} webhook.", $event->id, $event->type);

        // Process event
        switch ($event->type) {
            case 'payout.paid':
            case 'payout.failed':
            case 'payout.updated':
                // Dispatch job for payout events
                \App\Jobs\ProcessStripePayoutWebhook::dispatch($webhookEvent->id);
                break;
            case 'balance.available':
                Log::info('Stripe Webhook: balance.available event received', ['event_id' => $event->id]);
                $webhookEvent->update(['processed_at' => now()]);
                break;
            default:
                Log::info('Stripe Webhook: Received unhandled event type ' . $event->type);
        }

        return response()->json(['message' => 'Webhook handled'], 200);
    }
}
