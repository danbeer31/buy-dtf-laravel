# Transparency source-only scheduler correction: local review plan

This operations-only replacement is based on `b3d4b009b1b99d2cc6b9e7f3a641d341956d1849`.
It preserves the eleven application members and the accepted Laravel 12.69.1
dependency envelope. The branch remains local and unpushed. This packet grants
no production, staging, cutover, recovery, finalization, or capability authority.

The failed runner `25da4ddef0b4eb088cdedadf4848b1286a389760942493717e52d00f02c014df`
and release receipt `5621e1aad4c25bbffa5fad0f858358458595491b6a83c28ec8fc543aa6dd3f2d`
are permanently rejected by the new runner. The retained release
`b02fce32-20261004T234125Z`, its inputs, rollback evidence, and all earlier
partial releases must remain untouched. Future actions use a fresh v4 release,
new control identities, and separate evidence-bound authorizations.

## Confirmed cause and correction

Accepted sample 19, generated `2026-10-05T00:20:11Z`, observed the existing QBO
admin-cache refresh overlap mutex. Independent review confirmed that the task
logged success at `00:20:12Z` and its mutex subsequently cleared. The v3 runtime
validator required zero overlap mutexes in every phase. It consequently treated
ordinary scheduled work as a deployment failure and correctly invoked rollback.

The replacement preserves idle requirements through source installation and
candidate checks. After reopening, and while verifying rollback or recovery,
it admits only the pinned QBO task's bounded activity. It does not change the
schedule, accounting command, cache lifetime, application, images, or dependencies.
It neither disables cron nor runs, acquires, clears, releases, or expires a task
mutex. The operations observer reads existing file/database records directly;
Laravel's mutex `exists()` can acquire/release a lock and is no longer used.

The proposed policy is frozen in the reviewed control, with these exact bounds:

| Invariant | Requirement |
| --- | --- |
| Event inventory | Exact three commands, expressions, timezone, background and overlap attributes |
| Allowed task | `qbo:refresh-admin-cache`, `*/10 * * * *`, UTC, background, `withoutOverlapping(15)` |
| Command identity | `5e5f803d8dcc65662d6a731cff510c28b61dece97d429bbf4f949099f7c9f5fd` |
| Mutex identity | `a086c96c5fd6e5ba9e3e47ba418706400ad8928e2ea406688628a505d26b3eff` |
| Start window | First 15 seconds of the ten-minute slot |
| Activity bound | 120 seconds, independently checked from the existing mutex expiry and durable monotonic observations |
| Mutex lifetime | Existing 900-second application setting; never changed or cleared |
| Completion | Healthy cache status, bounded success timestamp, mutex release within five seconds of success |
| Active follow-up | Every five seconds, with runtime, health where open, source, dependency, configuration and log-continuity checks |
| Observation continuity | At most 90 seconds between accepted observations; no backward clock/status movement or unexplained wall/monotonic divergence |
| Process identity | Exact PHP executable, QBO arguments, application cwd, approved site UID, start slot and age; no process environments read |
| Dispatcher/finish | Brief QBO-only dispatcher or exact successful mutex finish only; reject Stripe/accounting/other Artisan work, unsuccessful finish and shared due slots |

The 120-second bound is a conservative deployment acceptance limit for review,
not a new application timeout. The accepted incident demonstrates completion
one second after the failed probe; the new expiry/status fields in regression
inputs are explicitly synthetic because the old helper did not capture them.
The native Windows PHP 8.2.30 observer proof validates cache semantics. Its
command/mutex path formatting is platform-specific; the production policy uses
the accepted Unix identities, also checked with the real Laravel classes in WSL.

## Complete validation-call review

| Call or phase | Scheduler policy |
| --- | --- |
| Phase 0 memory guard and complete preflight | Strict idle, exact event/source/mutex inventory and healthy recent status |
| Phase 1 before/after construction | Strict idle; bind scheduler identity and policy into the release receipt |
| Cutover preflight | Strict idle; require the current identity to equal the staged identity |
| Final under-gate check before source mutation | Strict idle, unchanged source/dependencies/schema/ledger and zero existing non-null `item_meta` |
| Candidate CLI/runtime checks under the gate | Strict idle |
| Post-open health | Bounded QBO only, durable private receipts; settle observed work before passing |
| Every monitor sample and active follow-up | Bounded QBO only, all existing non-scheduler invariants retained |
| Monitor close | Fresh complete runtime/health/source/dependency/configuration checks; settle final activity before acceptance |
| Source rollback schema check/comparison | Bounded QBO only; restore source before runtime/scheduler validation |
| Rollback post-open health | Same bounded policy and completion checks, with original source identity |
| Interrupted recovery | Same boot-independent restore, durable gate controls and scheduler state; lost/malformed continuity fails closed |
| Final receipt | Fresh monitor-close verification, replacing the stale post-open snapshot |

All other runtime checks remain in the same validator: PHP 8.2.30, Laravel
12.69.1, Imagick, non-authoritative class map, exact Fuel connection, installed
schema and 21-row ledger, nullable TEXT metadata, empty incoming-order tables,
empty queues, disabled capabilities and empty artwork hosts. The source CAS,
mode-sensitive dependencies, configuration, health and complete-entry log parser
are retained. The parser additionally rejects the QBO refresh's explicit failure
message, even if a later success obscures an intermediate cache-status failure.
The reviewed 56 benign diagnostics remain nonfatal; exceptions, traces, fatal
errors, SQLSTATE, missing classes/views, severe levels, candidate failures,
invalid UTF-8 and unparsed/orphan log data remain fatal.

## Future staging and deployment sequence

1. Independent code/evidence review must accept this exact local commit and
   hashes. A separate authorization is required before pushing or production
   access. A restricted stage must use a reviewed input transfer containing
   the new scheduler Python/PHP controls as well as all existing frozen files;
   the old v3 uploader/input slot and release cannot stand in for this package.
2. Under fresh restricted-stage authority, verify remote tip/clean worktree and
   all controls; rerun complete read-only Phase 0. Require current source/front
   controller/configuration/service/nginx/FPM/dependency identities, exact
   schema `5485779bdcf0ea3a4372410ef76cd0bc418d1f6400128868606e901b8e9e85da`,
   ledger 21 / `f1140209ad897fbdba506d87329f9e4481ccfa5aff7fb6a423e6ec7a0dbe5f53`,
   migration entries exactly once, zero pre-install non-null metadata, empty
   incoming-order tables/queues, disabled capabilities, empty artwork hosts,
   inactive maintenance/gate and free deployment locks. Scheduling must be idle.
   Use accepted nginx evidence plus the unchanged read-only eighteen-file
   verifier. Do not recreate nginx sudo permission. Stop on inaccessible or
   changed evidence; never relax the gate.
3. Create a fresh private source release. Verify all eleven raw-byte application
   members, PHP lint, controls, the new runtime observer and policy. Capture the
   exact scheduler/cache definition identity in the release receipt and recheck
   the immutable live envelope afterward. Stop for independent stage review.
4. A separate cutover authorization must name that fresh receipt, its hash,
   commit and runner. Repeat strict preflight and verified backups. Keep all
   scheduler idle/drain requirements before source mutation. Install the same
   reviewed static gate, durable transitions, full seven-second monotonic
   OPcache waits, two cache-busted origin responses and public response.
   Repeat schema/ledger, source/dependency, idle and exact-zero metadata checks
   under the gate before the eleven-member source-only installation.
5. Run the existing CLI/FPM checks and original-front restoration through the
   full reviewed wait. Require exact original front identity and health. Permit
   only bounded reviewed QBO work after reopening. Cron remains enabled; do not
   schedule a rollout across an unapproved Stripe/accounting due-work window.
6. Run all thirty sixty-second monitoring intervals. Active work is additionally
   followed every five seconds until verified completion, extending elapsed
   time rather than shortening the thirty-minute monitor. Every observation
   and acquisition/completion/release transition is persisted privately at
   mode 0600. Preserve rotation-safe raw logs privately and redacted analyses
   for review. New customer metadata may grow legitimately after installation.
   Close with a fresh full check and a cleared, successfully completed task.
   Stop at `awaiting_independent_log_review`; do not finalize or create a review
   receipt on behalf of an independent reviewer.

No migration, pretend, reverse, SQL restore, dependency/cache exchange, source
outside the eleven members, service restart, configuration/sudo change, cron
change, mutex clearing, manual accounting task, retention, deletion, capability
enablement, artwork-host addition, customer-artwork or ShopNLTees action is part
of this sequence. Preserve original artwork and all accepted derived-image,
Saved Image, preview, legacy and separate incoming-image policies unchanged.

## Rollback and recovery

Before mutation, use the unchanged exact-front restoration and health receipt.
After mutation, retain/reassert the exact gate, use the frozen FPM emergency
envelope where necessary, complete the monotonic wait, and restore original
source bytes/metadata boot-independently before runtime validation. HTTP gate
verification failure never prevents this source restore. Laravel 12.69.1 lock,
vendor and cache remain untouched; preserve schema, ledger, metadata and all
customer data. A normal QBO task may complete naturally during verification,
under the same bounds and without any mutex action. Restore the original front
only after source/schema/dependency/scheduler checks pass, then repeat bounded
post-open verification. Unexpected, stuck, failed or unprovable work keeps the
site contained with the original source restored; do not report a healthy
completed rollback when verification fails. Interrupted recovery uses the exact
reviewed durable state and separate recovery authority, never ad hoc path swaps.

The accepted dependency rollback set and earlier transparency pre-freeze
commit `3db18d1fff3f599299eecd2aae21b9102fc45540` remain untouched. That historical
commit retains `DEPENDENCY_ENVELOPE_FROZEN = False`. All raw evidence stays
private; this packet includes only redacted or synthetic summaries and hashes.
