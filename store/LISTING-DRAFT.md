# Proposed Microsoft Store listing — review before submission

Name: Easy Astro Studio (subject to name reservation)
Publisher display name: use the exact Partner Center value
Suggested category: Photo & video
Supported language: English (United States)
Architecture: x64
Operating system: Windows 11
Pricing/markets: owner to select; not configured or published

## Short description

Stack FITS exposures, inspect stars and turn your astrophotography data into
finished images with an approachable desktop interface.

## Description

Easy Astro Studio helps you process color astrophotography FITS files on your
Windows PC. Open an existing stack, or align and combine individual exposures.
Preview exposures and compare advisory star-quality measurements to choose an
alignment reference. Adjust brightness, contrast, stretch, color and smoothing;
crop your composition; and export TIFF, PNG, JPEG or linear FITS.

Save your editing session as a self-contained project and return later. Undo and
redo help you explore adjustments, while an RGB histogram and optional preview
clipping markers help assess the displayed result. Choose from six interface
themes, including light and dark modes. Compatible OpenCL GPUs can accelerate
row combining and image adjustments; CPU processing remains available.

Your FITS processing happens locally. An internet connection is used when you
choose to send feedback or open external links. No telescope connection or
account is needed for image processing.

## Features

- FITS stack import and alignment/stacking of individual color exposures
- Bayer header detection with manual pattern choices and camera guidance
- Exposure previews, star metrics and explicit reference selection
- Disk-backed, bounded-chunk sigma-clipped combining
- Optional OpenCL GPU processing with CPU fallback
- Adjustment sliders, crop ratios, guides, rulers, zoom and pan
- Histogram and preview-only clipping warnings
- Self-contained projects, undo/redo and six saved interface themes
- TIFF, PNG, JPEG and linear FITS export

## Important processing limits to disclose

There is no dark/flat/bias calibration, photometric color calibration or telescope
control. Exposure scores are relative advisory measurements and cannot guarantee
alignment. Background removal and smoothing can suppress faint signal. FITS
export preserves linear pixels and applied crop, without display adjustments.
Preview sampling can cause small differences from full-resolution exports.
Keep original exposures backed up. GPU speed varies with hardware and data.

## Draft reviewer steps

1. Launch; select Bayer Auto or None as appropriate.
2. Open a local FITS stack, or add at least two comparable individual exposures.
3. Preview/rate exposures; choose a reference if desired; align and stack.
4. Adjust/crop and export JPEG/PNG/TIFF or linear FITS.
5. Save/reopen a .astro project; verify undo/redo.
6. Select Light from Settings > Theme and reopen to confirm persistence.

Provide a small distributable FITS sample with confirmed redistribution rights
for certification review; private user uploads are not included automatically.
