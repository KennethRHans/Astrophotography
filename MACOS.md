# macOS 1.5.0 preview

This is a desktop preview with optional Metal image adjustments, not a Mac App Store submission.
Build on macOS with Python 3.12 and Xcode command line tools:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt 'pyinstaller>=6.16,<7'
python scripts/build_macos.py
dist/EasyAstroStudio.app/Contents/MacOS/EasyAstroStudio --smoke-test
```

The app is built for the build machine's architecture. The GitHub macOS
workflow runs the existing tests, builds the app, exercises the bundled GUI,
and uploads a ZIP. It does not publish a release or submit to Apple.
The bundle ID is `com.astrivanta.easyastrostudio` (registered Apple ID
`6832157430`, Team `XHRHMQ4A9G`). Distribution signing remains separate.
The build has only an ad hoc development signature; it is not notarized.

Use a runtime environment without pytest for packaging. If you installed pytest
to run the tests, run `python -m pip uninstall -y pytest` before building (the
workflow does this automatically after testing). Astropy's optional plotting
imports otherwise raise a pytest skip exception when matplotlib is absent,
which interrupts PyInstaller's isolated module collection. Excluding pytest
from the bundle alone does not remove it from the build environment.

## Metal image adjustments

The Mac GPU switch enables Metal stretch, saturation, brightness, contrast and
Gaussian smoothing. Alignment and stack combination remain on CPU. Background
modeling, normalization, percentiles and clipping masks also remain on CPU.
Windows continues to use its existing OpenCL backend.

The build compiles `macos/metal_bridge.m` with Apple's command line tools and
bundles the bridge and Metal shader source. Metal compiles the shaders locally
with fast math disabled. GPU buffers are transient; input data is preserved.
Metal initialization compares a small synthetic image against CPU results
(including smoothing) before enabling GPU mode. Failures, device loss or buffer
limits produce a CPU result through the existing fallback. A previous GPU
setting in a project is restored only if initialization succeeds.

The Mac workflow compiles the native bridge and runs numerical comparisons
when a Metal device is available. Hosted runners without Metal skip GPU
execution explicitly; they cannot establish numerical correctness or speed on
Apple Silicon hardware. The packaged smoke test also checks Metal when a device
is available, including inside App Sandbox.

On Apple Silicon, enable **Use Metal GPU for image adjustments** and check the
log for the device name. Compare changes, crop behavior, and exported images
with GPU off/on. Small previews may not be faster because allocation/dispatch
costs can dominate. Full-resolution exports and smoothing are the main cases
to measure. Stack-combining acceleration remains future work.

## Sandbox development build

Run `python scripts/build_macos.py --sandbox` to sign a separate development
build with App Sandbox. The workflow produces `EasyAstroStudio-macOS-sandbox`
alongside the regular preview. Neither is a distribution-signed App Store app.

The sandbox grants read/write access to files selected in native open/save
panels, plus outgoing networking for the user-initiated feedback form. It has
no blanket access to Pictures, Documents, or the home directory. Temporary
stack storage uses Foundation's app temporary directory. Project writes use
NSFileCoordinator and NSItemReplacementDirectory, then Foundation replacement,
so a failed archive write preserves the existing project without requiring
permission for arbitrary sibling files.

The Mac file dialogs use NSOpenPanel/NSSavePanel directly and retain the
original security-scoped NSURLs until the app quits. Astropy and NumPy use
Python file I/O rather than Qt's file engine, so Qt-managed selection alone
does not reliably authorize background workers. Each acquired scope is stopped
once at shutdown. The Mac export save panel includes a visible Format selector for TIFF, PNG,
JPEG, and linear FITS. Selecting a format updates the extension automatically.

Projects include their image and edits. On sandbox reopen, original exposure
paths remain provenance but are not repopulated as stack inputs. To re-stack,
select the originals again with Add exposures. No persistent file bookmarks
are needed for this workflow; opening the project grants its current session
access. Themes/settings now live in the sandbox container, so the first launch
may start with the default theme rather than the previous preview's preference.

CI checks the signed sandbox entitlement, verifies an unselected external file
cannot be read, then runs the bundled app's processing/project/export smoke
test in its container. This does not automate the native file panels.

On a real Mac, validate these additional sandbox cases before release:

1. Use native dialogs to import exposures outside the container, stack, cancel,
   and re-stack. Review/rate exposures as well.
2. Export each supported format into a chosen external folder.
3. Save a new `.astro` there, change an edit, and save over it. Try Save As too.
4. Quit/relaunch and select the project again. Edit, save over it, and export
   without having access to any original exposures. Re-select originals if
   you want to stack again.
5. Repeat with iCloud Drive/external volumes, full disk or read-only destinations,
   and confirm failed saves preserve the previous project.
6. Minimize the window and click the Dock icon; confirm the existing window
   returns with its image and unsaved edits. Repeat after switching to Finder.
7. Confirm theme persistence and feedback UI/network behavior (send only a
   deliberate test message). Check container storage cleanup after processing.

## Remaining App Store work

- Validate FITS import, alignment/stacking, edit previews, project round trips,
  cancellation, large stacks, and all exports on a physical Apple Silicon Mac.
- Add a proper macOS app icon, document type registration, and native menu polish.
- Audit dependencies and bundled license notices, including Qt distribution terms.
- Complete the sandbox development build's native file-panel checks above.
- Configure the real bundle ID, Apple distribution certificates, provisioning,
  sandbox entitlements, and signed embedded libraries/frameworks.
- Prepare privacy disclosures and App Store metadata, then validate and submit
  using Apple's tools. App Store acceptance has not been established.

Developer ID distribution outside the store uses a separate signing and
notarization process. Neither distribution path is implemented by this preview.

## Remembered preferences and sky brightness

The FITS import dialogs remember the folder from the last successful exposure
or finished-stack selection, across launches. Cancelling leaves it unchanged.
On macOS the saved path is a native-panel location hint, not a persistent file
permission; users still select their files each session.

GPU selection is an app preference. Opening a project does not override it.
If the remembered GPU cannot initialize, the app uses CPU and logs the failure;
the preference remains enabled for a future launch when the device is available.
Explicitly turning GPU off is remembered too.

Sky brightness adjusts darker rendered tones with a smooth luminance weight,
reducing the adjustment toward bright highlights. Zero is neutral; negative
values darken and positive values lighten. Values are hundredths of a stop.
It is not a sky/object mask and can affect faint nebulosity. Original linear
pixels and linear FITS exports are preserved. Preview and rendered exports use
the same curve after CPU or GPU adjustments. The control participates in reset,
undo, redo and project storage; older projects open with a neutral sky setting.
The small final curve runs on CPU with either rendering backend.

## Project and exposure-review toolbar

New Project appears immediately before Open project (also File → New Project,
Command-N). It prompts to Save, Discard or Cancel unsaved image edits. A save
must succeed before the project clears; cancelling the save dialog or a failed
save keeps the current work. A list of unprocessed exposures gets a separate
Discard/Cancel prompt. New Project retains theme, GPU and FITS-folder preferences.

Preview / rate exposures remains in Step 2, below Remove selected, and becomes
available after adding exposures. Review offers preview/full resolution, zoom/pan, batch
star detection, approximate FWHM, elongation, relative scoring within comparable
groups, sorting, highest-score selection, cancellation and Use as reference.
Using a reference moves that exposure to the first position without removing
other exposures or replacing the edited main image. Review analysis does not
automatically reject or remove exposures; use Remove selected in the main list.

## Windows 1.5.0 integration

Merged Windows source `133591e` into the Mac branch rather than converting the
Windows installer. Shared features include:

- Responsive coalesced draft/final preview rendering and bounded caches.
- JPG/PNG opening, full linear-stack FITS saves and completion sound preference.
- Manual labels, label styling/Undo/project storage and labeled JPG/PNG copies.
- Offline catalog projection using WCS, optional consent-based Astrometry.net
  source-list solving, and optional consent-based Gaia DR3 candidate matching.
- Embedded privacy policy, catalog attribution, clearer image/solve diagnostics.
- Auto sky, visible full crop reset, friendly slider units and Advanced controls.
- Midtones, monotone luminance curves and star-protected noise reduction.

Mac adaptations retained: Metal stretch/color/smoothing with CPU fallback,
App Sandbox entitlements, security-scoped native import/export panels,
coordinated atomic project saves, remembered folder/GPU/theme preferences,
Command shortcuts, New Project in the existing window and Dock restore.
The new stack/labeled-copy saves also use native scoped panels. The retained
Sky exposure control preserves the earlier Mac sky curve independently of the
Windows Shadows/sky brightness control. Older Mac and Windows project histories
are migrated with neutral defaults for new adjustments. Reference-output fixtures
compare Windows 1.5 rendering and the previous Mac sky-exposure rendering.

The online clients verify HTTPS using system roots plus bundled certifi roots,
so the sandboxed app does not depend on an external Python certificate directory.
No live image/source-list uploads are part of the automated tests. Packaged
smoke checks use an offline WCS/catalog and synthetic Gaia candidates; real
online solving/matching must be tested deliberately with the relevant consent.
Mac stack alignment/combining remain on CPU. The new tone and protected-noise
operations also run on CPU, matching Windows 1.5's processing order.

Before App Store submission, repeat import/stack, all exports, project/history
round trips, live slider/curve editing, labels, offline identification, optional
online services, and minimize/Dock restore on physical Apple Silicon hardware.
This remains an ad hoc signed development package, not a submission package.
