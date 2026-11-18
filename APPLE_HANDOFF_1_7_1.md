# Apple supplement — adaptive linked-RGB FITS opening

## What Ken tested

Opening the same C56 FITS in Windows 1.7.0 and Siril showed an overly bright,
brownish initial Windows preview. Local inspection confirmed RGB reads matched
the source FITS exactly and reproduced the brightness without a GPU. It was a
rendering problem, not extra Bayer decoding or incorrect FITS scaling.

The legacy pipeline used per-channel 0.1-percentile black points, a shared
99.9-percentile white and fixed asinh Stretch=30. The new adaptive opening uses a
shared black point/full bright end and a linked-luminance midtones transform.
On the private test file, median displayed brightness changed from about 61% to
20%; the original file remained unchanged. That file and diagnostic images are
NOT in this package. This is not a promise of exact Siril matching or calibrated
colors. Gradients remain for separately chosen background extraction.

## Source files and integration points

All paths are under windows-source/:

- opening_stretch.py: opening_statistics, validate_opening_stretch, linked_midtones.
- review_stretch.py: existing review_statistics reused with target=.20 for main
  opening; the exposure-review window retains its existing .16 target.
- engine.py: model-dictionary unwrapping in correct_background, adaptive scalar
  normalization, linked opening transfer before GPU/CPU display adjustments.
- app.py: Opening preview combo; loaded(..., automatic=True), change_opening_mode,
  make_background, settings/compare, reset_adjustments, edit_state,
  apply_edit_state, _project_opened and update_actions.
- project_store.py: validate transfer in every state/history entry; format 2 saves
  adaptive state; accept versions 1 and 2. Format 1 remains for all-legacy history.
- tests/test_opening_stretch.py: new behavior, export/source preservation, mode
  switch/Undo/reset, old/new project restoration and OpenCL parity when available.
- tests/test_live_preview.py: opening Black point now displays 0.00% in Adaptive.
- OPENING_PREVIEW_TEST.md: Windows test instructions and compatibility explanation.

Do not copy app_version.py PREVIEW_BUILD=True, the Windows test QSettings namespace,
Windows taskbar identity or CI packaging into the current Apple release. Choose
Apple version/build numbers independently and preserve its existing preferences.

## Exact transfer and ordering

opening_statistics calls review_statistics(image, target=.20):

1. Use a grid of ORIGINAL source pixels with step ceil(max(height,width)/512).
   Valid samples must be finite and positive in every RGB channel. No valid
   samples -> no adaptive transfer (Legacy fallback).
2. Luminance weights [0.2126, 0.7152, 0.0722]. Sky=median(sample luminance).
   Noise=max(1.4826*median(abs(light-sky)), abs(sky)*1e-6, 1e-12).
3. black=max(0, sky-3*noise). White=max(full original RGB image peak,
   sky+12*noise, black+1e-12). The peak comes from the ORIGINAL image, not a resized
   draft. Do not use a percentile of sparse background noise as the white point.
4. b=clip((sky-black)/(white-black), 1e-12, 1-1e-7).
   m=b*(1-target)/(b+target-2*b*target), clipped to [1e-7,1-1e-7].
   Persist [black,white,m] as finite built-in numeric values.
5. Validate exactly three finite non-boolean numbers: black>=0, white>black,
   0<m<1. Reject malformed metadata rather than guessing.

Normalization and rendering:

- Wrap the ordinary gradient model as {opening_stretch: tuple(values),
  background: coefficients}. Existing display_encoded raster wrapping remains
  separate and does NOT enable adaptive opening.
- correct_background unwraps a dictionary's background before fitting/removal;
  do not use array indexing on the wrapper.
- Adaptive floor is scalar black. Black point slider starts at 0% ADDITIONAL
  percentile clipping. If raised, floor=max(base black, percentile(corrected
  luminance, requested percentile)). White span=max(base white-floor,1e-12).
- Normalize max(corrected RGB-floor,0)*manual RGB gains / white span, clip [0,1].
  Shared preview sampling statistics keep zoom/drag stable. At default Black=0,
  original-field transfer is identical for preview and full raster export.
- Existing optional neutralization and protected denoising precede the opening
  midtones map. For normalized luminance L:

      M=((m-1)*L)/((2*m-1)*L-m)
      ratio=M/L for L>0, otherwise 0
      RGB=normalizedRGB*ratio
      RGB/=max(max(RGB channels),1)

  Clamp [0,1]. Common scaling preserves channel ratios subject to normalization,
  clipping and explicit manual edits. Zero/invalid source coverage stays black.
- Run that shared CPU preparation ONCE before the existing GPU or CPU adjustment
  path. Then apply user asinh Stretch, saturation/smoothing/exposure/contrast,
  sky offsets and user midtones/curve in the current established order.
  On GPU failure, retry from the same prepared pixels, not a twice-applied opening
  map. Preserve Apple's Metal implementation; do not replace it with OpenCL.
- Original source pixels and headers are untouched. This is display/raster-export
  processing; Save stacked FITS and linear FITS export retain linear source data.

## UI, reset and history

New linear FITS (including newly integrated stacks) initializes Adaptive. The
Opening preview combo offers Adaptive — darker sky and Legacy — bright preview.
Adaptive uses Stretch=0, additional Black=0 because its base transfer is already
active. Legacy retains Stretch=30 and Black=0.1 percentile. Imported JPG/PNG stays
in its display-encoded path with no adaptive transform; disable the mode chooser.

Mode changes preserve other edits but reset Stretch/Black/Exposure/Shadows to the
chosen mode's initial values. Record history BEFORE changing the transfer, rebuild
the gradient-model wrapper/cache key, reset Compare off and render. Undo restores
both transfer and slider state. If no adaptive statistics exist, represent the
actual fallback accurately in the UI.

Compare: opening view ignores subsequent user adjustments and uses the selected
opening transfer. Reset adjustments restores the selected opening values and
curve/background defaults; it does not silently switch to Legacy. Cropping/zoom
reuse the original-field transfer instead of estimating a new stretch from each
view. New Project clears it. Theme/reference-guide changes do not touch it.

## Project compatibility — essential

Persist an optional opening_stretch field in editing state AND each history state.
Missing/None means Legacy, not automatic detection. An existing project must not
change appearance when opened with the new app.

The Windows implementation calls loaded(..., automatic=False) during project
restoration, then restores the saved transfer. Normalize absent fields to None in
ALL restored history/current states before comparisons, otherwise opening an old
project can spuriously appear dirty or enable Undo. Rebuild the model when the
transfer or background fit changes, even without a crop change.

For the existing shared .astro v1 format, saving any adaptive current/history
state writes version 2. All-legacy histories can remain version 1. New readers
accept both; old 1.7.0 readers reject version 2 instead of rendering it wrongly.
If Apple has already advanced its own schema, migrate compatibly rather than
blindly downgrading it. Explicitly document cross-platform compatibility.

Test with copies. Validate transfer values on save/load in every history entry;
do not pickle objects. Keep existing atomic save behavior and original image
embedding. There are no new online requests or telemetry from this feature.

## Acceptance checklist

- New FITS opens around the intended background level; validate astrophotography
  stars/extended objects and gradients, not only uniform synthetic noise.
- Unknown/flat/all-zero frames, raw debayered inputs and float RGB stacks remain
  finite; input files/arrays stay byte/pixel-identical.
- Adaptive default agrees with the audited linked transfer. Rendered export and
  settled preview agree; zoom/drag retain stable histogram/normalization.
- Manual color gains, Black point, exposure, curves, protected denoising, sky and
  selected background extraction still respond meaningfully.
- Adaptive/Legacy toggles, reset, Compare, crop, Undo/Redo restore exact state.
- Old projects with multiple history entries restore their Legacy appearance,
  saved edits, dirty state and Undo availability. New projects round-trip the
  transfer, crop and history in the chosen compatible schema.
- GPU/Metal on/off agrees within documented numeric tolerance. Simulated device
  failure produces the same CPU result without doubling the opening transform.
- Main JPG/PNG import remains unchanged. Original linear FITS exports retain data;
  TIFF/PNG/JPG include display edits, never an Object Reference guide.
- Run the cross-feature checklist in APPLE_COMBINED_HANDOFF.md on a packaged Mac.

A 20% sky estimate can be biased by extended nebulosity/gradients. The base black
point clips some shadows; it is not guaranteed to preserve every faint feature.
Watch clipping, keep manual control and do not describe this as photometric color
calibration, automatic gradient removal or added signal. No Apple implementation
or release has been performed as part of preparing this handoff.
