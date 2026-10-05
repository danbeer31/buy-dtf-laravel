# Transparency scheduler timezone and startup correction: local review plan

This operations-only replacement is based on rejected review commit
`8678872c337f1e1c56347a16329b4d0a212281ce`. It preserves all eleven application
members, original artwork, schema and the accepted Laravel 12.69.1 dependency
envelope. It remains local and unpushed. This document grants no production,
stage, cutover, recovery, finalization, configuration or capability authority.

The rejected v4 runner `880d6ec6cb1ca5cee95964cf48843384afbaaeb73e835d03850e32de92aa21ab`
joins permanently retired runner
`25da4ddef0b4eb088cdedadf4848b1286a389760942493717e52d00f02c014df`.
The failed release receipt
`5621e1aad4c25bbffa5fad0f858358458595491b6a83c28ec8fc543aa6dd3f2d`
and all earlier releases, inputs and rollback evidence remain untouched and
ineligible for reuse. Preserve the prior v4 review packet byte-for-byte.

## Review findings and corrected controls

The accepted incident at sample 19 still describes ordinary QBO activity:
the probe ran at `2026-10-05T00:20:11Z`, success followed at `00:20:12Z`, and
the overlap mutex cleared. The first correction incorrectly required UTC text
and UTC schedules. The actual status writer emits Chicago timestamps such as
`2026-10-04T19:20:12-05:00`, using `now()->toIso8601String()`. The application
configuration defaults to `America/Chicago` and the three scheduled events
inherit that timezone. Neither the production timezone nor cache is changed.

The observer now strictly parses explicit RFC3339 offsets, validates calendar
dates and normalizes only its returned copy to UTC. Naive timestamps, invalid
dates/times/offsets, unknown `-00:00`, trailing bytes and unsupported precision
fail closed. Integer UTC epochs drive state comparisons. The returned inventory
binds the application timezone, PHP default timezone and all event timezones to
`America/Chicago`. Timestamp text need not use that particular offset: any valid
explicit offset represents an absolute instant and is normalized consistently.

Due-work checks convert absolute instants through the IANA Chicago timezone.
They evaluate the actual hourly Stripe, daily 01:30 accounting and ten-minute
QBO expressions in local time. They distinguish summer/winter offsets and both
fall DST folds; they never attach Chicago to a naive time or assume a constant
UTC offset. Dispatcher acceptance still requires QBO to be the only due task.

Laravel acquires the overlap mutex before the worker calls `markAttempt()`.
After reopening, an exact fresh scheduled mutex with the previous healthy,
completed status may enter a durable startup state. It cannot do so before
source mutation: all idle gates remain strict.

| Invariant | Frozen requirement |
| --- | --- |
| Task/inventory | Exact pinned QBO command and source; exact three-event inventory |
| Schedule | `*/10 * * * *`, `America/Chicago`, background, `withoutOverlapping(15)` |
| Mutex | Exact reviewed name/owner/expiry; existing 900-second lifetime unchanged |
| Acquisition slot | First 15 seconds of the actual local ten-minute slot |
| Startup | At most 10 seconds from mutex acquisition, requiring unchanged previous healthy completion until progress |
| Progress | `markAttempt()` timestamp within the original ten-second bound; or a successful completion within that bound |
| Activity | At most 120 seconds from mutex acquisition, plus independent durable monotonic checks |
| Release | Mutex released within five seconds of success; success must belong to this attempt |
| Active observation | Every one second while starting, then every five seconds while running/completing; never run a task or change its mutex |
| Continuity | At most 90 seconds between accepted observations; no clock/status regression or unexplained wall/monotonic divergence |
| Processes | Exact executable, arguments, cwd, UID and age; worker launch bound to the verified acquisition plus ten seconds; only a brief QBO-only dispatcher or exact successful finish |

The startup deadline uses the existing mutex expiry minus 900 seconds and its
remaining grace at first observation. It is persisted once and never renewed.
State records startup, running and completion-before-release separately, with
attempt/completion epochs and lock identity. A recovered snapshot can prove a
previous timely attempt from its timestamp, but cannot grant another startup
window. Late/unproven progress, release without success, identity changes,
regression, unexpected work, failure/deferment, or lost continuity fail closed.
If startup was observed, a later completion beyond its deadline cannot substitute
for missing timely progress evidence. All bounds remain subject to independent
review; they do not change application timeouts or scheduling.

The production observer reads existing FileStore/DatabaseStore records directly.
It never calls mutex `exists()`, runs commands, expires values, or acquires or
releases a scheduler lock. Reads preserve original cache bytes. Private durable
state and observation/rejection receipts remain mode 0600; only redacted or
synthetic evidence is committed.

## Validation-call review

| Call/phase | Scheduler policy |
| --- | --- |
| Phase 0 memory guard and complete preflight | Strict idle, exact inventory/timezones/source and healthy recent completion |
| Phase 1 before/after construction | Strict idle; freeze scheduler identity and policy in the release receipt |
| Cutover preflight and final under-gate check | Strict idle; staged/current identity equal; zero pre-existing non-null `item_meta` |
| Candidate CLI/runtime checks under the gate | Strict idle |
| Post-open health | Bounded reviewed startup/running/completion only, followed to verified release |
| Every monitor sample and active follow-up | Same durable policy; all non-scheduler checks retained |
| Monitor close | Fresh complete runtime/health/source/dependency/configuration check and verified completion/release |
| Rollback schema comparison and verification | Same bounded policy, after boot-independent original source restoration |
| Rollback post-open health | Same bounded policy with original source identity |
| Interrupted recovery | Same persisted deadline/progress/history; no grace or continuity reset |
| Final receipt | Fresh monitor-close verification; independent log-review gate still required |

PHP 8.2.30, Laravel 12.69.1, Imagick, dependencies, source CAS, configuration,
services, front controller, installed schema, 21-row ledger, queue and failed-job
counts, incoming tables and disabled capabilities keep their existing controls.
The complete-entry log parser still rejects QBO failures and all reviewed genuine
error categories, severe levels, invalid UTF-8 and orphan/unparsed data. The
reviewed 56 benign entries remain nonfatal. Legitimate metadata growth is allowed
after source installation; rollback never erases customer data or metadata.

## Local proof and evidence

Integration uses the unchanged `QboAdminSnapshotStore` methods and real Laravel
mutex acquisition and framework finish in new disposable caches. It executes no
QBO/accounting command, API request or business query. The real writer produces
summer `-05:00` and winter `-06:00` statuses, and the actual observer normalizes
them without changing cache bytes. The lifecycle is observed before attempt,
after attempt, after success and after framework release.

Real Laravel scheduling-expression checks independently agree with the Python
Chicago due-work decisions across summer, winter, the spring gap and both fall
folds. An absolute-instant test date factory avoids ambiguous-wall-time mock
reparsing for the fold tests; this exists only in the disposable integration
process. Offset parsing also distinguishes the two fall-fold instants.

WSL's PHP binary differs from production's `/usr/bin/php8.2`. The Python integration
projects only that binary path in test inventory after verifying all other actual
inventory fields and the unchanged real Unix mutex name. Live validation never
projects or relaxes identities. Native PHP 8.2.30 separately repeats observer,
writer and lifecycle semantics; its Windows command/mutex path formatting is
documented as platform-specific, not a production Unix identity proof.

The runner/control, monitoring, gate, rollback/recovery, nginx/database-envelope
and complete-entry parser suites are repeated. Source rehearsals exercise normal
startup during automatic rollback and interrupted recovery. Monitoring rehearsals
exercise startup after open, at sample 19, at monitor close and in winter, plus
late/stuck/orphaned/failing startup and every retained failure category. Rehearsals
use disposable paths, virtual monitor clocks and mocked external endpoints/SQL;
they do not claim fresh production validation. Prior application, Composer, npm
and image-render evidence remains retained because those bytes did not change.

## Future authorized sequence

1. Independent review must accept the replacement commit and exact hashes.
   Pushing, production read access and a restricted stage need separate authority.
   The old runner, input slot, uploader assumptions and release cannot be reused.
2. A freshly authorized Phase 0 must verify remote tip/clean worktree, every
   control and current source/front/configuration/service/nginx/FPM/dependency
   identity. Require the unchanged eighteen-file nginx inventory, index socket
   and document root, FPM envelope and complete seven-second OPcache policy.
   Do not recreate nginx sudo permission; stop on unavailable or changed proof.
3. Require installed schema
   `5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da`,
   ledger 21 / `f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53`,
   exact migration entries, nullable TEXT `item_meta`, zero pre-install non-null
   values, empty incoming tables/queues, disabled receiver/job-label/retention,
   empty artwork hosts, no gate/maintenance, free deployment locks and idle
   scheduling. Verify actual Chicago inventory and normalized status without
   changing configuration or cache. Any mismatch rejects release creation.
4. Create a fresh private v5 source release containing the same eleven members
   and the replacement operations controls. Verify raw bytes, lint and receipts;
   bind scheduler timezone/identity/policy into the receipt. Prove live immutability
   and stop for independent stage review.
5. Separate cutover authority must bind that fresh receipt, commit and runner.
   Repeat preflight/backups, keep scheduling idle, install the unchanged reviewed
   gate with durable transitions and full monotonic OPcache waits, verify both
   origin probes and public route, drain, and repeat zero-metadata/schema/ledger/
   source/dependency/idle checks before the source-only installation.
6. After candidate checks and exact original-front restoration through the full
   wait, use the bounded Chicago QBO policy in post-open health and monitoring.
   Keep cron enabled and avoid an unapproved hourly/daily due-work window. Follow
   observed startup every second and running work every five seconds with all other invariants intact.
   Thirty sixty-second intervals remain mandatory; follow-ups extend elapsed time.
   Capture rotation-safe logs privately and perform complete-entry parsing.
7. Finish with fresh health/runtime/source/dependency/configuration checks and a
   successful released task. Stop at `awaiting_independent_log_review`; finalization
   requires separate evidence-bound independent review and authorization.

## Failure and recovery

Keep the reviewed v4 gate safety primitive unchanged: durable state, exact bytes
and metadata, full monotonic revalidation wait, current strict FPM probe before
mutation and frozen-envelope emergency containment afterward. Before mutation,
restore the exact original front controller and verify health. After mutation,
retain/reassert the gate and restore original source boot-independently even when
HTTP gate verification fails. Then verify schema/data/dependencies and the same
durable scheduler policy. Normal startup may progress naturally; never manipulate
its task or mutex. Unexpected, unprovable or failing work keeps the site contained
with original source restored. Reopen only after verification, through the full
gate restoration wait and bounded post-open checks. Interrupted recovery requires
its exact state and separate authorization; no manual exchanges or retries.

No migrations/pretend/reversal, database restore, dependency/cache replacement,
configuration/timezone/sudo change, service restart, cron disablement, production
mutex action, accounting task execution, capability enablement, artwork-host
addition, ShopNLTees, retention, deletion or customer-artwork action is included.
The historical pre-freeze transparency commit
`3db18d1fff3f599299eecd2aae21b9102fc45540` and its false dependency-envelope gate
remain untouched. This packet stops at local independent review.
