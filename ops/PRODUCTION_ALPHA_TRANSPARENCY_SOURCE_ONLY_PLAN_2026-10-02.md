# Production alpha transparency source-only replacement plan

Status: artifact commit c43f39f556d057c99bb01e95ee7ca68658c05232 is
permanently NO-GO. Do not stage or deploy it. Corrected v2 mechanics are under
pre-freeze review on branch
fix/production-alpha-transparency-source-only-v2-20261002. Final packaging is
blocked until the separately deployed Laravel 12.69.1 dependency envelope can
be frozen from production.

Independent review label: rollback review

Independent review SHA-256:
bbfd8079f73f5196ee4e519fbdee523058e0d843f375cb369fafe90c327fa760

## Historical replacement authority (revoked)

The migration-running runner with SHA-256
76cfff204e86ee1119251b1d79931b1219cd19704b099f75d4e3db202ffe5b17
is permanently retired. No receipt, approval, or prior rehearsal may make that
runner eligible again.

The following values describe the rejected c43f39f artifact only. They have no
staging or deployment authority, and every approval token previously emitted
for that artifact is revoked. Its application target was commit
b02fce3213fc632891036f1b5c98b9cddb94e499. The historical candidate archive has
SHA-256
3067bca578201a39254d8544b633a04ff6a9e43fc0de2a2783a95ccde9a1bfcd.
The historical application manifest has SHA-256
93bc5ff1427693539faabda97d7fc1b9b8a5bca8075dea7bec5cb17d75a7faf2.

The archive contains exactly eleven source paths: ten replacements and the
already-recorded migration source as one absent-to-present addition. Installing
the migration source records the deployed application version; it does not
authorize executing, pretending, or reversing the migration.

The three added replacement paths correct checkout and Shippo diagnostics:

1. app/Http/Controllers/Checkout/CheckoutController.php
2. app/Services/ShippoService.php
3. app/Http/Controllers/Webhooks/ShippoWebhookController.php

The normal diagnostic calls changed by application commit b02fce use debug,
info, or warning levels. Those changed calls no longer log direct customer
addresses, complete checkout requests, complete Shippo responses, complete
carrier messages, webhook payloads, tracking numbers, or customer email
addresses. Failure calls changed by that commit retain bounded identifiers and
exception type/code where useful, without copying exception messages.

## Mandatory installed state

Every stage and deployment boundary must require all of these exact values:

- schema SHA-256
  5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da;
- migration-ledger row count 21;
- migration-ledger SHA-256
  f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53;
- exactly one ledger entry named
  2026_10_01_120000_add_item_meta_to_savedimages_table;
- savedimages.item_meta present as nullable TEXT, with no default or generated
  expression;
- the reviewed identities for the schema without item_meta and the ledger
  without the target row;
- source compare-and-swap SHA-256
  0ceca182384a8e68560ec542c0c2c0c695971b8488321ca0899ea7a880d6fd17;
- receiver, job-label, and retention capabilities false, with an empty artwork
  host allowlist;
- queues and failed jobs idle, locks free, and health checks green;
- the approved Composer lock, vendor, Laravel cache, and front-controller
  identities unchanged.

Any schema or ledger mismatch is a hard stop. The runner must never invoke a
migration command, migration pretend, migration reversal, database restore, or
schema mutation. Source rollback verifies the exact installed schema and ledger
and does not mutate, delete, dump, or restore customer rows.

## Log monitoring rule

Monitoring parses complete Laravel entries, including multiline continuations
and orphaned trace fragments. The literal .ERROR level is metadata and does not
fail a candidate by itself.

The monitor requires an existing nonempty baseline log. The baseline, every
60-second sample, and the final delta require the same inode, no size
regression, and an unchanged hashed tail anchor. Rotation, truncation, or anchor
rewrite is a hard-stop rollback because log continuity cannot be proven.

Rollback remains mandatory for exception or Throwable/Error classes, structured
exception-type fields, stack traces, fatal or uncaught errors, SQLSTATE,
missing classes/interfaces/traits/views, candidate-related failures, and
failure-level entries whose messages say error, failed, or failure. Receipts
store hashes, counts, and signal classes without copying log messages.

The private reviewed source delta remains outside Git. Its SHA-256 is
81e429a215856b401d74a361c86a37453e65047af6faf3802127b04f61100a08.
The committed redacted regression fixture represents the reviewed 56 legacy
error entries as two reconstructed 28-entry diagnostic sequences. It contains
no customer address or full carrier payload and must remain nonfatal.
Genuine-error fixtures must continue to fail the monitor and exercise source
rollback.

## Phase 0: read-only revalidation

Phase 0 requires independent approval of this exact branch and artifact set.
It performs read-only inspection only:

1. Verify runner, manifest, archive, runtime-probe, and log-guard hashes.
2. Reject the retired runner, retired release receipt, or any mismatched target
   commit.
3. Record raw bytes, hash, owner, and mode for all ten existing live paths and
   prove that the migration source path is absent.
4. Require the exact installed schema and 21-row ledger above.
5. Verify dependency/cache/front-controller identities, disabled capabilities,
   empty artwork hosts, locks, queues, maintenance state, and health.
6. Stop on any difference and emit only redacted receipt data.

Phase 0 performs no Git operation, live-source write, cache command, service
action, or database mutation. Its database access is limited to the reviewed
read-only schema, ledger, queue, and capability queries.

## Phase 1: private source-only staging

Phase 1 requires separate staging authorization after independent review. It
must not alter live source.

1. Create a new private release directory with restrictive permissions.
2. Extract exactly the eleven reviewed paths from the frozen archive.
3. Verify each target byte count and SHA-256 against the manifest, then run PHP
   syntax checks on every candidate PHP file.
4. Copy and hash the reviewed runner, runtime probe, and Laravel log guard.
5. Repeat the complete Phase 0 check. Require the installed schema and ledger
   to be unchanged.
6. Repeat live-source read-only runtime and health probes; staged candidate
   execution begins only during an authorized cutover. Independent review
   cross-references the separately frozen local test and rehearsal evidence;
   those artifacts are not embedded in the live staging receipt.
7. Emit a redacted staging receipt that records exact artifact identities,
   commands, schema/ledger identities, source CAS, and health results.
8. Stop for independent review of the staging receipt.

The stage must record all three migration flags as false and a migration-command
count of zero.

## Phase 2: controlled source cutover

Phase 2 requires explicit deployment authorization for the independently
accepted Phase 1 receipt.

1. Revalidate the immutable release and repeat every hard-stop check.
2. Back up the exact ten existing live source files, prove the migration source
   was absent, and back up the original front controller. Hash and verify every
   backup before mutation.
3. Install and verify the reviewed static gate.
4. Under the gate, recheck source CAS and the exact installed schema/ledger.
5. Atomically install only the eleven reviewed source files. Run no migration,
   Composer, npm, cache-clear, service-restart, retention, or deletion command.
6. Verify installed source identities, PHP syntax, the reviewed alpha/FPM
   runtime probes, application health, capabilities, queues, and exact
   schema/ledger identities. Checkout and Shippo behavior is covered by the
   frozen local regression tests and by parsed production logs during the
   monitor; the cutover does not submit a synthetic checkout or carrier request.
7. Restore the original front controller only after all candidate checks pass.
8. Run the reviewed public HTTP, runtime, capability, queue, and schema checks,
   followed by the full 30-minute parsed-log monitor.

Any failure after source mutation starts restoration of the exact original
source and front controller. A successful rollback verifies raw identities and
health before reopening. If restoration or its verification fails, the runner
retains or reinstalls the exact static gate, persists containment state, and
requires reviewed recovery. Rollback never reverses the migration, drops
item_meta, creates or restores a database dump, or deletes customer data.

## Scope exclusions

This plan makes no ShopNLTees, dependency, configuration, incoming-order,
job-label, retention, customer-deletion, or customer-artwork mutation. Receiver,
job-label, and retention capabilities remain disabled, and the artwork-host
allowlist remains empty.
