# Validation receipt

Date: 2026-10-02 (America/Chicago)

## Results

- Complete PHPUnit run: 191 tests, 1,959 assertions, PASS in 11:29.087.
- Checkout and Shippo focused matrix: 14 tests, 255 assertions, PASS.
- Laravel log guard and source-only runner unit suites: 32 tests, PASS.
- Disposable native-Linux rehearsal: 7 of 7 scenarios, PASS.
- Failure scenarios: pre-source, source-swap, candidate-check, post-reopen,
  genuine-log, and schema-preserving rollback all restored exact expected-live
  source and the original front controller.
- Every rehearsal scenario retained installed_schema_source_only_v1, recorded
  zero migration commands, and left all migration flags false.
- Genuine-log rehearsal used the pinned parser and caused source rollback.
  Success used the redacted 56-entry nonfatal fixture.
- Log continuity tests reject rename rotation, size truncation, and
  copytruncate/regrow anchor replacement.
- Monitor scheduling test proves 30 complete 60-second intervals plus a final
  continuity check. The disposable rehearsal does not wait 30 wall-clock
  minutes.
- Python bytecode compilation: runner, rehearsal, and parser, PASS.
- PHP syntax: all eleven candidate files plus the runtime probe, PASS.
- composer validate --strict: PASS.
- npm audit --omit=dev --audit-level=high: zero vulnerabilities.
- npm run build: PASS. Existing Sass deprecation and stale Browserslist-data
  warnings remain.
- git diff --check: PASS.

## Dependency audit boundary

The historical repository composer.lock has SHA-256
eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831.
On 2026-10-02, composer audit --locked reports four advisories across its
Laravel 12.61.1, league/commonmark 2.10.0, and league/flysystem 3.30.2
generation, including one high-severity CommonMark advisory.

This task does not change dependencies. The source-only runner rejects any
dependency operation and requires the independently reviewed live Composer
lock SHA-256
22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9
plus its exact vendor and Laravel cache identities. The historical-lock audit
result is disclosed here and is not represented as a clean audit.

## Rehearsal identity

The final portable rehearsal receipt has SHA-256
eaae0f811642b2dba8a0639a0f4cfa5239ee5522395e7a76c999edcbcd0e8e47.
Its portable manifest has SHA-256
3de3ec6df09df29014a2db2ca149f54968866c5ea737eb47db24aae3cee72b82.
The private raw rehearsal tree remains outside Git; the portable receipts
contain hashes and bounded status data only.

## Safety assertions

- No production staging, source deployment, migration, pretend, reverse,
  database dump, dependency change, cache change, service restart, retention
  action, customer deletion, or ShopNLTees change was performed.
- A read-only live identity check supplied raw hashes and byte counts for the
  three added logging paths. It made no production write.
- Receiver, job-label, and retention capabilities remain disabled in the
  runner invariant, and the artwork-host allowlist must remain empty.
- The candidate archive and private reviewed log source remain ignored private
  artifacts and are not committed.
