# One Apple update for both pending Windows changes

## Included work

| Feature | Reference notes | Source/provenance |
| --- | --- | --- |
| Object Reference: color survey guide, mirror fallback, local/offline references | APPLE_HANDOFF_1_7.md | Shipped/tested Windows 1.7.0, retained in the combined snapshot |
| Adaptive FITS opening: darker linked-RGB transfer, Legacy choice, saved-project compatibility | APPLE_HANDOFF_1_7_1.md | Windows 1.7.1 portable test accepted by Ken; not promoted to the Windows Store yet |

Combined source pin: `af4e91d5387cd02419d828dd70044ce3cb7fcebc`.
Branch: `preview/adaptive-fits-opening-1-7-1` in KennethRHans/Astrophotography.
Windows test run: https://github.com/KennethRHans/Astrophotography/actions/runs/44333483520
**128 passed, 14 skipped**, plus frozen-app smoke success. Hardware-dependent
OpenCL cases are skipped when no device exists. Ken reported the test looks great.
Earlier Object Reference production validation and its live M77 test are linked
in APPLE_HANDOFF_1_7.md. No Mac validation has been performed for this handoff.

The previous Object Reference handoff remains complete in this ZIP, not just a
link. Its 1.7.0 pin is historical provenance; use the combined source snapshot
above when porting, with the later opening behavior described in the supplement.
The project-format version 2 change is intentional. Do not accidentally restore
the older project_store.py over it while integrating Object Reference.

## Integration order when Ken authorizes implementation

1. Identify the current Apple branch, release version and project schema. Preserve
   local changes. Confirm which prior shared processing updates have been ported.
   The old stacking/quality-weighting/background extraction handoff is included at
   windows-source/APPLE_HANDOFF_1_6.md for a baseline audit; it is not automatically
   assumed complete or silently added to scope.
2. Port the adaptive transfer and project state/schema support as one unit. Verify
   existing project appearances before changing the opening GUI defaults.
3. Integrate the Opening preview choice, history, compare/reset, crop, exports and
   Metal/CPU preparation. Preserve Apple preferences and native file handling.
4. Port Object Reference as an independent optional panel. Integrate it with the
   same existing toolbar/dock area as Labels & Objects without replacing the
   adaptive preview or processing state.
5. Merge both features' new-image/new-project, project restore, UI readiness,
   theme, cancellation and shutdown handling. Do not take one Window.loaded or
   closeEvent change and discard the other.
6. Bundle reference assets/notices and update the public AND embedded policy for
   the optional reference requests. The adaptive stretch itself is entirely local.
7. Run feature and cross-feature tests on the actual Mac build, then report what
   passed, failed or remains unverified. Do not treat Windows results as Mac,
   Metal, sandbox or App Store validation. Release only on Ken's instruction.

## Required cross-feature behavior

- Newly opened linear FITS uses Adaptive; old saved projects retain their prior
  appearance. JPG/PNG inputs keep display-encoded treatment. Loading any new
  image resets reference consent/context without fetching a survey.
- Opening Reference, fetching a survey, rotating/flipping a guide, loading/clearing
  its cache and switching dock tabs do not alter the adaptive transfer, sliders,
  crop, annotations, history, project dirty state, pixels or exports.
- Adaptive/Legacy mode changes, sliders, compare/reset, Undo/Redo, cropping and
  project save/load do not trigger reference requests or replace its guide.
- Keep both toolbar buttons working in one click when their docks are tabified.
  Hiding/switching away revokes reference permission and cancels local work.
- Reference GPU use is browser WebGL2. Image adjustment GPU use is the existing
  Apple Metal path, fed the shared adaptive preparation. They are independent;
  do not tie reference WebGL to the processing Use GPU checkbox.
- Existing .astro projects do not silently acquire adaptive rendering merely
  because the user opens them. Saved adaptive transfer values remain fixed across
  crop/zoom and round-trip with the correct history/schema.
- Raster exports include adaptive/edited display appearance but never the separate
  reference guide. Linear FITS exports and original input files retain source data.
- Preserve Apple's sandbox/native chooser behavior for BOTH main-image access and
  local reference photos. Never disable sandbox protections to load the panel.

## Combined acceptance run

Open an old project; confirm unchanged appearance. Open a new FITS; confirm Adaptive.
Load an online reference only after consent. Move sliders, crop, change modes,
Undo/Redo and export: no reference fetch/replacement and no guide in the output.
Save a new project, close the app, disconnect the network and reopen it: adaptive
appearance/history round-trip, and the reference loads only from its saved cache
when requested. Reconnect, start a reference request, then open another image or
hide the dock: cancel/reset with no stale result or crash. Repeat with Metal on/off,
light/dark themes and the signed/sandboxed packaged Mac variant.

No Apple binaries, certificates, provisioning files or Store submission are
created by the handoff build. Do not merge the whole Windows branch into Apple.
