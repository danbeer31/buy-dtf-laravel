# Production alpha source-only replacement evidence

Status: PERMANENTLY RETIRED / NO-GO. Artifact commit
c43f39f556d057c99bb01e95ee7ca68658c05232 and runner SHA-256
59bbd90cafa8d1b5efd56a6c40667924193e37539f4340e4b6163c6274425cab
must never be staged or deployed. This directory is retained only as rejected
audit history. No hash, token, receipt, or command recorded here has authority.

The application target is
b02fce3213fc632891036f1b5c98b9cddb94e499. It combines the reviewed
transparency repair with bounded checkout and Shippo logging. The deployment
artifact is built from base
307b99e9429ca4623c72cc121e12997bdb4dfcad.

The rollback review supplied by the user is pinned as SHA-256
bbfd8079f73f5196ee4e519fbdee523058e0d843f375cb369fafe90c327fa760.
Runner 76cfff204e86ee1119251b1d79931b1219cd19704b099f75d4e3db202ffe5b17
and its prior release receipt are permanently rejected.

## Historical rejected behavior

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
- RUNNER_DESCRIBE.json preserves rejected historical describe data and is
  explicitly marked permanently retired.
- LOCAL_REHEARSAL_PACKAGE_RECEIPT.json preserves rejected historical package
  identities and carries no staging or deployment authority.
- deployment-rehearsal contains the redacted aggregate and seven scenario
  receipts. Raw backups, logs, and disposable filesystem state remain outside
  Git.
- ORIGINAL_C43_SHA256SUMS preserves the checksum list issued with the rejected
  c43f39f artifact for audit history only. SHA256SUMS covers the current
  retirement-marked directory, including that original list, and excludes only
  SHA256SUMS itself.

The private reviewed log delta remains outside Git. Its SHA-256 is
81e429a215856b401d74a361c86a37453e65047af6faf3802127b04f61100a08.
The committed fixture represents its 56 reviewed error entries as two
reconstructed and redacted 28-entry diagnostic sequences. It contains no
customer address, order identifier, postal code, or full carrier payload.

The rejected historical staging and cutover sequence is retained in
ops/PRODUCTION_ALPHA_TRANSPARENCY_SOURCE_ONLY_PLAN_2026-10-02.md. Phase 1
and Phase 2 are both revoked and must not be run.
