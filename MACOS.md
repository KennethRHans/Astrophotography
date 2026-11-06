# macOS preview

This is a CPU-only desktop preview, not a Mac App Store submission.
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

GPU controls are disabled on macOS for this preview. Existing OpenCL stacking
requires double precision; a future Apple GPU backend needs separate numerical
validation. Windows GPU support remains available.

## Before App Store submission

- Validate FITS import, alignment/stacking, edit previews, project round trips,
  cancellation, large stacks, and all exports on a physical Apple Silicon Mac.
- Add a proper macOS app icon, document type registration, and native menu polish.
- Audit dependencies and bundled license notices, including Qt distribution terms.
- Implement and test App Sandbox file access, including access to source files
  reopened through saved projects (security-scoped bookmarks if needed).
- Validate temporary stack storage and atomic project saves inside the sandbox.
- Configure the real bundle ID, Apple distribution certificates, provisioning,
  sandbox entitlements, and signed embedded libraries/frameworks.
- Prepare privacy disclosures and App Store metadata, then validate and submit
  using Apple's tools. App Store acceptance has not been established.

Developer ID distribution outside the store uses a separate signing and
notarization process. Neither distribution path is implemented by this preview.
