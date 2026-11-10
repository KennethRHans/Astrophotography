# Apple handoff: stacking and background extraction (Windows 1.6.0)

Shared source commit: `b52a3b1b37dd0246446b379008a2a7ea5fa9f19e`
Branch: `codex/seestar-studio-preview`. Port selectively into `codex/macos-1.5`.
Do not overwrite Mac packaging, sandbox/file-access handling, Metal code or
Mac-only sky settings. This release adds no new third-party dependencies or
network/data collection. Private astronomy images are not part of the changes.

## 1. Stacking audit and robust rejection

See `STACKING_AUDIT.md`. Existing code already does median-centered 3-sigma
clipping using standard deviation, three iterations, then an equal mean. Multiple
bright contaminated frames can inflate that deviation and survive rejection.

`stack_store.robust_weighted_mean(block, weights)` adds one-pass unweighted
median/MAD rejection at 4 × 1.482602218505602 × MAD. Minimum threshold is
max(abs(median) × 1e-6, 1e-6), handling constant/quantized inputs. Only finite
samples count. At least EIGHT covered samples are required at a pixel; smaller
sample sets use a weighted mean without rejection. Rejection does not use weights.
After rejection, sum(value × frame weight)/sum(accepted frame weights). Missing
coverage becomes zero in `combine`. This is not a guarantee against every trail,
stationary hot pixel, variable/transient source or star-profile mismatch.

`combine` adds keyword `weights=None, rejection='legacy'` to preserve existing
low-level callers. `engine.stack` defaults to rejection='robust', quality=True,
normalize_exposure=False. Keep legacy 3-sigma/equal weights selectable. Legacy
mode disables both weighting and normalization. Chunked disk-backed storage and
cancellation cleanup remain intact.

## 2. Relative quality weights and exposure handling

New portable module: `stack_quality.py`. `engine.stack` calls existing
`frame_quality.measure` on each original unaligned RGB exposure, after optional
exposure scaling. Weights compare matching dimensions, target, exposure and
filter. For valid groups of at least two frames:

    raw = (median_noise/noise)^2 * (median_FWHM/FWHM)^2
          * (median_elongation/elongation)^2
    weight = clip(raw/median(raw), 0.25, 4)

Require at least six measured stars and finite positive metrics. Unmeasurable
frames/singletons retain 1; no whole frame is automatically discarded. Alignment
failures are still skipped, and the first listed frame remains the reference.
Log weight range and neutral-metric fallbacks. Noise/FWHM measurements remain
advisory and are not transparency or photometric calibration.

Optional exposure normalization is OFF by default. Require positive finite
exposure metadata for ALL inputs, otherwise disable it. Scale moving RGB pixels
by reference exposure/current exposure. For quality grouping set EXPTIME in the
measurement header copy to reference exposure when normalization is active.
Use calibrated frames: camera offsets also scale; this is not dark/flat or sky
level calibration. With normalization off, mixed exposure levels can impair
rejection; log this when durations differ. Never alter files on disk.

Copy integration metadata from `engine.stack`:
- NCOMBINE: alignment-accepted frames, not contributors at every pixel.
- TOTALEXP: sum available actual accepted durations, not weighted exposure time.
- EXPTIME retains the reference value; HISTORY explains mixed durations.
- EASREJ, EASWGHT, EASNORM record method and flags.
- EXPMIN/EXPMAX record accepted duration range.
- WGHTMIN/WGHTMAX and EFFRAMES=(sum w)^2/sum(w^2) when weighting is enabled.
  EFFRAMES is global before per-pixel rejection, not local coverage.

## 3. GPU porting

Windows `gpu.py` adds `combine_weighted`; it is OpenCL-specific. Scratch is
separate from the original input to retain frame-index/weight correspondence
when quickselect reorders samples. Median and MAD use the scratch; accepted sums
read original frame positions and their weights. Scratch budget accounts for
both image buffers, and fp64 accumulation mirrors CPU behavior. CPU fallback
retries the intact current chunk if a device/kernel fails.

Do NOT copy OpenCL GPU initialization over the Mac Metal path. Either implement
and test equivalent Metal weighting/rejection or explicitly use the bounded CPU
robust path until supported. Do not silently run legacy/equal-weight combining
when robust/weighted is selected. Existing Metal image adjustments can remain.

## 4. Visual sky-sample background extraction

Portable new modules:
- `background_extraction.py`: validation, auto point grid, sample fitting and
  transformation of original-field coefficients to current cropped coordinates.
- `background_dialog.py`: Qt visual sample editor using original image coordinates.

Step 4 button: "Background extraction — choose sky samples…". Left-click adds a
sample, clicking near a box removes it, auto points exclude a central ellipse,
and Clear permits manual placement. Wheel zoom and right/middle pan work. Auto
points assume a centered target; users must review and remove contaminated boxes.
Default model is a plane; quadratic is optional. Fit medians of finite positive
pixels in small boxes after rejecting >3-MAD pixel outliers. Require enough valid
samples, broad coverage and a well-conditioned design. Do not silently discard
selected boxes based on diffuse object emission. A user can still subtract real
nebulosity by choosing it as sky.

Apply sets Gradient removal to 100%; the slider can reduce it afterward. Retain
the fitted constant term: remove spatial variation only, not a global sky offset.
Background color neutralization remains independent. Restore automatic background
fit is available. Existing automatic background behavior stays unchanged for old
projects and when no custom sample configuration is active.

## 5. UI, projects and crop integration

Port relevant `app.py` portions, not the whole file:
- Step 3 rejection selector; quality toggle default ON; normalize toggle default
  OFF; controls disabled during work/legacy mode; QSettings preferences.
- Pass `stack_options` into Worker/engine.stack.
- Step 4 editor button and `edit_background`.
- State `background_fit`: None, or {'order': 1|2, 'points': [[x,y], ...]}.
  Normalized original-image coordinates [0,1], max 144 samples. Missing in old
  projects/history means None. No render-settings tuple positions change.
- `project_store.validate_state` validates extraction config.
- `make_background` fits original pixels and transforms coefficients for crop.
  Preserve the Mac display-encoded wrapper and existing image adjustments.
- `apply_edit_state` recomputes on model/crop change. Include model in Undo/Redo,
  dirty signatures and project saves. Reset adjustments restores automatic fit.
- New-project/image load clears custom fit. Full-frame restore retains selection
  and transforms it correctly; editing still shows the full original image.

Background extraction remains display-only: TIFF/PNG/JPG include it, but Save
stacked FITS and FITS export retain the integrated linear data. Stacking weighting,
rejection and optional exposure normalization DO change the integrated data.
Do not describe display extraction as calibrated linear FITS export.

## 6. Validation

New tests: `tests/test_stack_improvements.py`, `tests/test_background_extraction.py`.
Repeat existing pipeline, stack-store, GPU, project/history, crop, live-preview,
neutralization and export tests. Adapt OpenCL cases to Metal; keep shared CPU cases.

Cases include: two bright trail samples among eight surviving legacy but removed
by robust; <8 samples un-rejected; uncovered/one-sample pixels; weights capped and
fallback neutral; synthetic sharp/clean versus blurred/noisy mixture improves
background noise and star peak; chunk bounds/device failure/input immutability;
mixed 20/30-second scaling and TOTALEXP; selected-sky gradients and extended-signal
retention; crop coefficient mapping; invalid fits; Undo/reset/project round trips.
Manual GUI check should cover sample selection, editor zoom/pan, preview/raster
export and restoring automatic fit. Add packaged import/processing smoke checks
for the new modules before releasing a Mac package.

Windows local validation: 123 tests and application smoke passed; controlled GUI
checks passed. Windows package validation passed: packaged smoke, exact Store-identity
installation/activation, Program Files, desktop shortcut and upgrade checks.
Windows runner: 110 passed, 13 skipped (OpenCL unavailable there); local fp64
OpenCL tests passed on the software OpenCL runtime. Downloads are in README. Re-run on Apple hardware rather
than treating Windows success as Metal or sandbox validation.
