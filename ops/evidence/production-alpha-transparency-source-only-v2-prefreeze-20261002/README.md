# Transparency source-only v2 corrections: pre-freeze review

Status: corrections prepared for independent review. Staging and deployment
are disabled. This directory is not a final deployment package.

The full handoff `buy-dtf-codie-handoff-2026-10-02.md` was verified at
SHA-256
`ba9fd4dcf5fa5854b2e23418e0cd6ed8799874494a0341c726302b92a5acc127`.
Artifact commit `c43f39f556d057c99bb01e95ee7ca68658c05232` and its runner SHA-256
`59bbd90cafa8d1b5efd56a6c40667924193e37539f4340e4b6163c6274425cab`
are permanently rejected.

The corrected pre-freeze manifest has SHA-256
`01731f42b8b241ebb55a310f55e6bd20d67729c60a37ea126f5c2ce0804ed32d`.
It embeds the same handoff identity and declares itself non-stageable and
non-deployable while the production dependency freeze is pending.

Current pre-freeze code identities are:

- runner: `c42f076e9810df8722773806ceac051e9b6e63b1e7ae9139f480bc34f8144841`;
- parser: `4bdec766469e71568631dbcf7408e94696f2fd99c46c18dd58b8374f31a488c8`;
- rehearsal: `1b9a676ac652e2fea6c30fae96b21e072cf77ac51217a3f48d9da2078107c2cd`;
- describe receipt: `13ec71f689e1276a8004b5305ed1216c8c4399d0cc08ab523cf96d2f163c0e85`.

These are correction-review identities. Every one must be regenerated after
the separate Laravel 12.69.1 production cutover.

## Corrections available for review

- The Laravel log parser now treats `CRITICAL`, `ALERT`, and `EMERGENCY` as
  unconditional rollback signals. Invalid UTF-8 and every nonempty orphan or
  otherwise unparsed entry also fail closed. Header-shaped lines with unknown
  levels cannot hide as continuations of a prior entry.
- A log baseline ending mid-entry retains bounded context back to the most
  recent Laravel header. The later delta reparses the complete crossing entry.
  A partial baseline without a reconstructable header is rejected.
- Staging preflight requires zero non-null `savedimages.item_meta` values. The
  same condition is checked again under the static gate immediately before
  source installation. Post-cutover health, monitoring, and rollback preserve
  the schema while allowing legitimate new uploads to populate the column.
- The corrected manifest records 795 CRLF pairs and 102 remaining bare LF
  bytes for the live `CheckoutController.php`. Its authoritative raw SHA-256
  and 44,433-byte count are unchanged.

The reviewed 56-entry redacted benign fixture still passes. Existing genuine
exception, trace, fatal, SQLSTATE, missing-class, missing-view, and candidate
failure fixtures still fail. Focused tests add the five handoff cases and the
baseline-boundary behavior.

## Dependency-envelope gate

The runner intentionally has
`DEPENDENCY_ENVELOPE_FROZEN = False`. Both stage and deploy entry points stop
before reading or creating deployment artifacts. Values shown by `--describe`
are explicitly labeled historical pre-upgrade values.
Stage, deploy, and recovery approval tokens are withheld from `--describe`
until the post-upgrade envelope is frozen.

After Laravel 12.69.1 is deployed and monitored through its separate repair,
the following work remains mandatory:

1. Read the exact production Composer lock, vendor tree, bootstrap-cache tree,
   `packages.php`, `services.php`, PHP/Laravel runtime, and front-controller
   identities without changing production.
2. Replace every historical dependency value in the runner, set the freeze
   status to the reviewed post-upgrade identity, and only then enable the
   envelope flag.
3. Recompute the manifest, parser, runner, archive, describe, rehearsal, and
   checksum identities.
4. Repeat all parser and runner tests, all seven source-only rehearsal
   scenarios, the applicable PHP suite, Composer validation and audit,
   frontend audit and build, and deterministic render checks.
5. Return the resulting evidence for another independent review. Do not stage
   or deploy without later authorization.

The source archive may remain byte-identical to application commit
`b02fce3213fc632891036f1b5c98b9cddb94e499` if the post-upgrade validation
passes. No migration, ShopNLTees, retention, customer-deletion, or
customer-artwork change is included. Receiver, job-label, retention, and
artwork-host capabilities remain disabled.
