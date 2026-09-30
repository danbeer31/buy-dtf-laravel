# Incoming-order v1 front-controller gate correction

Date: 2026-09-30 (America/Chicago)

Status: local correction and rehearsal complete; **NO-GO for staging or deployment pending independent review**.

The failed production-operation evidence at `/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-rollbacks/0799440b-20260930T220235Z` was not accessed or changed during this work. Production was not accessed.

## Frozen local artifacts

- Receiver target remains `0799440b7cbb0bad364fc2a65b41285f20245658`.
- Permanently retired runner: `2a7bf3966c593532af1e22db0f03d8cec1c6aecfde0902629b9f2328016c1138`.
- Corrected runner: `ops/deployment/incoming_order_v1_deploy.py`.
- Corrected runner SHA-256: `61607104b81470af9cf8b5505f9ec6ae04cb67653474aa726b0b2d712097fb5f`.
- Rehearsal script: `ops/deployment/rehearse_incoming_order_v1_gate.py`.
- Rehearsal script SHA-256: `f43f84352a1a972d70120ed7a3528924e770ba01e9ac06b3d1f1ab5dd13b44e2`.
- Rehearsal receipt: `ops/evidence/incoming-order-v1-gate-correction-20260930/rehearsal-receipt.json`.
- Rehearsal receipt SHA-256: `6d8c03d382f3bafea293cff5c3ebff7c4a3db3fabeada652747a0babc9e744b5`.
- Rehearsal canonical payload SHA-256: `b8d44252d71db1b46063313212c4a0e38780416c993ae0a72b8538f2d5b43b57`.
- Validation receipt: `ops/evidence/incoming-order-v1-gate-correction-20260930/validation-receipt.json`.
- Validation receipt SHA-256: `cde8568af9ca08df5b9a063c918595d794dfb72705fd1ed1aaf467a073a14968`.

## Correction mapping

1. The gate is explicitly assigned UID `1000`, GID `1000`, and mode `0644`, then its bytes and metadata are verified before `os.replace`.
2. A durable `replacement_pending` state is written and fsynced before replacement.
3. A durable `installed` state is written immediately after replacement and directory fsync, before HTTP verification.
4. Initial gate failure restores the exact retained original through the same atomic transition primitive and writes exact-restoration plus gate-failure receipts.
5. Recovery checks the actual front-controller SHA-256 and validates durable transition history. `static_gate_active` is retained for reporting but is not the recovery decision authority.
6. Cutover, rollback, failure containment, candidate reopening, and rollback reopening use the corrected primitive.
7. Preflight now requires the reviewed front-controller owner and `0644` mode in addition to its SHA-256.

## Local rehearsal

The rehearsal ran as root only inside WSL disposable `/tmp` paths so it could create the reviewed UID/GID `1000` owner and drop a separate reader/executor to UID/GID `33`. It ran with process `umask 077`; every disposable path was removed afterward.

All seven scenarios passed and ended on the byte-exact original front controller:

- successful gate and reopen under `umask 077`;
- injected failure before replacement;
- injected failure after replacement and durable installed state;
- failed verification after a successful separate-identity read;
- recovery from the historical live gate bytes with mode `0600`;
- recovery from durable pending state plus actual live gate bytes while the boolean was stale;
- later-phase rollback gating and reopen.

The UID/GID `33` reader and PHP process read/executed the `0644` gate. A separate `0600` negative control was denied. Exact per-scenario transition, state, event, restoration, and failure-receipt hashes are recorded in `rehearsal-receipt.json`.

## Validation results

- Python compilation: pass for runner and rehearsal script.
- Runner `--describe`: pass.
- `git diff --check`: pass.
- PHPUnit: 170 tests, 1,099 assertions, 1 existing Imagick-dependent skip.
- Composer validation: pass.
- npm production audit: zero vulnerabilities.
- Vite production build: pass, 112 modules; existing Sass deprecation warnings remain.
- Composer production audit: **blocked/failed due four newly published advisories affecting three locked packages**:
  - Laravel framework below 12.69.0: low severity, `CVE-2026-102279` / `GHSA-jh5r-qr3c-85q8`;
  - league/commonmark through 2.10.1: medium `GHSA-97jj-33gv-5xf9` and high `GHSA-3q6v-r5mr-hxv8`;
  - league/flysystem through 3.35.2: low `CVE-2026-102601` / `GHSA-cxf4-7mrp-vvpr`.

The advisory result is a separate deployment blocker. No dependency was changed because this authorization was limited to the gate correction and local rehearsal.

## Explicit non-actions

- no production access;
- no staging or release receipt creation;
- no migration or database access;
- no source deployment or service restart;
- no capability or artwork-host enablement;
- no ShopNLTees change;
- no retention or customer-deletion action.
