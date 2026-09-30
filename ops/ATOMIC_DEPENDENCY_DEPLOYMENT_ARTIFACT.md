# Atomic Dependency Deployment Artifact v2

Date: 2026-09-30 (America/Chicago)

Status: **re-frozen for the four-package security candidate; rehearsal and staging do not authorize cutover**.

This artifact starts from the dependency state successfully deployed on 2026-09-19. It keeps the reviewed v2 atomic vendor/cache exchange and boot-independent static maintenance gate. It changes no application source, configuration, database schema, assets, or services.

## Exact identities

| Item | SHA-256 |
|---|---|
| Deployment runner | `9a8d130eeee5b9aab1cbe89632a9357af6dcdcb8bbd1b484b6d2fdf7f0ce56be` |
| Runtime helper | `16e1f7cf814112120eb71afa3385dd0ae5251dac85e5407d88ed0b639bc93cb0` |
| Candidate `composer.lock` | `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9` |
| Production `composer.json` to retain | `7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872` |
| Production `composer.lock` to retain for rollback | `eeac4637272ca2b9aeaa797a4440cfc8b4e31f5a469619c46ebfa5791c701831` |
| Production `vendor/` manifest to retain for rollback | `97cd0bb104c42b57fbf90204ee74837ec1359b0ab1cbf8dac7d6929a154922d7` |
| Production runtime-source manifest | `46f6a1ffa03364b550395c89111a0d69a844d1379f3c5aba6ed5c1e17616abca` |
| Production bootstrap-cache manifest observed at preparation | `468c3eadd5d92b7c13024ab613ebb5ad986015359ef3181adee51892a3110ac9` |
| Production database configuration | `d25ab83243dc255e43ddbaa856991dae93016dd8ff77fa11be20d222693bb8f9` |
| Production front controller | `eba77cba39695b6bd091fe5211d481f7ebb2ce2d8d26230b5a609465d0a4aff9` |
| Embedded static maintenance gate | `94bc83db8df1d6a18fc74575adbb89d3d9176e58474d951926eff96019c89c03` |

The dependency-only candidate is commit `c07c29332adcc9fa41f2c3b4f14bf6f35cf28c3c`. Its lock was produced from the exact production Composer JSON with `--with-dependencies --minimal-changes`. It updates only:

| Package | Live | Candidate |
|---|---:|---:|
| `laravel/framework` | `12.61.1` | `12.69.0` |
| `league/commonmark` | `2.10.0` | `2.10.2` |
| `league/flysystem` | `3.30.2` | `3.35.3` |
| `league/flysystem-local` | `3.30.2` | `3.35.3` |

Guzzle remains `7.15.2`. Production installation remains `--no-dev`; Laravel Pail and every other development package are rejected.

## Read-only production preflight

The runner has a distinct read-only mode:

```text
python3 atomic_dependency_deploy.py \
  --preflight \
  --candidate-lock /absolute/reviewed/bundle/composer.lock
```

It verifies the exact candidate lock, live Composer files, source manifest, vendor manifest, bootstrap cache, database configuration, front controller and metadata, application owner, PHP and Composer toolchain, maintenance state, deployment-lock availability, scoped Artisan/payout processes, HTTP health matrix, application environment, debug state, queue state, all five runtime package identities and install paths, and the complete loaded PHP extension list. It emits JSON to standard output and writes nothing.

## Restricted staging

The exact staging token is:

```text
STAGE-BUYDTF-DEPS-22af12c7e58fcfe8
```

The stage command is:

```text
python3 atomic_dependency_deploy.py \
  --stage \
  --candidate-lock /absolute/reviewed/bundle/composer.lock \
  --approval-token STAGE-BUYDTF-DEPS-22af12c7e58fcfe8
```

Staging re-runs the full preflight while holding the scoped dependency-operation lock, then creates a new restricted sibling release directory. It runs Composer strict validation, locked production audit, `composer install --no-dev --prefer-dist --optimize-autoloader --no-scripts`, platform checks, shadow package discovery, and shadow route discovery. The receipt freezes the command-output hashes, candidate vendor manifest, candidate bootstrap-cache identity, retained live vendor/cache/front-controller identities, full preflight, package versions, PHP extension list, and exact runner/helper hashes.

Staging does not enter maintenance and does not change the live vendor, Composer files, bootstrap cache, application source, front controller, configuration, database, or service state.

## Atomic rehearsal and cutover boundary

The disposable rehearsal exercises 23 scenarios with real `renameat2(RENAME_EXCHANGE)` calls: stale dev cache replacement, both between-exchange failure windows, an unbootable candidate, every cutover interruption, boot-independent recovery, every rollback interruption, stale gate state, and rollback-health failure containment.

The reviewed cutover mechanism remains available in the runner but is **not authorized by rehearsal or staging**. Any future cutover requires independent approval of the exact new release receipt, vendor/cache identities, command receipts, and runner/helper hashes. Its token would be `DEPLOY-BUYDTF-DEPS-22af12c7e58fcfe8`; it must not be used without that separate approval.

Recovery is pinned to the retained live lock with token `RECOVER-BUYDTF-DEPS-eeac4637272ca2b9`. Cutover and recovery retain the old vendor, exact old cache, lock, and front-controller evidence. They never run Git, migrations, `composer update`, source/config deployment, or service restarts.

## Scope exclusions

This artifact does not stage or deploy the incoming-order receiver, run migrations, enable capabilities, change ShopNLTees, run retention, or run customer deletion. The approved receiver gate commit `33337116556c28ce217869f74f66936b48a276ff` remains a separate future deployment line. When that receiver is re-frozen, its `--describe` output must explicitly distinguish pre-mutation restoration of the original front controller from post-mutation retention of the exact static gate.
