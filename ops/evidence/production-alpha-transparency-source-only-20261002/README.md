# Production alpha source-only replacement evidence

Status: prepared for independent review. Nothing in this package authorizes
staging or deployment.

The application target is
b02fce3213fc632891036f1b5c98b9cddb94e499. It combines the reviewed
transparency repair with bounded checkout and Shippo logging. The deployment
artifact is built from base
307b99e9429ca4623c72cc121e12997bdb4dfcad.

The rollback review supplied by the user is pinned as SHA-256
bbfd8079f73f5196ee4e519fbdee523058e0d843f375cb369fafe90c327fa760.
Runner 76cfff204e86ee1119251b1d79931b1219cd19704b099f75d4e3db202ffe5b17
and its prior release receipt are permanently rejected.

## Reviewed behavior

The new runner requires the already-installed schema with SHA-256
5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da
and exactly 21 migration-ledger rows with SHA-256
f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53.
The target migration entry must occur exactly once and item_meta must be a
nullable TEXT column. Any mismatch stops before source mutation.

The runner installs source only. It has no migration, pretend, reverse,
database-dump, dependency-install, cache-clear, Git, retention, or customer-row
mutation path. Source rollback verifies the same installed schema and ledger
without dumping, restoring, comparing, or deleting customer rows.

The candidate contains eleven source paths: ten replacements and one reviewed
absent-to-present migration source file. The migration source is installed only
to make the live code tree complete; it is never executed or reversed.

Normal checkout and Shippo diagnostic calls changed by the application commit
now use debug, info, or warning levels. Those calls omit direct customer
addresses, complete checkout requests, complete Shippo or carrier payloads,
tracking numbers, and customer email addresses. Changed failure calls retain
bounded identifiers and exception type/code without copying exception messages.

The monitor parses complete Laravel entries instead of treating the literal
.ERROR level as a failure. It still rolls back for exceptions, structured
exception types, traces, fatal or uncaught errors, SQLSTATE, missing classes or
views, candidate failures, and failure-level messages containing error, failed,
or failure. It requires a nonempty log plus continuous inode, size, and hashed
tail-anchor identity at every 60-second sample. Rotation, truncation, or rewrite
fails closed.

## Evidence layout

- APPLICATION_MANIFEST.json contains authoritative raw expected-live and target
  identities for all eleven paths.
- RUNNER_DESCRIBE.json is the byte-for-byte output of the frozen runner describe
  mode.
- LOCAL_REHEARSAL_PACKAGE_RECEIPT.json indexes the frozen private archive,
  runner, parser, schema, ledger, test, and rehearsal identities.
- deployment-rehearsal contains the redacted aggregate and seven scenario
  receipts. Raw backups, logs, and disposable filesystem state remain outside
  Git.
- SHA256SUMS covers every committed file in this evidence directory other than
  SHA256SUMS itself.

The private reviewed log delta remains outside Git. Its SHA-256 is
81e429a215856b401d74a361c86a37453e65047af6faf3802127b04f61100a08.
The committed fixture represents its 56 reviewed error entries as two
reconstructed and redacted 28-entry diagnostic sequences. It contains no
customer address, order identifier, postal code, or full carrier payload.

The proposed staging and cutover sequence is in
ops/PRODUCTION_ALPHA_TRANSPARENCY_SOURCE_ONLY_PLAN_2026-10-02.md. Phase 1
creates a private source-only release and stops for independent receipt review.
Phase 2 remains separately authorized and was not run.
