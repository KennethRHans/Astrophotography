# Easy Astro Studio — 1.3.0 Store update

A Windows GUI for aligning and stacking color FITS exposures, editing existing
FITS stacks and exporting images. Built for Windows 11 x64; Python is not needed
when using the installer. Previously named Astro Studio for Seestar.

## Automatic catalog labels (1.3.0)

Open **Labels & Objects… → Identify objects…**. With a complete RA/Dec FITS WCS
or saved-project solution, the offline method projects bundled catalog positions
onto the full original image, then filters to the current applied crop. Position
matching supports rotation, mirroring and SIP distortion. Header placeholders,
missing pixel scales and external distortion-table dependencies are rejected.
Existing headers are assumed to describe the actual image; the app cannot
prove their accuracy without a new solve. Check labels against visible stars.

Without valid sky coordinates, choose the online Astrometry.net method, obtain
your own API key at https://nova.astrometry.net/api_help, enter it in the masked
field, check the explicit consent box and click Identify. Local SEP extraction
finds up to 2,000 stars in a bounded sample and maps their positions back to the
original full-resolution pixel system. HTTPS sends the positions/rank, image
size and solver options, not image pixels, paths, filenames or FITS headers.
Login sends your key only to the service; it is never written to settings,
projects or logs. The app requests private visibility and restrictive reuse.
Astrometry.net may retain requests; cancellation cannot recall uploaded data.
The GUI stays responsive, polls at five-second intervals, limits each network
request to 20 seconds and waits at most ten minutes for a solution.

Review the results before **Add selected labels**. Filter Galaxies, Nebulae,
Clusters and Stars; set the faintest catalog magnitude, unknown-magnitude policy
and maximum results (1–300). Check individual rows or Select all/none. Selected
matches become editable circle/text labels with the current color and size,
with duplicate prevention by catalog ID and a 500-label project limit. Existing
manual labels are preserved. Undo removes a batch; projects save both labels
and the sky solution so future filtering can work offline. A solved identification
WCS is cached in the project; original FITS headers and source pixels are not
rewritten by identification. Crop/export follows the existing annotation path.

Bundled data: reduced OpenNGC deep-sky and HYG v4.1 bright-star catalogs, 15,162
entries total (3,065 stars). Attribution, data source details and CC BY-SA 4.0
license are in `assets/catalogs`. The catalogs cover selected named/bright stars
and NGC/IC objects, not every object. Magnitudes can be approximate or absent;
HYG proper motions are applied when DATE-OBS is valid. These are catalog
positions, not pixel-level detection or proof that a faint object is visible.

The online protocol is tested with simulated login, queued/solving jobs,
private source-list submission, WCS download, cancellation and error responses.
No live authenticated solve or private user-data upload was performed during
development. All 66 local tests passed, including sky projection through
rotation/mirroring/SIP, real-catalog matching, source extraction, HTTPS request
encoding, redacted errors, opt-in, cancellation, duplicate handling and project
reopening. The application smoke test also passed. Full Windows package
validation is in progress for 1.3.0.0.

## Labels, image opening and stack completion (1.2.0)

The far-right **Labels & Objects…** toolbar button opens a manual annotation
panel when an image is loaded. Choose Text, Arrow or Circle, enter a caption,
color and text size, then choose Place on image and click the target. Select an
entry to edit its appearance or remove it. Escape cancels placement. Show labels
controls visibility. Labels follow original pixel coordinates through crop and
restore, support undo/redo, and are saved in .astro projects. Old projects open
with no labels. At most 500 annotations are supported. Automatic identification
and plate solving are planned, not included in this release.

**Open image or FITS stack…** accepts FIT/FITS, JPG/JPEG and PNG. Raster inputs
honor EXIF orientation and open with neutral stretch/black settings. Their
imported display-encoded RGB data is not linear sensor data. Default raster
rendering preserves RGB values, including zero-valued channels. Bayer patterns
apply only to 2D FITS. PNG/JPEG import and labeled export use 8-bit RGB; these
are not archival high-bit-depth or color-managed workflows.

Section 5 adds **Save stacked FITS…** for the full original aligned stack,
including exposure metadata, without display adjustments, labels or cropping.
It is enabled for FITS stacks with multiple exposures. Existing general FITS
export still saves the current crop without display adjustments or labels.
**Export labeled image…** saves a separate PNG/JPG with visible annotations
at the current crop's full resolution. Original files and linear arrays are
unchanged; normal exports remain free of annotations.

Successful alignment/stacking reports combined and skipped exposure counts,
requests taskbar attention and plays the Windows system notification sound.
Settings offers **Play sound when stacking finishes**, saved per user. Opening
a single image, failed operations and cancellation do not play the chime.
System volume and sound-scheme settings control whether a sound is audible.
This release needs no online solver, account or extra Store capabilities.

All 56 local tests passed. Windows tests, packaged GUI smoke checks (including
JPG opening and labeled PNG export), MakePRI/MakeAppx validation and exact
Microsoft Store identity installation/activation passed for version 1.2.0.0.

[Download the 1.2.0 Store upload ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/42445610275/artifacts/13603766860).
Extract it and upload `EasyAstroStudio-1.2.0-x64-Store-UNSIGNED.msix` to the
Packages page of the next Partner Center submission. Microsoft signs accepted
Store packages. The unsigned package is for Store upload, not direct installation.

## Session tools, sky background and responsive previews (1.1.0)

New project appears before Open project in the toolbar and File menu (Ctrl+N).
It offers Save/Discard/Cancel for unsaved edits and clears the image, exposure
list, history, crop and adjustment state. Original files, theme, Bayer choice,
last FITS folder and GPU preference are preserved. New project is unavailable
while stacking or project I/O is active.

Add exposures and Open existing FITS stack start in the last selected FITS
folder. Cancelled file dialogs do not overwrite it. An unavailable folder falls
back to an existing parent or Documents. GPU selection is remembered per user;
a driver/device failure uses CPU without forgetting the saved preference for a
future start. The global preference takes priority over older projects' GPU view
flag. An older project's enabled GPU choice can seed the preference if none has
yet been saved. Windows settings are stored locally and do not upload data.

Sky background % darkens or lightens shadows while applying less change to
brighter tones. It is a display adjustment, not a semantic sky/object separation;
faint nebulosity can change too. Zero is neutral. TIFF/PNG/JPEG reflect it; linear
FITS export does not bake it in. Old .astro files gain a neutral Sky setting on
load, including their undo history. New files retain the existing project format.

Slider previews run in a background worker with one active render and one latest
request. Dragging uses a reduced preview (up to 1280 pixels per side), then the
current zoom's resolution is restored on release. Resized inputs and percentile
normalization are reused until their inputs change. Crop/reset/initial-load
operations retain immediate preview behavior. GPU render calls are serialized
with export to avoid overlapping use of the same OpenCL kernels. The exposure
list signature is cached; combining progress/log updates are throttled and the
visible log keeps at most 2,000 lines. Preview work from a previous project is
ignored after New project. These changes improve UI responsiveness, not the
underlying speed of CPU alignment, storage or every processing phase.

All 51 local tests passed, including pending-preview safety, latest-request
coalescing/UI heartbeats, project save protection, old-project migration,
preferences, cache reuse and CPU/software-OpenCL sky-adjustment comparisons.
A Linux CPU check using a full-resolution 2160×3840 Seestar stack and 546
exposure-list entries measured a maximum slider-handler duration of 0.76 ms,
with the UI heartbeat continuing through the render and the latest settings
shown correctly. This is a UI responsiveness check, not a Windows/RTX 5070
stacking-speed guarantee. A shared OpenCL processor also passed concurrent
background-preview/export numeric comparisons on software OpenCL.
Windows tests, packaged application smoke checks, MakePRI/MakeAppx validation,
archive identity checks and installation/activation with the exact Microsoft
Store identity passed for version 1.1.0.0.

[Download the 1.1.0 Store upload ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/42398766275/artifacts/13584538658).
Extract it and upload `EasyAstroStudio-1.1.0-x64-Store-UNSIGNED.msix` to the
Packages page of the next Partner Center submission. Microsoft signs accepted
Store packages. This source package is intended for Store upload.

## Privacy policy (1.0.1)

[Easy Astro Studio Privacy Policy](PRIVACY.md) is published at:
https://github.com/KennethRHans/Astrophotography/blob/codex/seestar-studio-preview/PRIVACY.md

Public privacy/deletion contact: starsandfits@gmail.com. The policy describes
local image/project processing, optional Formspree submissions, external links,
provider processing, retention and user requests. No fixed automatic feedback
deletion period is claimed. Settings, About and the feedback form link to the
policy; the feedback dialog explains what Send transmits before submission.
The updated package is version 1.0.1.0. All 43 local tests passed. Windows
tests, manifest/archive identity validation, installed MSIX activation,
processing/export/project/theme checks and legacy installation/upgrade checks
passed. No live feedback was sent while testing the privacy links.

[Download the updated Store upload ZIP](https://github.com/KennethRHans/Astrophotography/actions/runs/41851417254/artifacts/13336166867).
Extract it and upload `EasyAstroStudio-1.0.1-x64-Store-UNSIGNED.msix` to the
submission's Packages section. Put the public policy URL above into the Store
privacy-policy field. Microsoft certification and publication remain pending.

## Microsoft Store preparation (1.0)

The app now has a native x64 MSIX build path using MakeAppx/MakePRI and the
existing approved logo for Windows icons. It retains full-trust desktop file
and OpenCL access without requesting administrator elevation. Package-aware
launch keeps the Store-assigned taskbar identity; the separate EXE build keeps
its existing identity. Version 1.0.0 maps to Store package version 1.0.0.0.

See [Store submission guide](store/SUBMISSION-GUIDE.md),
[listing draft](store/LISTING-DRAFT.md) and
[privacy draft for owner review](store/PRIVACY-DRAFT.md).
The provided Partner Center identity is configured in store/identity.json:
Astrivanta.EasyAstroStudio, publisher
CN=D1BC40AB-66EF-44E8-9901-3DF6CBECAF25, publisher display name Astrivanta.
CI builds the Store candidate using that identity, verifies the actual archive
and separately tests a disposable signed copy under the exact package identity.
The Store-Upload artifact contains only the original unsigned submission
candidate and validation reports. Development test packages remain separate.
Nothing has been submitted or published to the Store.

[Download the Store upload package](https://github.com/KennethRHans/Astrophotography/actions/runs/41717811587/artifacts/13270319227).
Extract the ZIP and upload `EasyAstroStudio-1.0.0-x64-Store-UNSIGNED.msix` in
Partner Center > Packages. This artifact contains no development package.
The archive's Name, Publisher, PublisherDisplayName, display name, x64
architecture and 1.0.0.0 version were verified against store/identity.json.
The exact Store identity also passed installed activation, local processing,
project/export and saved-theme checks using a disposable CI-signed copy. The
original upload candidate is unsigned for Microsoft Store signing. All 42 local
tests passed. Store listing/privacy completion and Microsoft certification are
still pending; a validated upload is not a published release.

All 41 local tests passed. Windows tests, MakePRI/MakeAppx validation, actual
MSIX installation, package-identity activation, CPU combining, FITS/project/JPEG
checks and theme persistence across two installed launches passed. The test
certificate and package registration were removed afterwards. Legacy installer
installation/shortcut/upgrade checks also passed. This does not replace Microsoft
Store certification, Windows App Certification Kit results or a physical Windows
11/OpenCL GPU test.

[Download the MSIX preparation kit](https://github.com/KennethRHans/Astrophotography/actions/runs/41711291933/artifacts/13267949775).
It contains a development-identity unsigned package and submission drafts, not a
public installer or a package ready to upload under your Store account. Use the
source checkout on this branch for building; the kit alone is not a full source
distribution. The provided identity is now configured for the separate Store upload build.
Review and publish the privacy policy and complete
the remaining listing/certification steps in the guide. Nothing is live yet.

## Themes and planner link (0.16)

Settings > Theme offers Dark (the existing black/blue default), Light,
Midnight Purple, Forest Green, Slate and Warm Copper. Changes apply immediately
to the app, menus and dialogs and are remembered per Windows user across
restarts/upgrades. Invalid saved theme names fall back to Dark. Theme selection
is an application preference, separate from .astro projects and undo history.

The astronomical image/preview stays on black for consistent viewing, and
changing a theme does not change image pixels or adjustment settings.
The footer now opens https://planner.astrivanta.com and displays that address.
Donation and feedback destinations remain the same.

## Five-step workflow and sortable review (0.15)

Instructions and the five matching blue sections are now:
1. Set Bayer Pattern (Equipment-based)
2. Load FITS Stack or Multiple Files to Stack
3. Align and Stack Exposures
4. Adjust and Crop
5. Export

Step 2 separates Open existing FITS stack and Add exposures with a centered OR.
Existing stacks skip step 3 and open in step 4. Continue buttons use the new
numbers. Alignment is available after adding at least two individual exposures.
Bayer help still recommends Auto and explains that the stored camera/file
orientation determines the pattern.

Mouse-wheel events no longer change adjustment sliders, even when focused;
they pass through for panel scrolling. Dragging, clicking and keyboard arrows
still adjust sliders. Image-wheel zoom remains available.

Every exposure-review column sorts by clicking its heading; click again to
reverse direction. Score, star count, FWHM and elongation use numeric ordering.
Updates during/after analysis keep all values with their filename and preserve
the selected frame. Sorting the review table does not reorder the main exposure
list; Use as reference remains the explicit operation that changes its first file.

The community footer background is black; its buttons, banner and border remain.

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
Plan tonight's observing at https://planner.astrivanta.com and opens the default browser.

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

[Download Easy Astro Studio 0.16](https://github.com/KennethRHans/Astrophotography/actions/runs/41676523870/artifacts/13250841921).
Close the app, extract the ZIP and run
`installer/EasyAstroStudio-0.16.0-Setup.exe`.
Use Settings > Theme to select and save an appearance. All 39 local tests passed,
including persistence, invalid-preference fallback and unchanged image/history
across all themes. Light and colored themes passed local visual checks.
Windows tests, packaged launch/review/project/export checks, installation,
desktop shortcut and upgrade preservation checks passed. This preview remains
unsigned; OpenCL device comparisons skip on the Windows runner.

Previous version:

[Download Easy Astro Studio 0.15](https://github.com/KennethRHans/Astrophotography/actions/runs/41545469531/artifacts/13188367688).
Close the app, extract the ZIP and run
`installer/EasyAstroStudio-0.15.0-Setup.exe`.
All 38 local tests passed, including numeric/text sorting in both directions,
selection/row integrity during updates and wheel-disabled sliders. Windows tests,
packaged launch/exposure review/project/export checks, installation, desktop
shortcut, installed launch and upgrade with user-file preservation passed.
This remains an unsigned preview; OpenCL device tests skip on the Windows runner.

Previous version:

[Download Easy Astro Studio 0.14](https://github.com/KennethRHans/Astrophotography/actions/runs/41536718015/artifacts/13184763084).
Close the app, extract the ZIP and run
`installer/EasyAstroStudio-0.14.0-Setup.exe`.
All 37 local tests passed. Windows tests, packaged exposure preview/analysis,
project/JPEG checks, Program Files installation, desktop shortcut, installed
launch and actual upgrade with user-file preservation checks passed. The runner
has no OpenCL device, so hardware comparisons skip there. This remains an
unsigned preview.

Previous version:

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

All 39 local tests passed, including software OpenCL comparisons for 2–512
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
