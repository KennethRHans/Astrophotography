# Windows stacking audit and improvements — 1.6.0

## Finding

The existing CPU implementation uses Astropy sigma_clip: median center, standard
deviation, 3 sigma, three iterations, followed by an equal mean. The OpenCL
implementation mirrors it, including finite-sample coverage and bounded disk
chunks. It already rejects many trails; it does not remove all artifacts.
Two bright contaminated samples among eight can inflate the standard deviation
enough that they survive. With few samples, reliable outlier classification is
inherently limited. A stationary hot pixel surviving alignment in every frame
also cannot be identified by temporal rejection alone.

## New defaults and comparison

Step 3 defaults to Robust rejection and optional quality weighting enabled.
Legacy 3-sigma / equal weights remains selectable and disables normalization and
quality weighting. Rejection uses unweighted median/MAD, a 4-sigma threshold,
one pass, and a rounding floor for constant/quantized data. At least eight finite
samples must cover a pixel; otherwise a weighted mean is used without rejection.
This is not a promise to remove every trail or preserve variable/transient objects.
Rejection masks are independent of weights. Both CPU and fp64 OpenCL support the
new path; failures retry intact bounded chunks on CPU. No stack-wide RAM mapping.

Weights combine inverse squared measured background noise, inverse squared FWHM
and inverse squared elongation, normalized to a group median and capped at
0.25–4. Groups match dimensions, target, exposure and filter. Fewer than six
reliable detected stars, unavailable metrics, or a singleton group retain weight
1. Metrics are advisory: nebulosity, clouds, saturated stars, transparency and
undersampling can mislead them. Frames are not automatically removed. The first
listed frame remains the alignment reference; users can still choose it in review.

Exposure-time normalization is optional and OFF by default. It requires positive
exposure metadata on every input, scales pixels to the reference exposure, and
makes quality comparisons at that exposure. Use calibrated inputs: camera offsets
are scaled as well; this is not dark/flat calibration or transparency calibration.
With normalization off, mixed exposure levels can impair rejection, and a log
message explains that limitation. Single-duration batches are preferred.

FITS records EASREJ, EASWGHT, EASNORM, EXPMIN/EXPMAX and, with weighting, the
weight range and global effective frame count. EXPTIME refers to the reference;
TOTALEXP sums available accepted exposure durations, not weighted durations.
NCOMBINE remains the number accepted by alignment, not the number contributing
to every pixel. Weighted rejection means local contribution counts vary.

## Background extraction

Step 4 adds a visual sky-sample editor. Click to add/remove boxes, auto-place
boxes outside the central region, or clear them and select your own. Review all
boxes: auto placement only assumes the target is near the center. Plane fitting
is the safer default; quadratic fitting handles curved gradients. Fits require
sufficient valid samples, spatial coverage and a well-conditioned design.
Per-box medians reject bright pixels, but selecting diffuse target emission as
sky can still subtract it. Only the spatial component is removed, retaining the
constant sky level. Gradient removal controls the applied fraction (Apply sets
100%). Global sky-color neutralization remains a separate control.

Sample positions use original-image coordinates, and model coefficients transform
correctly when cropping. Undo/Redo, Reset adjustments and projects retain the
selection. Restore automatic background fit is available. Old projects have no
custom selection and retain their prior automatic model. Extraction is display
processing: linear FITS exports preserve the integrated data. Rendered TIFF,
PNG and JPG include it. No user files or private diagnostics are published.

## Verification

Synthetic tests compare legacy/robust contaminated stacks, covered/uncovered and
small-sample cases, GPU/CPU agreement, chunk limits, fallback and input immutability.
A sharp/clean versus blurred/noisy mixture verifies lower background noise and
stronger retained star peaks with weighting; this is not a universal performance
claim. Mixed exposure tests verify reference scaling and actual total time.
Selected-sky tests check gradient residuals, extended-signal retention, crop
coordinate transforms, input immutability, invalid fits, Undo/reset and project
round trips. A full Windows build separately validates packaged launch, Store
identity installation and standard installer/upgrade behavior.
