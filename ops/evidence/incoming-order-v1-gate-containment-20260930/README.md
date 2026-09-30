# Incoming-order v1 phase-aware gate containment correction

Date: 2026-09-30 (America/Chicago)

Status: local correction and rehearsal complete; **NO-GO for production staging or deployment pending independent review**.

Production was not accessed. The failed-operation evidence, retired runner, receiver target, staged release, live application, database, services, configuration, capabilities, ShopNLTees, and retention state were not changed.

## Corrected artifacts

- Base commit: `a67a7e6276afe1407c20b31db4e21e6cc13decb0`.
- Receiver target remains `0799440b7cbb0bad364fc2a65b41285f20245658`.
- Permanently retired runner remains `2a7bf3966c593532af1e22db0f03d8cec1c6aecfde0902629b9f2328016c1138` and must not be retried.
- Corrected runner SHA-256: `53723435a2d56d2736746a5a6d1e98fddeda660acbcf3a45f57b662b06b4adfd`.
- Rehearsal script SHA-256: `c3b2e2b79986650a6d27625ae18372057d987ac61eebf42e8a08fb6d40232e5d`.
- Rehearsal receipt SHA-256: `063a006ac173baf789bb0d1dd9da859f9805b3ef63a0906e2ec7382a08b6adfa`.
- Rehearsal canonical payload SHA-256: `5308f0303d56ef7529f1928c350cbe8aa9a25c037de3257ba0cf1e6565c8836c`.
- Extracted later-phase failure receipts SHA-256: `56095d4dcc3c183ee3d7fb9cc1e199faed598c980f2d0a88384d8a567cc8df4c`.

## Safety correction

The gate now has two separately identified checks: a direct loopback origin request that bypasses Cloudflare and a public Cloudflare request. A response is accepted only when its route identity, HTTP `503`, reviewed header, and reviewed body sentinel all match.

Before either schema migration or source installation starts, a gate failure atomically restores the exact original front controller and records both the restoration receipt and a normal post-restoration health result. After either durable mutation flag is true, a gate failure instead retains or reinstalls the exact reviewed gate with UID/GID `1000`, mode `0644`, durable gated state, and a containment receipt. It cannot restore the original over partially changed application code.

Rollback begins through the explicit `establish_rollback_containment()` path. The later-phase injected failure sets both `migration_executed=true` and `source_install_started=true`, passes the local/origin check, fails the public check, and ends with:

- exact gate SHA-256 `94bc83db8df1d6a18fc74575adbb89d3d9176e58474d951926eff96019c89c03`;
- reviewed owner and mode `0644`;
- `static_gate_active=true` and `containment_active=true`;
- no automatic original-restoration receipt.

## Local rehearsal and tests

The Linux rehearsal ran only in disposable WSL `/tmp` paths, as root so it could set the reviewed application owner and execute/read as separate UID/GID `33`, and under `umask 077`. All eight scenarios passed. The aggregate receipt embeds every per-scenario receipt payload and hash. The later-phase receipts are also extracted into a smaller review file.

- Python compilation: pass.
- Runner `--describe`: pass.
- Gate rehearsal: 8/8 pass; every final identity is either the exact original or the exact fail-closed gate.
- PHPUnit: 170 tests, 1,099 assertions, one existing Imagick-dependent skip.
- Composer validation: pass.
- npm production audit: zero vulnerabilities.
- Vite production build: pass, 112 modules; existing Sass deprecation warnings remain.
- Composer production audit on the receiver branch: expected failure for four newly published advisories affecting Laravel, CommonMark, and Flysystem.

The advisories are addressed separately by dependency-only commit `c07c29332adcc9fa41f2c3b4f14bf6f35cf28c3c`, based on the exact current production lock. That branch is not merged, staged, or deployed by this correction.

## Raw evidence hashes

- `raw-phpunit.txt`: `cc6c2b76057101f1ad5c7d153d0db06107d419bffb3a257c83169144cf10a5b2`.
- `raw-runner-validation.txt`: `b297512e170a2b97bb2675a01e1df9e51fa66a9e2971b5532502cf1626268942`.
- `raw-composer-validation-audit.txt`: `42087a6c63a3a15a28de601a1de39a5d11a8ab31d3beb708e682b80dc1af1370`.
- `raw-frontend-validation.txt`: `ae0a1cf7d5764c6f836947a0a1f03611c317519b48309322defdd5accc02fc2c`.

## Explicit non-actions

- no production access or production evidence changes;
- no staging, deployment, migration, maintenance, or source installation;
- no dependency cutover, service restart, or configuration/cache change;
- no capability or artwork-host enablement;
- no ShopNLTees change;
- no retention, purge, or customer-deletion action.
