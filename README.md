# Easy Astro Studio — preview 0.14

A Windows GUI for aligning and stacking color FITS exposures, editing existing
FITS stacks and exporting images. Built for Windows 11 x64; Python is not needed
when using the installer. Previously named Astro Studio for Seestar.

## Exposure review, About and workflow (0.14)

About in the top menu shows the full application version. The header includes
by Astrivanta © in smaller centered text. Instructions and Step 1 now put Bayer
selection/help first, then Open existing FITS stack, then Add exposures, review,
and Align and stack, using the requested wording.

After adding individual exposures, click Preview / rate exposures. Select an
exposure and click Preview selected (or double-click its row). Fit, 100%, mouse
wheel zoom and right/middle-drag pan help inspect it. The default preview is
reduced to at most 1600 pixels on its longer side; Full resolution rerenders
native pixels for focus/star checks. Only one exposure is loaded at a time.
The current main image, crop and edits are preserved while reviewing.

Analyze all exposures measures detected star count, approximate FWHM and median
elongation using SEP on a background-subtracted, reduced image. A relative score
favors sharpness (55%), roundness (25%) and star count (20%). Scores are grouped
by target metadata, dimensions, exposure time and filter. A frame needs at least
six reliable detections and another comparable frame to receive a score.
Select highest score operates within the selected exposure's matching group.

These are advisory comparisons, not calibrated image-quality grades or alignment
guarantees. Clouds, nebulosity, saturation, hot pixels, sampling and missing
metadata can mislead the detector. Preview the stars before deciding.
Use as reference explicitly moves the chosen exposure to the first list position;
all exposures remain included. Analysis never deletes or automatically rejects
files and does not change their pixels. Cancel stops between exposures. Closing
the review safely waits for its current worker to stop.

The reference matters because all other exposures align to it; a sharp frame
with many well-distributed stars generally makes matching more reliable. Choosing
a better reference can reduce skips but cannot rescue frames with little shared
field or poor signal. Raw exposures still need the same target, dimensions and
exposure settings. The app does not weight stack contributions by these scores.

## Community buttons and observing banner (0.13)

The fixed dark-blue footer includes Buy the Developer a Coffee (opens
https://cash.app/$KennethRHans) and Report a Bug / Suggest a Fix. Feedback opens
an in-app form with report type, optional name/email and a message, submitted
only when Send is clicked to https://formspree.io/f/xzezdzwd. Success is confirmed
by the service; errors/timeouts retain the message for retry. No images or logs
are attached automatically. A clickable banner below the buttons reads
Plan tonight's observing at https://astrivanta.com/ and opens the default browser.

## Changes in 0.12

- GPU row combining when the GPU checkbox is selected, in addition to GPU image
  adjustments. Star matching, registration, file reads and background fitting
  remain on CPU. The log identifies the active combining backend and fallback.
- Bounded input chunks (up to 32 MiB, also limited by device capacity), explicit
  temporary disk reads and immediate release of completed chunks. The whole
  aligned stack is no longer mapped into process RAM. The final image, alignment,
  transfers and CPU clipping statistics still need additional system memory.
  Windows may use spare RAM for reclaimable disk caching.
- New name in the header, title, executable, Windows app entry and shortcuts;
  supplied telescope-and-observer logo recolored blue/white for the black/navy
  theme. Removed the old affiliation text from the interface.
- Bayer guidance with camera examples and file-orientation cautions.

## Windows download

The 0.14 installer is being validated. Previous version:

[Download Easy Astro Studio 0.13](https://github.com/KennethRHans/Astrophotography/actions/runs/41518195945/artifacts/13177820196).
Close the app, extract the ZIP and run
`installer/EasyAstroStudio-0.13.0-Setup.exe`.
Windows tests, packaged launch (including the feedback dialog), installation,
desktop shortcut and upgrade preservation checks passed. Feedback validation,
success/error handling and retry were tested with simulated responses; no live
test report was submitted to the owner's Formspree inbox.

Previous version:

[Download Easy Astro Studio 0.12](https://github.com/KennethRHans/Astrophotography/actions/runs/41383581168/artifacts/13114313119).
Close the app, extract the ZIP and run
`installer/EasyAstroStudio-0.12.0-Setup.exe`. Python is not required.
The previous 0.11 version is available
[here](https://github.com/KennethRHans/Astrophotography/actions/runs/41379578047/artifacts/13112444289).

New installations default to `C:\Program Files\Easy Astro Studio`. Upgrades keep
the existing folder and stable installer identity, replace the old executable
and app-created shortcuts, and preserve user files. Close the app before updating.
The installer offers a desktop shortcut. Taskbar pinning is a manual Windows
action; re-pin the renamed app if needed. This preview is unsigned.
If still using the old per-user 0.2 preview, uninstall it in Windows Settings first.

## Workflow

1. Copy your original FITS files to a local folder and keep a backup. Add individual
   exposures and choose Align and stack, or open an existing FITS stack directly.
   Use one target, image size and exposure setting per batch. The first exposure
   is the alignment reference. Files marked STACKCNT/NCOMBINE > 1 are rejected in
   the individual-exposure route. Review the log for skipped frames.
2. Adjust stretch, black level, brightness, contrast, saturation, RGB gains,
   background correction and optional noise smoothing. Drag crop edges/corners
   in the image; choose a ratio, rulers or guides. Use +/−, Fit, 100%, mouse wheel
   and right/middle drag to zoom/pan. These view changes do not resize exports.
3. Export full-resolution 16-bit RGB TIFF, 8-bit PNG/JPEG, or linear float32 FITS.
   The suggested filename uses FITS OBJECT (for example C 56 becomes C56).
   FITS preserves linear data and the applied crop, without display adjustments.

Reset adjustments restores sliders without removing the crop. Restore full frame
recovers original pixels while the original image is loaded or saved in a project.
Cropping trims pixels and adjusts FITS WCS/SIP coordinates; it does not remove
noise within the retained area. Guides never appear in exported images.

## Save projects, undo and histogram

Use Open project, Save project or Save as in the toolbar. A self-contained `.astro`
project embeds the original linear RGB image, FITS header, adjustments, crop,
view and up to 100 undo states. Original exposure filenames are references;
raw exposures are not embedded or automatically reopened. Keep them backed up.
Projects work after the input stack has moved. Save/reopen runs in the background.

Undo/redo: Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z). A slider drag or crop gesture is one
operation. Applied crops, crop restoration and reset can be undone.
The RGB histogram and clipping percentages use the rendered preview sample.
Blue shadow/red highlight warnings are preview-only and never exported.

## Bayer pattern guidance

Use **Auto** whenever FITS BAYERPAT is present. The camera sensor and capture
software determine the stored pattern, not the telescope optics. These are
examples, not automatic model-to-pattern assignments.

| Choice | Guidance |
| --- | --- |
| Auto | Recommended for Seestar and most color cameras; uses each file's header. Missing metadata produces grayscale. |
| RGGB | Common on ZWO ASI2600MC, ASI533MC and ASI6200MC color cameras; verify the file's header/orientation. These cameras can be used with refractors, reflectors or SCTs. |
| GRBG | Confirmed in the supplied Seestar S50 Pro raw exposures. Do not assume every Seestar model/software version stores the same orientation. |
| BGGR | Some camera/file orientations; also a 180-degree rotation of RGGB. No dependable telescope-only assignment. Check the header or camera/software documentation. |
| GBRG | Some camera/file orientations; also a 180-degree rotation of GRBG. Check the header or camera/software documentation. |
| None | Monochrome cameras such as ASI2600MM/ASI533MM, or single-channel data that should stay grayscale. |

Already-color RGB FITS cubes bypass Bayer conversion, even if an old BAYERPAT
card remains. Odd Bayer offsets are rejected to prevent wrong reconstruction.
Do not force a pattern just because a camera name looks familiar.

## GPU and memory

Install a current graphics driver; no CUDA toolkit is required. Selecting GPU
before stacking enables OpenCL sigma-clipped row combining and image stretch,
color, brightness/contrast and smoothing. If initialization, allocation or
processing fails, CPU processing resumes and the log explains the fallback.
Row combining requires double-precision OpenCL to preserve clipping decisions;
adjustments still work on devices without it. The GPU checkbox is locked during stacking so a run has a consistent selection.

Aligned frames use temporary disk space of approximately
`12 × width × height × frame count` bytes. Processing uses three iterations of
median-centered 3-sigma clipping and an average of retained samples. Uncovered
pixels are black. Both CPU and GPU use the same chunked disk-reading path.
GPU transfers and disk reads may outweigh compute savings; no RTX 5070 stacking
speed measurements are available yet. Cancellation takes effect between
alignment calls and combining chunks.

A synthetic 160-frame, 512×512 RGB CPU comparison measured peak process RAM at
611.4 MiB with the previous mapped-stack method and 154.1 MiB with the new method
(about 75% lower), with identical output means. This Linux measurement includes
storage and combining and is not a Windows/RTX 5070 performance guarantee.

## Processing limits

Background correction fits a smooth quadratic sky surface and starts at zero.
Increase gradually: extended faint nebulosity can be mistaken for background.
RGB gains are artistic controls, not photometric color calibration. Smoothing,
registration and interpolation alter pixels. No generated detail is added to
astronomical images. Preview percentiles are sampled; full-size exports can
look slightly different. JPEG is lossy, quality 95; TIFF is 16-bit RGB.

There is no dark/flat/bias calibration, automatic frame ranking, photometric
calibration, sharpening or automatic updates. Absolute color fidelity is not
validated. Keep linear FITS and original exposures and inspect a small batch first.
The header artwork is decorative and does not affect astronomical processing.

## Validation

All 37 local tests passed, including software OpenCL comparisons for 2–512
frames, boundary-sensitive clipping, missing coverage, disk chunk limits,
GPU failure fallback, project/history/GUI behavior and reference review/scoring.
Synthetic sharp/blurred/trailed/noise-only fields verify the rating direction and
group separation. The ten real S50 Pro samples also completed quality analysis. Ten real S50 Pro exposures
passed full-resolution alignment and all 120 GPU combining chunks matched the
CPU result within floating-point tolerance (maximum absolute difference 0.0078125
in the source data scale). No source images are included in the download/repo.
Windows tests passed (OpenCL comparisons skipped on the runner without a device).
Packaged app launch, JPEG export, project roundtrip, Program Files installation,
desktop shortcut and installed launch checks passed. An actual upgrade from 0.11
also passed: the Windows app entry and shortcuts use Easy Astro Studio, the old
executable was removed, a user-created file was preserved and the upgraded app
launched. This preview remains unsigned; RTX 5070 combining performance still
needs testing on physical hardware.

## Development

Python 3.12 x64:

```
python -m pip install -r requirements.txt pytest
python -m pytest -q
python app.py
```

On Windows, Build-Windows.cmd creates the executable; Inno Setup 6 compiles
installer.iss. GitHub Actions runs tests, builds, launches the packaged app,
checks Program Files installation/desktop shortcut and verifies an actual upgrade.
OpenCL comparisons skip when a runner has no device; local software OpenCL is
used for numerical conformance, without claiming hardware GPU performance.
Libraries retain their own licenses, including PySide6/Qt LGPL terms.
