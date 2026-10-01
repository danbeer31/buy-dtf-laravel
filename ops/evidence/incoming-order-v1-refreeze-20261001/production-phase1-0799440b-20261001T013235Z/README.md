# Production Phase 0/1 evidence

The re-frozen receiver artifact completed only the authorized read-only preflight, restricted release staging, candidate verification/lint, and absolute staged-path `--realpath --pretend` migration check.

- Release: `/var/www/buy-dtf/storage/app/private/operations/incoming-order-v1-releases/0799440b-20261001T013235Z`
- Release receipt: `e08e969c97065cc7e387acbcf5544355b6270e55b095d4d9fa5d8bf06e33a9ed`
- Phase 0 preflight: `ccce56f438a315c75c0c345be2ab5ca0a2a317dcdbf52ad5b40d1ccb862309ff`
- Migration pretend: `66f090e924a92279692a0766d026a664fdc92c03a3a3e4a657ff100c1e1f524a`
- Evidence manifest: `c6beb3d2c11dfbe470ae51fa1dfce31aca100479181a3cbdb8210940645decbc`
- Phase 1 completion: `c5533a9010e1e5e2873de0d9d92a41b450608f9dc541a92252347b68182298e5`

The schema and Fuel migration ledger fingerprints were identical before and after pretend. Production source, dependencies, cache, configuration, front controller, schema, ledger, services, capabilities, ShopNLTees, retention, and customer deletion were not changed. No Phase 2 backup exists, maintenance/static gating was never entered, and all locks were free after the runner stopped.
