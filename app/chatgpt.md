CODEX HANDOFF — Add Stripe ↔ QBO Reconciliation Check
Scope

Add a read-only reconciliation / health-check layer to both:

ShopNLTees shops

buy-dtf.com

This must NOT change existing accounting posting logic.

The current accounting pipeline already works like this:

Sales receipts post to Stripe Holding

Stripe fees post as expense / bank charges paid from Stripe Holding

Refunds / reversals reduce Stripe Holding

Stripe payouts post as Transfer: Stripe Holding → Main Bank

Bank feed transactions in QBO are later matched to the posted transfers

The new work is only to verify that the math is still correct and flag mismatches.

Core Goal

Add a reconciliation feature that answers:

Based on everything we posted, what should the Stripe Holding balance be for this shop?
Does that match QuickBooks?

This is a monitoring / verification layer only.

Do not refactor or alter:

current Stripe sync logic

current QBO posting logic

current payout sync logic

current fee sync logic

current sales receipt generation logic

Business Rule

For each shop/accounting connection:

Expected Stripe Holding Balance
=
Sales Receipts posted to Stripe Holding
- Stripe Fees posted from Stripe Holding
- Refunds / reversals / disputes posted from Stripe Holding
- Payout Transfers posted from Stripe Holding to Main Bank

Compare that to:

Actual QBO Stripe Holding balance

If the difference is within tolerance (<= 0.01), status is balanced.

If not, status is mismatch / investigate.

Important Constraints
1. Read-only against existing posting flow

This feature must not create, modify, or delete accounting transactions.

It only:

reads existing synced/app records

optionally reads QBO account balance or computes actual balance from synced posted transactions

compares numbers

stores reconciliation results

shows admin warnings/status

2. Shared architecture

This should be implemented in a reusable way because both:

ShopNLTees

buy-dtf.com

use the same accounting model/pattern

Prefer extracting reusable service/class patterns where practical.

3. Idempotent

Running the reconciliation multiple times must be safe.

Deliverables

Implement all of the following.

A. Database table for reconciliation logs

Create a new table for storing reconciliation snapshots.

Suggested name:

accounting_reconciliation_checks

Suggested columns:

id
shop_id
provider                  // 'stripe'
scope                     // optional: 'daily', 'current', 'as_of'
as_of_date                // nullable date for daily snapshot
currency                  // nullable, default USD if applicable

expected_holding_amount_cents
actual_holding_amount_cents
difference_amount_cents

status                    // balanced, mismatch, error
tolerance_cents           // default 1
notes                     // nullable text/json
meta                      // nullable json

ran_at
created_at
updated_at

If each app already has conventions for audit/log tables, follow local convention.

Use integer cents, not floating math.

B. Reconciliation service

Create a dedicated service, something like:

App\Services\Accounting\StripeQboReconciliationService

or equivalent namespace for each project.

Responsibilities:

1. Compute expected holding balance

Using existing synced records already stored by the app.

Do not scrape raw QBO transaction lists unless there is no existing internal record structure.

Preferred data sources:

posted daily sales receipts

posted fee sync records

posted refund/reversal records

posted payout transfer records

Use only records that are marked as successfully posted/synced.

2. Determine actual QBO holding balance

Preferred order:

If the codebase already has a reliable way to retrieve QBO account balance for the Stripe Holding account, use that.

Otherwise compute actual from the app’s own posted QBO-linked transaction records if that is the current source of truth.

If neither is available cleanly, add a small QBO helper to fetch the relevant account balance safely.

3. Compare and return result

Return a DTO/array like:

[
'shop_id' => 123,
'provider' => 'stripe',
'as_of_date' => '2026-03-09',
'expected_holding_amount_cents' => 0,
'actual_holding_amount_cents' => 0,
'difference_amount_cents' => 0,
'tolerance_cents' => 1,
'status' => 'balanced',
'notes' => null,
'meta' => [...],
]
C. Nightly command / cron job

Add an Artisan command / console command like:

php artisan accounting:reconcile-stripe-holding

Requirements:

loops eligible shops

skips shops without Stripe + QBO accounting enabled

runs reconciliation

stores one log row per shop

safe to rerun

prints summary to console

Optional flags:

--shop_id=

--date=YYYY-MM-DD

--dry-run

D. Admin UI

Add an admin page / card to show reconciliation results.

Minimum columns:

Shop

As Of

Expected Holding

Actual Holding

Difference

Status

Ran At

Action (Re-run)

Recommended statuses:

Balanced

Mismatch

Error

Recommended visual badges:

green = balanced

yellow/red = mismatch

gray/red = error

Minimum UI requirements

A list/table of recent reconciliation runs

A row/detail page or expandable detail section showing component totals:

sales receipts total

fee total

refund total

payout transfer total

expected holding

actual holding

difference

Re-run action

Add a button to re-run reconciliation for a shop on demand.

This does not repost accounting.
It only recomputes and stores a fresh reconciliation result.

E. Dashboard alert / health summary

Add a lightweight summary widget where appropriate.

Example:

Stripe/QBO Reconciliation
Balanced Shops: 14
Mismatches: 2
Errors: 1

If there is a mismatch, provide a link to the reconciliation page.

Matching / Data Rules
What counts toward expected holding
Positive to Stripe Holding

Sales receipts deposited to Stripe Holding

Negative from Stripe Holding

Stripe fees

Refunds

Disputes / chargebacks

Other reversals/adjustments if already part of current accounting design

Payout transfers to Main Bank

Use the project’s existing accounting semantics. Do not invent new accounting behavior.

Tolerance Rule

Treat balances as matched if:

abs(difference_amount_cents) <= 1

Store tolerance on the log row.

Error Handling

If a reconciliation cannot be completed:

store a log row with status = error

include diagnostic notes/meta

do not throw away the failure silently

do not break existing accounting jobs

Examples:

missing Stripe Holding account mapping

missing QBO credentials

failed QBO account balance lookup

invalid shop configuration

ShopNLTees-specific requirements

Implement in the ShopNLTees accounting architecture using the current Stripe/QBO setup already in place.

Use the existing shop-scoped accounting settings and mappings.

Must work with current concepts already present in the app, including:

Stripe payout sync

daily sales receipt flow

Stripe fee recording

refund / reversal handling where already implemented

existing QBO account mappings / sync records

Do not change the existing posting flow.

buy-dtf.com-specific requirements

Add the same reconciliation feature to buy-dtf.com.

Assume accounting flow is intentionally the same:

Stripe Holding clearing account

sales to Stripe Holding

fees against Stripe Holding

payouts transferred to bank

bank feed matches transfer

Reuse as much of the service/logic design as practical, but adapt to the buy-dtf.com codebase structure.

Do not assume table names are identical between the two apps. Inspect the current accounting models first.

Suggested implementation order
Phase 1 — Discovery

Codex should inspect the current accounting implementation and identify:

table(s) for posted daily sales receipts

table(s) for Stripe fee sync records

table(s) for refund / reversal sync records

table(s) for payout transfer sync records

where Stripe Holding account mapping is stored

whether QBO account balance fetch helper already exists

Document findings briefly before coding.

Phase 2 — Service

Build the reconciliation service and unit-testable computation logic.

Phase 3 — Persistence

Add the reconciliation log table and save results.

Phase 4 — Console command

Add nightly / on-demand command.

Phase 5 — Admin UI

Add list/detail/re-run UI.

Phase 6 — Dashboard warnings

Add mismatch summary badge/widget.

Definition of Done

This feature is done when:

Running the command for a correctly synced shop produces:

expected holding = actual holding

status = balanced

If a payout transfer is artificially missing in test data, reconciliation shows:

non-zero difference

status = mismatch

Admin UI shows recent runs and status clearly

Re-run button works without creating any accounting transactions

No current accounting posting behavior changed

Both ShopNLTees and buy-dtf.com have this feature implemented in their own codebases

Testing requirements

Codex must add or run tests where practical.

At minimum validate:

Case 1 — Normal balanced flow

sales receipt + fee + payout

expected = actual = 0 after payout

Case 2 — Pre-payout balance

sales receipt + fee but no payout yet

expected holding equals current net Stripe balance

Case 3 — Missing payout transfer

expected and actual differ

status mismatch

Case 4 — Refund included

refund reduces expected holding correctly

Case 5 — Missing configuration

status error with useful notes

Use cents in assertions.

UI notes

Keep styling consistent with each app’s existing admin design.

For tables:

compact

sortable if easy

status badges

timestamps

clearly labeled amounts

Do not do

Do not:

rewrite Stripe sync

rewrite QBO posting

change transfer behavior

change sales receipt logic

auto-fix mismatches

create hidden accounting adjustments

This feature is only:

calculate

compare

log

display

alert

Final expected result

After implementation, each site should have:

A nightly reconciliation check

Admin visibility into whether Stripe Holding is balanced

A manual re-run option

A safe way to catch accounting sync problems early without touching the current logic

Short version for Codex

Build a read-only Stripe/QBO reconciliation layer for both ShopNLTees and buy-dtf.com that:

computes expected Stripe Holding balance from existing posted records

compares it to actual QBO Stripe Holding balance

logs the result

exposes admin UI + re-run

adds a nightly command

does not modify existing accounting behavior
