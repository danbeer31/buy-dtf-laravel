# Stripe Payout `notes` Execution Artifact

Status: **prepared and locally verified; not copied to or executed on production**

Scope: add only the nullable `stripe_payout_entries.notes` column through the single reviewed migration. General `php artisan migrate`, migration discovery, schema consolidation, and any other pending migration are prohibited.

## Reviewed Files and Hashes

| File | SHA-256 |
|---|---|
| `database/migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php` | `6bdd43d63d2427af19a2fb65afd1b295b12759ac916d2803d245de2c6f7c1e0c` |
| `ops/deployment/payout_notes_runtime.php` | `04918419f9b085fcbe0eb35294fc6ec58ca1eaacbfd95bb8a8a9e73aa8f60cae` |
| `ops/deployment/payout_notes_correction.py` | `80f99eee566a2fc212a17ba34dc55c94db47c6816abe49deca9d78a55cae98b2` |

The migration is deliberately connection-bound. Laravel's migrator must make `fuelmysql` active, and that active name must equal `database.fuel_connection`; otherwise `up()` and `down()` fail before any schema query. Pretend mode emits only the proposed DDL because the execution runner separately proves the table exists and the column is absent.

## Fixed Preconditions

The artifact stops unless all of these are true:

- It runs as the application owner, never root, against the real non-symlink `/var/www/buy-dtf` path.
- The migration and runtime-helper hashes match the table above.
- Effective `database.fuel_connection` is exactly `fuelmysql`, its driver is MySQL, and the connected server is MySQL 8.0.x.
- `stripe_payout_entries` exists, `notes` is absent, both payout-table row counts are readable, and this exact migration is absent from the Fuel migration ledger.
- No `stripe:sync-payouts` or identifiable payout-webhook job process is active.
- The public home, health, and login routes return 200; `/admin` and `/checkout` return the expected unauthenticated 302.

The precheck is repeated after backup and preview. Any schema, ledger, row-count, connection, or process change stops execution before the migration.

## Backup and Preview

Execution creates a mode-0700 run directory below:

```text
/var/www/buy-dtf/storage/app/private/operations/payout-notes/<UTC timestamp>/
```

Before preview or migration it:

1. Resolves the audited Fuel credentials through the booted Laravel connection.
2. Writes them only to a new mode-0600 temporary MySQL option file; no password appears in an argument, receipt, or console output.
3. Uses MySQL 8 `mysqldump` with `--single-transaction`, `--quick`, `--skip-lock-tables`, `--hex-blob`, and only `stripe_payouts` plus `stripe_payout_entries`.
4. Compresses the dump, verifies gzip integrity, verifies both table definitions and the dump-completion marker, records its size/SHA-256, and deletes the temporary credential/raw-dump files.
5. Runs only:

```text
php artisan migrate \
  --database=fuelmysql \
  --path=database/migrations/2026_09_18_120000_add_notes_to_stripe_payout_entries_table.php \
  --pretend --force --no-interaction --no-ansi
```

The runner parses that output and requires exactly one `ALTER TABLE stripe_payout_entries ... ADD notes TEXT` statement. Any drop, delete, update, insert, truncate, rename, second alteration, or different table/column stops execution.

## Future Reviewed Execution

These steps are instructions for a separately approved maintenance window. They have **not** been run.

1. Place the exact Python/PHP artifact pair in an access-restricted private operations bundle. Copy only the reviewed migration to its exact application path. Verify all three hashes independently.
2. Run the non-mutating artifact check:

```text
python3 payout_notes_correction.py \
  --self-check \
  --repo-root /var/www/buy-dtf
```

3. Run the read-only production preflight and retain its output for the operator review:

```text
python3 payout_notes_correction.py --preflight
```

4. Confirm no payout sync is running, the latest row count is plausible, the site baseline is healthy, and the window is approved.
5. Execute only the frozen artifact:

```text
python3 payout_notes_correction.py \
  --execute \
  --approval-token APPLY-STRIPE-PAYOUT-NOTES-6bdd43d63d2427af
```

There is no command or option in this artifact that runs unrestricted migrations.

## Verification and Receipts

After the exact migration command, the runner requires:

- `notes` exists as nullable `TEXT`;
- the exact Fuel-ledger entry count is one;
- `stripe_payouts` and `stripe_payout_entries` row counts are unchanged;
- public health matches the pre-execution baseline.

The restricted run directory retains:

- verified compressed two-table backup;
- validated `--pretend` output;
- exact migration output;
- `execution-receipt.json` with before/after schema hashes, counts, artifact hashes, output hashes, and health statuses;
- `rollback-receipt.json` with the backup hash and approved rollback policy.

Receipts contain no database password, customer data, raw payout rows, webhook payload, or credential value.

## Rollback Policy

The safe rollback is to retain the additive nullable column and, if necessary, roll application code back separately. The migration's `down()` intentionally leaves the column in place.

The runner never automatically restores the payout tables: doing so could overwrite payouts written after the backup. A table restore is an incident procedure requiring separate approval, stopped payout writes, verification of the recorded gzip/SHA-256, and reconciliation of any post-backup activity. Failure receipts preserve the last completed stage and backup identity for that review.

## Current Decision

Targeted payout repair: **ready for independent artifact review; NO-GO for production execution until that review issues a separate approval and a window is selected.**
