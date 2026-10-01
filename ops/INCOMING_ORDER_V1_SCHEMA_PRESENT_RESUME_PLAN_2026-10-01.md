# Incoming-order v1 schema-present resume plan

Date: 2026-09-30 America/Chicago (2026-10-01 UTC)

Status: restricted staging candidate only. This document does not authorize a
receiver cutover, maintenance, a live-source change, or any migration command.

## Authoritative baseline

The failed receiver attempt completed the reviewed additive migration before
the source installation failed. Automatic source rollback completed and the
installed schema is now the production source of truth:

- receiver source target: `0799440b7cbb0bad364fc2a65b41285f20245658`;
- original 37-path source CAS:
  `9c0b081853feed397cc61be4b7b6d7c302df2298a87cca30e69e80f067cda6db`;
- Fuel schema SHA-256:
  `4f1990336946bde95c6a13d0245fe4a5845eff2f23999f62e8529478d95d51ed`;
- Fuel migration ledger: 20 rows, SHA-256
  `3168a7da9ca4aad0a81e673ec61c1647242916d054768f4dd48ff4b9d7eb28d4`;
- target migration ledger entries: exactly one;
- `incoming_order_jobs` and `api_asset_records`: both present and empty;
- target table-definition SHA-256:
  `aa0a038110dc355ffcd0ed12768c2adb7b0954ecbcc9aeb0fc4ef0efb5d287dc`;
- Composer lock SHA-256:
  `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`;
- vendor manifest SHA-256:
  `7399949f857da190c5ff07b89c85e8fba8a6f681695e20a462862be591b698ed`;
- bootstrap-cache manifest SHA-256:
  `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9`.

The runner records this state as `installed_schema_resume_v1`. It refuses any
schema, ledger, table-definition, index, row-count, source, dependency,
capability, artwork-host, queue, lock, or health drift.

## Permanently retired artifacts

The following runners and release receipts are explicit hard stops and cannot
be staged, deployed, or recovered with the resume runner:

- runner `2a7bf3966c593532af1e22db0f03d8cec1c6aecfde0902629b9f2328016c1138`;
- runner `569f8aec08b8493d1544a9c1c84b0dca2e0efd74cd8385091cbff13796c6119c`;
- receipt `0ae00bbbf5a3fbccc2e69d1318ed17896d4b33ea107f716059018eab710af184`;
- receipt `e08e969c97065cc7e387acbcf5544355b6270e55b095d4d9fa5d8bf06e33a9ed`;
- release directories `0799440b-20260928T020518Z` and
  `0799440b-20261001T013235Z`.

All failed-attempt evidence remains retained and unchanged.

## New artifact identities

- runner: `ops/deployment/incoming_order_v1_deploy.py`;
- runner SHA-256:
  `c97f4250742dadc8af0a00632f856b120c8f3ec6425e81b647c261f47d56692d`;
- runtime archive SHA-256:
  `ed1df143d219fa073efb2707508c3eb81ba17b777597cebc20a72d3c546522c2`;
- 37-path manifest SHA-256:
  `b6efbd5463c82f895ca8d359b665a145d88c0d363ce7f97b247eae9080853bb6`;
- runtime helper SHA-256:
  `1b37d3a38834ef633cee5caa784d909b2f5be41ae6e22766f817f80f9f4a20bd`;
- migration source-file SHA-256:
  `79fa911b0b2ad9bb79c33080725446093dffd4df3e01c3cb3888d508087c9f9d`.

The migration file is only verified as one of the reviewed source paths. The
resume runner contains no migration execution or pretend path. Every receipt
records:

- `migration_command_invoked=false`;
- `migration_pretend_invoked=false`;
- `migration_executed_this_attempt=false`.

## Authorized restricted staging sequence

1. Run the hard-stop in-memory preflight before creating a sibling release.
2. Require the exact old 37-path source CAS, live dependency/cache identities,
   original front controller, free locks, no conflicting process, healthy
   endpoints, disabled receiver/job-label/retention capabilities, an empty
   artwork allowlist, and empty queues.
3. Require the exact installed schema, ledger, target definitions, reviewed
   indexes, one migration entry, and zero target rows.
4. Create a new private sibling named `0799440b-resume-<UTC timestamp>`.
5. Copy and hash the frozen archive, manifest, helper, and this exact runner.
6. Extract and verify the 37 candidate paths, immutable font/license, planned
   file metadata, and PHP syntax.
7. Run a second read-only runtime probe and prove the installed schema and
   ledger did not change. Do not invoke Artisan migration in any form.
8. Recheck live source, dependencies, health, gate/maintenance state, and
   locks; write the release receipt, evidence manifest, and completion receipt.
9. Stop for independent review.

Restricted staging must not create Phase 2 backups, install the static gate,
enter Laravel maintenance, modify live source, configuration, dependencies, or
cache, restart a service, enable a capability, change ShopNLTees, or execute
retention/customer deletion.

## Separately reviewed future cutover behavior

A later, separately authorized cutover may create reviewed backups, install the
exact mode-`0644` static gate, enter maintenance, and install the 37 source
paths. It must re-prove the installed schema under the gate before source
mutation and must not execute or pretend the migration.

Pre-source-mutation gate failures restore and health-check the exact original
front controller. Once `source_install_started=true` is durable, any gate
verification failure retains the exact gate. Automatic rollback restores the
original 37-path source CAS while requiring the installed schema and migration
ledger to remain exact; it never removes or rolls back the additive schema.

All receiver, job-label, and retention capabilities remain disabled, and the
artwork-host allowlist remains empty. Physical job-card enablement is still a
separate print-review gate.
