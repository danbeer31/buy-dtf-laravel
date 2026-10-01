# Production alpha repair render evidence

This evidence reproduces the confirmed cart bug and compares it with the
derived-only repair at alpha threshold 128.

## Reproduction

The source contains alpha values `0`, `32`, `96`, `160`, and `255`. The old
Imagick call supplied `128 / 255` directly to `EVALUATE_THRESHOLD`. On the
active Q16 build, Imagick expects a value in the `0..65535` QuantumRange, so
that level is approximately `0.502`, not the intended midpoint. Every nonzero
source alpha therefore became fully opaque. The buggy result has an 11x11
visible square.

The fixed production derivative converts the 8-bit threshold to QuantumRange,
maps alpha below 128 to zero and alpha at or above 128 to 255, and then crops
the newly transparent perimeter. Its visible result is 7x7. The source file is
never written. Imagick and GD produce the same normalized RGBA SHA-256:
`9f7b54ff696720fb8b1cf8b1c58928649ac5037c62d1c9a0edc0154fb1511981`.

All raw source/before/after PNGs report 300 PPI (11,811 pixels per meter).
`comparison.png` uses a common 20 display pixels per source pixel, rather than
auto-fitting each panel, so the incorrect and corrected visible bounds remain
visually comparable.

## Reproduction command

From the repository root in the approved WSL PHP environment:

```text
php ops/evidence/production-alpha-transparency-20261001/render_evidence.php
cd ops/evidence/production-alpha-transparency-20261001
sha256sum -c SHA256SUMS
```

The renderer removes only the volatile PNG `tIME` chunk from generated
evidence. Running it twice with a delay must produce identical PNG hashes.
Detailed dimensions, alpha sets, normalized pixel hashes, bounds, and DPI are
recorded in `metrics.json`.
