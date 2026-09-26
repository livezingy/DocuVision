# Case Study: Catching a Silent Coordinate Bug in an OCR Pipeline

> As of 2026-09-25 · All numbers cross-checked against [CHANGELOG.md](../../CHANGELOG.md) (P-020 / P-021).

## TL;DR

- A measurement harness built on born-digital PDF text layers — no hand labeling — exposed that OCR result polygons were silently off the uploaded image's pixel frame.
- Root cause was one engine preprocessing default. The fix is one init parameter, locked by contract tests that fail if it is flipped or deleted.
- After the fix: 12 of 15 fixture/degradation combos improved, 0 regressed; recovered text volume reached 2.1×; two independent cloud runs reproduce byte-identically.

## What was going wrong

An OCR endpoint returned text-line polygons for every uploaded page. Consumers overlaid them on the image, cropped regions, and exported annotations. Nothing crashed, confidence scores looked normal, and the text itself was fine.

A calibration check said otherwise. Eight synthetic probes, with exact known ink positions, measured how the returned polygons related to the input frame. Scale drifted between 1.1084 and 1.2257, varying per probe, and the similarity fit left residuals of 9.9–51.6 px. Rotation was silently flattened too: a 3° input came back with a −0.82° residual, a 15° input with −2.80°.

The failure mode is what made it dangerous. Every overlay, crop, and export built on those boxes was quietly misplaced, while every human-facing signal still said healthy. Only a geometric probe against known ground truth could see it.

## How we measured it — without hand-labeled ground truth

We used the born-digital text layer of PDF fixtures as weak ground truth. Word-level boxes come straight from the file, so no human labeling is involved. We do not claim this ground truth is absolutely accurate; it serves relative comparison only.

Each fixture was rendered clean and again under a degradation ladder: rotated 3°, then 15°. A character-level scoring family — match rate, three CER variants, reading-order LCS — plus geometric calibration probes scored every run with the same scale.

The harness reads only API output. It never imports pipeline internals, so it stays a decoupled, fair scale. The same fixtures, the same ladder, and the same scorer produced every number below.

## Root cause

The engine's document-preprocessing pipeline enabled an unwarping step by default. The step exists for photographed, warped pages, where rectification genuinely helps. For flat, born-digital pages it was doing harm.

With unwarping on, detection ran on a rectified, re-scaled canvas — not on the pixels the user uploaded. The polygons were honest coordinates for a different image. One neighboring service in the same codebase already disabled that step explicitly; the OCR path had missed it.

## The fix — and how it is locked

The fix is one init parameter: `use_doc_unwarping=False`. After it, the probes confirmed the polygons sit in the input pixel frame again, and rotation is preserved at its true magnitude instead of being flattened away.

The fix is locked by 4 contract tests incl. negative controls, wired into Phase A CI. Flipping the flag back or deleting the line turns the suite red. Regression protection does not depend on anyone remembering.

## Measured impact

| Evidence | Value |
|---|---|
| Coordinate drift (8 calibration probes) | scale 1.1084–1.2257, non-rigid; fit residuals 9.9–51.6 px |
| Rotation flattened | 3° input → −0.82° residual; 15° → −2.80° |
| Fix | one engine-init parameter (`use_doc_unwarping=False`) |
| Lock | 4 contract tests incl. negative controls, wired into Phase A CI |
| Before → after | 15 fixture×spec combos: 12 improved, 0 regressed, 3 flat |
| Text volume recovered | 2,712 → 4,963 chars (rotated dense form); 1,361 → 2,849 chars (heavily rotated engineering-drawing page) |
| Reproducibility | 26/26 API responses byte-identical across two independent cloud runs |

Every row above was read on the same scale, from the same fixture set, before and after the change. The two text-volume examples are the largest recoveries: a dense machine-printed form under rotation, and a born-digital engineering-drawing-style document under heavy rotation.

## What this means for your documents

> "These are relative improvements measured on controlled fixtures, before vs. after our own change — not absolute accuracy claims."
> "Every pipeline change we ship is measured the same way: same fixtures, same degradation ladder, same scorer."

A bug like this never announces itself. Text comes back plausible, boxes look roughly right, and the error only shows when coordinates meet the real image. It has to be measured out of the pipeline, not eyeballed away.

If you evaluate document-AI vendors, ask one question: is your before/after measured on the same fixtures with the same scorer, and can you reproduce the numbers? We hold ourselves to that, and this page is what the answer looks like.

If you want to see this measurement discipline in a live session, see [TRIAL_DEMO.md](TRIAL_DEMO.md).
