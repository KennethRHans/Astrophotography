# macOS preview

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
The bundle identifier is provisional and must match the eventual Apple record.
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
