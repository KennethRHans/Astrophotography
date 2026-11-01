# Seestar Studio — preview 0.4

A Windows desktop prototype for Seestar color FITS exposures and existing stacks.
Built for Windows 11; CPU processing. Optional OpenCL acceleration can use the RTX 5070 for image adjustments.

## Optional GPU adjustments (0.4)
Check Use GPU for adjustments to accelerate stretching, saturation and Gaussian
noise smoothing using OpenCL. Install a current NVIDIA graphics driver; no CUDA
toolkit is needed. The log identifies the selected GPU. If initialization or
processing fails, the app returns to CPU processing and explains why in the log.
This setting starts off and is experimental. Star matching, registration,
stacking, FITS I/O, background fitting and percentile calculations remain on CPU.
Transfers and CPU work may outweigh GPU savings for small previews or when
smoothing is off. No RTX 5070 performance measurements are available yet.

## Cropping (0.4)
Drag a rectangle on the image, or enter Left/Right/Top/Bottom margins in pixels,
then click Apply crop. Crops affect the preview and all exports, including FITS.
Restore full frame returns to the loaded image without changing your sliders.
Reset adjustments resets sliders and Compare, and keeps your crop.
Cropping trims pixels; it does not improve noise inside the retained area.
FITS reference pixels are shifted to retain WCS and SIP sky coordinates.
The original files remain untouched. Only the currently loaded image can be restored;
a cropped file reopened later does not contain the pixels removed on export.

## Reset adjustments (0.3.1)
Use Reset adjustments to restore all eight sliders to their starting values and
turn off Compare. The loaded image and exposure list are preserved.

## Latest Windows download (0.4)
[Download the Windows preview ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/41346118064/artifacts/13098754944).
Extract and run installer/SeestarStudio-0.4.0-Setup.exe. Close the app before
upgrading. Existing Program Files installations can be upgraded in place.
If still using the per-user 0.2 preview, uninstall that version first.

Windows validation passed: nine tests (one OpenCL device test skipped because no
OpenCL device was available), packaged GUI crop/reset checks, Program Files
installation, desktop shortcut creation and installed GUI launch. Separately,
all ten tests passed with a software OpenCL device on Linux. NVIDIA hardware and
performance remain unvalidated. CPU fallback remains available. This preview
is unsigned. Source images are not included in the repository or download.

## Previous Windows download (0.3)
[Download the Windows preview ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/41344792997/artifacts/13099415398).
Extract it and run installer/SeestarStudio-0.3.0-Setup.exe. The Windows runner
passed all seven processing tests, packaged GUI launch, silent installation into
native Program Files, desktop shortcut creation, and installed GUI launch.
Taskbar pinning remains a manual Windows action. This preview is unsigned.

## Progress display
A progress bar above the activity log shows alignment percentage, processed
frames and frames remaining. Skipped frames count as processed, not accepted.
The bar restarts for the image-row combining phase. These are work counts, not
estimated time remaining. Completion reaches 100% when the result is available.

## Installation changes in 0.3
The 64-bit installer now defaults to C:\Program Files\Seestar Studio and
requires administrator approval. It offers an optional desktop shortcut and
creates a Start Menu shortcut. At the end, choose Launch, then right-click the
running app's taskbar icon and select Pin to taskbar. Windows manages pinning;
the installer does not change your taskbar automatically.

If upgrading from the per-user 0.2 preview, uninstall the old Seestar Studio
Preview through Windows Settings > Apps > Installed apps first. The new installer
does not automatically remove another user account's installation or shortcuts.
Your FITS files are not stored in the program folder.

## Previous preview download (0.2)
[Download the Windows preview ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/41343270976/artifacts/13097859357)
(about 261 MiB; GitHub sign-in may be required). Extract the ZIP, then open
installer/SeestarStudio-0.2.0-Setup.exe. Python is not required to use the app.
The download also includes a portable dist/SeestarStudio folder; keep that folder
intact if using SeestarStudio.exe directly.

All seven processing tests and the packaged GUI launch check passed on GitHub's
Windows Server runner. The installer compiled successfully. Installation and
interactive use on physical Windows 11 hardware remain untested. This is an
unsigned preview. No user images are included in this repository or the download.
The Actions artifact expires January 30, 2027; the source remains on this branch.

To build from source on Windows, install Python 3.12 x64 (including Python
Launcher), then double-click Build-Windows.cmd. Internet is needed to install
build dependencies. For an installer, install Inno Setup 6 and compile
installer.iss after building. GitHub Actions automates both builds.

## Use
Copy original FITS files from your Seestar to a local folder. Keep a backup.
For individual exposures: Add exposures, choose Bayer mode, Align and stack.
For a Seestar-generated stack: Open existing FITS stack, without stacking it again.
The app rejects stacks marked by STACKCNT or NCOMBINE in the exposure workflow.
Files without those markers still require you to choose the correct route.
Use one target, image size and exposure setting per batch. First exposure is the
reference; remove a poor first frame before stacking. Frames without enough stars
may be skipped; review the log and NCOMBINE for the actual accepted count.
Auto reads BAYERPAT; missing Bayer metadata displays 2D data as grayscale.
Do not guess a pattern based on a camera name. Validate using a real sample.
Odd Bayer offsets are rejected to avoid incorrect color reconstruction.

Adjust stretch, black percentile, saturation and optional Gaussian smoothing.
Background correction fits a smooth quadratic surface to robust grid samples.
It starts at zero: increase gradually and compare, since large faint nebulae
can be mistaken for background. Manual RGB gain sliders adjust color balance;
these are artistic controls, not photometric color calibration.
Compare shows the default stretch. Changes always start from linear data.
TIFF is full-resolution 16-bit RGB; PNG is 8-bit RGB. FITS preserves linear
32-bit RGB and does not bake in preview adjustments. Display preview is reduced;
export renders full size. A small brightness/color difference is possible because
preview percentiles are sampled at reduced resolution.

## Processing and limits
Star matching uses astroalign similarity transforms (translation, rotation, scale),
then 3-sigma clipped averaging. Border pixels exclude missing coverage. Uncovered
pixels are black. Temporary disk needs about 12 × width × height × frame count
bytes, so 100 1920×1080 frames need about 2.5 GB. RAM is not used for the full cube.
Cancellation takes effect between alignment calls and stack row blocks.
Export and single-frame load can briefly pause the GUI on large files.

This preview has no dark/flat/bias calibration, automatic frame quality ranking,
photometric color calibration, sharpening, project saving,
automatic updates. Background percentile subtraction is a
simple artistic adjustment and can suppress faint signal: keep linear FITS.
No AI-generated detail is added. Outlier rejection is limited with very few frames.
Alignment/interpolation and noise smoothing alter pixels; inspect results critically.
One S50 Pro RGB stack (299 × 20 seconds, 2160 × 3840) has passed import and
exact linear FITS roundtrip checks. Ten real S50 Pro GRBG raw exposures have also passed full-resolution alignment,
stacking and exact linear FITS roundtrip checks. Absolute color fidelity and
physical Windows hardware remain unvalidated.
Use a small batch first; keep acquisition files and compare to your Seestar output.

## Development
python -m pip install -r requirements.txt pytest
python -m pytest -q
python app.py

Libraries retain their respective licenses, including Qt/PySide6 LGPL terms.
Review bundled dependency licenses before redistribution. This project is
independent and is not affiliated with or endorsed by Seestar or ZWO.

