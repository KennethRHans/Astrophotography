# Adaptive FITS opening preview — Windows test build 1.7.1

This is a portable test, not a Microsoft Store submission or installer. It uses
separate application preferences and reference-browser storage. The Store app
remains installed. Extract ALL files, then run EasyAstroStudio.exe alongside its
_internal folder. Keep projects as separate test copies.

## Try the comparison

1. Open the same C56 FITS used in Siril. New FITS opens with **Adaptive — darker
   sky** in **4. Adjust and Crop → Opening preview**.
2. Switch to **Legacy — bright preview** to compare the prior fixed stretch.
   Switching resets Stretch, Black point, Exposure and Shadows to that mode's
   opening values; other adjustments remain. Undo restores the previous state.
3. Adaptive already includes its base midtones transfer, so Stretch starts at 0.
   Raise Stretch/Midtones/Exposure for further adjustment. Black point starts at
   0% ADDITIONAL percentile clipping; the adaptive base has its own shared black
   point. Reset adjustments returns to the selected opening transfer.
4. Try GPU on/off and compare settled preview, zoom, crop and raster exports.
   GPU/OpenCL still handles its existing adjustment operations. The new linked
   opening transfer is shared CPU preparation for both paths, not a new GPU
   stacking algorithm. Unavailable/failed devices retain CPU fallback.
5. Open an older .astro project: it must retain its saved Legacy rendering, edits
   and history. Ordinary imported JPG/PNG files are not auto-stretched.

## What changes

The adaptive transfer estimates median/MAD from a bounded grid of original RGB
samples, uses a shared black point and the full original image peak, and derives
a linked-luminance midtones transform with a 20% background target. An original-
field transfer is fixed through slider changes, zoom and crop. The black point
can still clip some shadows; watch the histogram. The target is an estimate,
not a semantic sky mask or a color calibration. Extended nebulosity/gradients can
bias it; gradient removal remains a separate, user-controlled adjustment.

The prior pipeline used independent per-channel percentile black points and a
99.9th-percentile white followed by a fixed asinh stretch of 30. Its behavior is
retained in Legacy and for projects without an adaptive transfer.

Preview and TIFF/PNG/JPG exports use the same transfer. Linear FITS exports and
Save stacked FITS retain source pixels. There is no change to stacking/rejection,
calibration or original input files. No images, metadata or API keys are uploaded
by the adaptive stretch.

## Project compatibility

New adaptive projects save their transfer and Undo/Redo states in project format
2. They require this test build or a later app supporting format 2. Store version
1.7.0 intentionally rejects these projects instead of displaying them incorrectly.
Existing format-1 projects remain format 1 unless adaptive state is introduced
(including in Undo history). Use Save project as to keep test copies. Do not
replace your only working project during testing.

## Verification

Private user C56 data was tested locally only: engine RGB reads equal the source
FITS pixel-for-pixel; Adaptive preview median approximately 20.005%, rendered
full-resolution export approximately 20.001%, input-file SHA-256 unchanged.
The file and diagnostic images are excluded from this public test branch/build.

Automated tests cover the audited transfer, raw data preservation, linked RGB,
zoom/histogram/export consistency, invalid metadata, raster exclusion, mode
switching, reset, Undo, format-2 round trip, legacy project restoration and GPU
failure fallback. Actual OpenCL parity runs only when a device exists. Test on
Ken's RTX hardware before proposing a Store release. This test package does not
update the Apple handoff or publish a Store release.
