# Incoming-order v1 schema-present resume evidence

Date: 2026-09-30 America/Chicago (2026-10-01 UTC)

Status: local correction and rehearsal passed. The subsequently authorized
Phase 0 read-only production preflight and Phase 1 restricted private sibling
staging also passed. Live source, schema, dependencies, configuration, caches,
front controller, services, queues, capabilities, and public health remained
unchanged.

The new runner treats the additive incoming-order schema left by the failed
cutover as immutable production baseline. It requires schema
`4f199033…`, the 20-row ledger `3168a7da…`, one target migration entry,
both target tables present and empty, the exact target definitions and
indexes, and restored source CAS `9c0b0818…`. It contains no migration
execution or pretend path.

Runner SHA-256:
`c97f4250742dadc8af0a00632f856b120c8f3ec6425e81b647c261f47d56692d`.

Local verification completed:

- 10 installed-schema/refusal regressions passed using the exact retained
  post-migration fixture. The `ascii_bin_columns` proof is now a deterministic
  JSON-safe list.
- Five resume scenarios passed: success plus injected failures before source
  installation, during installation, during candidate checks, and after
  reopening. Every failure completed source rollback to `9c0b0818…` while
  preserving the installed schema and ledger.
- All eight static-gate scenarios passed under `umask 077`, including the
  separate UID/GID `33` reader and later-phase fail-closed containment.
- The receiver suite passed against the exact live Composer lock in the
  disposable dependency-baseline worktree: 170 tests, 1,099 assertions, and
  one expected Windows no-Imagick skip.
- Composer validation passed; `composer audit --locked --no-dev` reported zero
  advisories; npm production audit reported zero vulnerabilities.
- Vite built 112 modules successfully. Existing Sass deprecation warnings are
  retained in the raw stderr evidence.
- Linux-native WSL/Imagick renders reproduced the reviewed normal and
  maximum-field PNG hashes (`fa4d42b3…` and `cadf92ae…`) at 1500x900 and
  approximately 300 DPI using the pinned font `ae7b7855…`.
- Exact PHP version and extension lists for the PHP 8.2 test runtime and PHP
  8.3/Imagick render runtime are included.

The feature worktree intentionally retains the older application lock because
the receiver payload remains exact commit `0799440b…`; it is not the basis of
the dependency audit. The authoritative audit/test worktree contains lock
`22af12c7…` and Laravel 12.69.0, CommonMark 2.10.2, Flysystem 3.35.3, and
Flysystem Local 3.35.3, matching the successful dependency cutover.

`resume-rehearsal-artifacts.tar.gz` retains every per-scenario durable state,
source backup/install/rollback receipt, installed-schema verification, and
event log. `resume-rehearsal-receipt.json` provides their complete hash
inventory. Empty stderr files are retained as successful no-error evidence.

The new private sibling release is
`0799440b-resume-20261001T034232Z`. Its release receipt SHA-256 is
`446d077ad837d3552e37deda28ccb84f5f06fa311a9a645e643fb151392215b9`;
its 54-entry evidence-manifest SHA-256 is
`197000b5c0de233c42c991cfc232ca7474fe346ecb17070da447fb1dfa175ba0`;
and its Phase 1 completion receipt SHA-256 is
`64002162a93916b37cd10b03b3c86adfc121073ea800dd70b5e1110744d5a7e6`.
The complete downloaded release copy and production pre/post probes are
retained beside this README for independent review. The SHA-256 manifest for
the 20 production preflight/staging envelope files is
`43bad59fc1a434a35ad81a9953d222f4279954c4b3425e877d4af3e9433ba36a`.

No Phase 2 backup, gate installation, maintenance, migration command or
pretend, live-source change, service restart, capability enablement,
ShopNLTees change, retention action, or customer deletion occurred. Work is
stopped after Phase 1 for independent review.
