# Astro Studio for Seestar — preview 0.10

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

## Control visibility and image area (0.10)
The GPU checkbox has a white outline and a distinct white checkmark when on.
The image preview has a blue border and displays Processed picture will appear
here. until an image is loaded. Each slider value now follows the handle and is
centered directly beneath it, including when resetting or resizing the sidebar.
The value stays inside the control at the ends of the slider range.

## Astro Studio for Seestar (0.9)
The window/header, Windows app entry, executable, Start Menu and desktop shortcut
now use Astro Studio for Seestar. Windows executable metadata uses the new name.
GPU selection is in a dark blue bordered panel and reads Click to use GPU for
faster image adjustments. All three workflow sections have larger 20-pixel
bordered title banners. The replacement supplied logo is mirrored horizontally
for display and remains upright. Its original PNG is preserved.

New installs default to Program Files\Astro Studio for Seestar. Upgrades reuse
the existing installation directory and stable installer ID so Windows retains
one installed-app entry. The old executable and app-created old-name shortcuts
are removed. The new executable is AstroStudioForSeestar.exe. Re-pin the renamed
application if you previously pinned the old shortcut to the taskbar.

## Dark appearance and supplied artwork (0.8)
The application uses a black background and all three numbered steps use dark
blue panels, with bright text and controls. The disclaimer is aligned with the
app title, without its previous left indentation. The photo-selection control
is replaced by a fixed, bundled illustration supplied by the project owner.
The scientific processing and exported image colors are independent of the theme.

## Preview editing changes (0.7)
Crop edges and corner handles are dragged directly in the image. Drag inside a
selection to move it. The old Left/Right/Top/Bottom input fields have been removed.
Aspect ratios, guides, Apply crop and Restore full frame are retained.
Use +/−, Fit, 100% or the image's mouse wheel to zoom. Right- or middle-drag pans.
Zoom only changes the view; saved resolution is determined by the crop. At 100%
the preview uses native image pixels. Rulers and crop handles share image coordinates.

Brightness adjusts displayed exposure from -2 to +2 stops. Contrast adjusts
around a display midpoint of 0.18. Both work with CPU and GPU and reset to neutral.
Stretch and black level remain separate. FITS export still preserves linear data.
JPG/JPEG export produces an 8-bit, quality-95 image (lossy); TIFF/PNG/FITS remain.

Slider wheel sensitivity is narrowed horizontally by 10%: the outer 5% on each
side passes wheel events to the scrolling panel. Handle size remains unchanged.
GPU selection is now persistent at the top of the sidebar, above the scrolling
steps. Numbered sections have distinct colored borders/backgrounds and spacing.
The top includes Instructions For Use, indented step numbers and the requested
independent-project disclaimer under the name.

## Bundled telescope illustration
The project owner supplied the cartoon Seestar illustration displayed in the
header. It is included in the installer, so users do not need to choose a photo.
The original PNG is preserved; it is scaled only for display. The old photo
selector and its saved photo preference are no longer used.

## Guided workflow (0.6)
The controls are grouped under numbered headings matching the introduction:
1. Load or stack: add exposures and align/stack, or open an existing stack.
2. Adjust and crop: sliders and crop tools update the preview automatically.
3. Export: save TIFF/PNG with adjustments, or linear FITS data.
Step 2 and Step 3 enable when an image is ready. The view moves to Step 2 then;
Continue buttons scroll to the next section. The export button is numbered too.

## Easier adjustments and export names (0.5)
Slider handles are larger, with more space to click and a hover highlight.
Export starts with the FITS OBJECT name (C 56 becomes C56). Choose Linear FITS,
TIFF or PNG and the save dialog adds the corresponding extension. The name is
editable; missing object metadata falls back to the input filename. Names are
cleaned for Windows filename rules. Saved FITS remains linear data.

## Crop alignment and ratios (0.5)
Choose Free, Original, Square, 4:3, 3:2, 16:9 or the portrait equivalents.
Selecting a fixed ratio centers the largest matching crop inside the current
selection. Dragging keeps that ratio; edge pixel controls also maintain it.
Fixed ratios use exact whole-pixel multiples, so Original may move in larger
steps for unusual image dimensions. Choose Free for single-pixel control.
Thirds, center or a 10-by-10 grid plus pixel rulers help align the selection.
Rulers are pixel positions in the currently displayed frame. The crop label
shows exact width, height and top-left position. Guides never appear in exports.
To start a different ratio from the full image, choose Restore full frame.
These controls crop pixels; they do not resample the image to a smaller resolution.

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

## Latest Windows download (0.10)
[Download Astro Studio for Seestar 0.10](https://github.com/KennethRHans/Astrophotography/actions/runs/41367740262/artifacts/13107709307).
Close the app, extract and run installer/AstroStudioForSeestar-0.10.0-Setup.exe.
The GPU control now has a white checkbox outline and clear white checkmark.
The image area has a blue frame and an empty-state message. Slider values follow
the handles and remain below them during adjustment, reset and window resizing.
Local GUI checks covered minimum/midpoint/maximum values for every slider.
Windows tests, packaged launch/JPG export, fresh installation, desktop shortcut
creation and the upgrade-from-0.8 preservation check passed. This preview remains
unsigned; hardware OpenCL testing is unavailable on the Windows build runner.

## Previous Windows download (0.9)
[Download Astro Studio for Seestar](https://github.com/KennethRHans/Astrophotography/actions/runs/41365361806/artifacts/13106159783).
Close the app, extract and run installer/AstroStudioForSeestar-0.9.0-Setup.exe.
The new name appears in the header, window, Windows app list, executable metadata
and shortcuts. GPU selection has its own dark blue field with the requested
wording. Workflow headings are larger bordered title banners. The supplied
replacement logo is mirrored left-to-right at display time, remaining upright.

Windows tests, packaged launch, fresh installation and desktop shortcut checks
passed. An actual upgrade from the 0.8 installer also passed: the old executable
and shortcut were replaced, the Windows app entry was renamed, a user-created
file was preserved and the upgraded app launched. Existing installs reuse their
current directory. Remove any old taskbar pin and pin the renamed app again.
This preview is unsigned. Hardware OpenCL testing remains unavailable on the
Windows build runner; CPU fallback is retained.

## Previous Windows download (0.8)
[Download the Windows preview ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/41362474358/artifacts/13106225612).
Close the app, extract and run installer/SeestarStudio-0.8.0-Setup.exe.
This release includes the black application background, dark blue step panels,
brighter text, unindented disclaimer and the supplied cartoon bundled in the
header. The old photo-selection control is removed. Windows tests, packaged GUI
and JPEG export, Program Files installation, desktop shortcut, and installed-app
launch checks passed. Both packaged and installed checks require the bundled
artwork to be present and load successfully. This preview remains unsigned.

## Previous Windows download (0.7)
[Download the Windows preview ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/41358387168/artifacts/13103942956).
Close the app, extract and run installer/SeestarStudio-0.7.0-Setup.exe.
Windows processing/GUI tests, the packaged app including JPG save/reopen, Program
Files installation, desktop shortcut creation and installed-app launch passed.
Sixteen tests passed locally with software OpenCL. The Windows runner lacks an
OpenCL GPU, so its hardware comparison test is skipped. This preview is unsigned.
The stock telescope photograph is not bundled because the workspace blocks its
download; Choose photo supports a local photo and remembers the choice.

## Previous Windows download (0.6)
[Download the Windows preview ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/41349888827/artifacts/13100444750).
Close the app, extract and run installer/SeestarStudio-0.6.0-Setup.exe.
This release adds numbered Load, Adjust and Export sections, Continue buttons,
and automatic navigation to Adjust when an image becomes ready. GUI checks,
Windows processing tests, installation, desktop shortcut and installed launch
checks passed. The OpenCL hardware test remains skipped on the Windows runner.
This preview is unsigned.

## Previous Windows download (0.5)
[Download the Windows preview ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/41348457603/artifacts/13100307919).
Extract and run installer/SeestarStudio-0.5.0-Setup.exe with the app closed.
This includes crop guides, pixel rulers, ratio presets, larger slider handles
and object-based export filenames. Windows tests, packaged GUI checks, Program
Files installation, desktop shortcut and installed-app launch all passed.
The hardware OpenCL test remains skipped on the Windows runner without a GPU;
all twelve tests passed locally using software OpenCL. NVIDIA performance still
needs hardware validation. This preview is unsigned.

## Previous Windows download (0.4)
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

