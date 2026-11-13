# NI-086 — Approved visual assets

Built-in `imagegen` was used, without API keys, CLI fallback or a new dependency.
The approved full-page concept is preserved as
[approved-overview-concept.png](approved-overview-concept.png).
The actual page uses native HTML/React text and controls; it does not embed that
mockup as a screenshot. The separate decorative hero is stored in the project at
[overview-research-desk.png](../../../apps/web/public/illustrations/overview-research-desk.png)
(1254 × 1254, 2,046,996-byte PNG) and delivered through the existing Next Image
optimizer. Its alt is empty; unlabeled lines are decorative and not data.

The original SVG research illustration is preserved. Generated source images
remain in the default Codex generated-images directory; the selected project
asset is copied into the workspace and has no external runtime URL.

## Final hero prompt (verbatim)

```text
Use case: precise-object-edit. The reference is the approved full-page NEAR Intelligence Overview mockup. Extract and reconstruct ONLY the decorative research-desk illustration in the TOP RIGHT HERO, as a standalone high-resolution square or 6:5 website illustration. Keep the three overlapping warm ivory research sheets, subtle sage background, delicate leafy olive-green branch entering from the top right, thin dark-green decorative chart strokes on the middle sheet and forest-green fountain pen at the lower edge. Preserve the reference's refined softly lit tactile editorial illustration, restrained shadows and warm ivory/forest-green palette. Frame the artwork to fill the image, without any surrounding website, heading, navigation, card, button or footer. Remove all words and letters from the sheets: keep only fine abstract horizontal rules and unlabeled decorative line motifs, no numbers, axes, measured values or financial claims. The artwork is decorative, not observed chart data. Clean sharp edges, generous breathing room around the sheets, bright matte background, no logos, no watermark. No new objects.
```

Reference: the approved Overview mockup in this directory. Transparent background:
false. The image was visually inspected before project handoff; words and
financial values are absent from the artwork.
