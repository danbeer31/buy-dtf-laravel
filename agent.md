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

## Production Server
- Production URL: `https://buy-dtf.com`
- SSH: `ssh dan@134.209.175.25`
- App path: `/var/www/buy-dtf`
- Common production checks:
  - `cd /var/www/buy-dtf`
  - `php -l path/to/file.php`
  - `php artisan optimize:clear`
- User preference: for this site, apply urgent fixes directly to production when requested, then push the source changes to GitHub.
- Before overwriting a production file, create a narrow backup with a descriptive suffix, for example:
  - `cp app/Some/File.php app/Some/File.php.bak-short-reason`
- Prefer targeted `scp` deploys for changed files because the production git checkout has been messy/detached in the past.
- Do not deploy or commit `.env`, uploads, logs, caches, SQL dumps, `vendor/`, `node_modules/`, `public/build/`, or `.bak-*` files.

## GitHub Sync
- Repository: `git@github.com:danbeer31/buy-dtf-laravel.git`
- Primary branch: `main`
- After production fixes, push matching source changes to GitHub.
- The local workspace often has many dirty/untracked files. Do not run destructive cleanup, reset, or checkout commands unless the user explicitly asks.
- For GitHub commits, use a clean temporary clone when the local workspace is dirty:
  1. `git clone git@github.com:danbeer31/buy-dtf-laravel.git <temp-dir>`
  2. Copy only the changed source files into the clean clone.
  3. Run syntax checks, such as `php -l`.
  4. `git add`, `git commit`, and `git push origin main`.
  5. In the main local workspace, run `git fetch origin` to update remote refs without touching dirty files.
- If syncing a broad production snapshot, explicitly exclude runtime and secret paths:
  - `.env`
  - `vendor/`
  - `node_modules/`
  - `public/uploads/`
  - `public/build/`
  - `bootstrap/cache/`
  - `storage/framework/`
  - `storage/logs/`
  - `storage/app/public/`
  - SQL dumps, logs, result files, and backup files

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
