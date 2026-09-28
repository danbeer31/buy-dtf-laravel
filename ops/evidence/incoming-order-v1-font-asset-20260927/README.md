# Incoming-order v1 immutable font correction evidence

This directory records the local-only correction prepared after the 2026-09-27 Phase 0 font-identity stop. It does not record a new production preflight or staging run.

The exact reviewed DejaVu Sans file is now a versioned application asset beside its license notice. Renderer `separate-job-card-v2` ignores configuration or environment attempts to replace its path, hash, or version. The deployment manifest treats the font and license as new source files, and the runner verifies their absence before deployment, their exact identities in the candidate, and renderer readiness after install.

The original Phase 0 stop receipt remains unchanged at `../incoming-order-v1-phase0-20260927/preflight-receipt.json`. The real render evidence remains at `../incoming-order-v1-job-card-v2/` and retains the independently expected image hashes.

No production access, staging, migration, deployment, maintenance, restart, configuration change, capability enablement, ShopNLTees change, or retention action occurred while producing this correction evidence.
