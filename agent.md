# Agent Guide: buy-dtf-laravel

## Project Snapshot
- Framework: Laravel 12, PHP 8.2+.
- Frontend: Blade + Vite + Tailwind + Bootstrap + Alpine.
- Main domain: DTF order flow (cart -> checkout -> payment -> production/shipping), with admin tooling.
- Integrations: Stripe (payments + payouts), QuickBooks Online (invoices/payments/fees/transfers), Shippo (shipping labels/rates), Dropbox (file handling).
- Legacy context: mixed Laravel + FuelPHP-era schema/logic patterns are still present.

## Local Runbook
- Environment requirement: run `php artisan` and MySQL-related commands in WSL (not native Windows shell).
- Install: `composer install` and `npm install`
- Env: copy `.env.example` to `.env`, set app key with `php artisan key:generate`
- Migrate: `php artisan migrate`
- Run app stack: `composer run dev` 
- Build assets: `npm run build`

## Test Status Notes
- `php artisan test` currently fails in this environment because PHP `mbstring` is missing.
- Install/enable required PHP extensions before relying on test results.

## Architecture Notes
- Web routes: `routes/web.php`
- Admin routes: `routes/admin.php` (loaded via `bootstrap/app.php`)
- API/webhooks: `routes/api.php`
- Checkout flow: `App\Http\Controllers\Checkout\CheckoutController`
- Stripe webhooks: `App\Http\Controllers\Webhook\StripeWebhookController`
- Payout sync command: `php artisan stripe:sync-payouts` (also scheduled hourly in `routes/console.php`)

## Data + Connections
- Default Laravel connection from `DB_CONNECTION`.
- Fuel/legacy models extend `App\Models\FuelModel` and default to `FUEL_DB_CONNECTION` (`fuelmysql` unless overridden).
- Key order model: `App\Models\DtfOrder` (table `dtforders` on Fuel connection).

## Important Domain Rules
- Stripe checkout completion marks order status to `2` (paid/processing) and attempts QBO sync.
- Invoice checkout can finalize order even if QBO invoice creation fails (logged, then local completion continues).
- Stripe fees are intended to be recorded in QBO immediately at charge time.
- Payout sync records Stripe payouts and can create QBO transfers for paid payouts.

## Known Risks To Tackle Early
- `config/database.php` currently contains a hardcoded remote DB credential block (`remotefuel`) that should be moved to environment variables only.
- Several debug/test routes exist in `routes/web.php` (Dropbox/user debug) and should be environment-gated or removed for production.
- Checkout/controller code is very large and heavily stateful; high regression risk without additional feature/integration tests.

## Suggested Work Priorities
1. Remove hardcoded secrets from config and rotate exposed credentials.
2. Add/restore testability (PHP extensions + sqlite-safe tests for checkout/payment webhooks).
3. Restrict debug endpoints to local/dev only.
4. Incrementally split large controllers/services into smaller units with explicit contracts.

## Agent Working Conventions
- Prefer minimal, scoped edits over broad refactors unless requested.
- When touching payment/fulfillment flows, keep idempotency checks and audit logs intact.
- Preserve dual-connection behavior (Laravel DB vs Fuel DB) unless migration strategy is explicitly defined.
- For any Stripe/QBO changes, verify both local state updates and external-sync side effects.
