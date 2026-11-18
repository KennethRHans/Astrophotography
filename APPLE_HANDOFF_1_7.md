# Apple handoff — Object Reference (Windows 1.7.0)

## Scope and provenance

Runtime source commit: `14258de020e5cbfbdd862d7af10804f42af78a98` on
`KennethRHans/Astrophotography`, branch `codex/seestar-studio-preview`.
Validated Windows build: https://github.com/KennethRHans/Astrophotography/actions/runs/43742762788
Installer-only extraction: https://github.com/KennethRHans/Astrophotography/actions/runs/43744566720
Ken successfully ran the Windows update. Automated Windows validation: **115
passed, 13 skipped** (hardware-dependent cases), a real public M77 color request
inside Qt WebEngine, frozen-app offline checks, installed development and exact
Store-identity MSIX launches, Program Files installation and legacy upgrade.
These results do not establish macOS, Metal, sandbox, signing or notarization compatibility.

This handoff covers **Object Reference**, added after Windows 1.6.0. If the Apple
baseline still lacks the earlier robust stacking/quality weighting and selected-sky
background extraction, consult `windows-source/APPLE_HANDOFF_1_6.md` and its source
pins separately. Do not assume these earlier changes have already been ported.
Choose the next Apple version according to its current release history; do not
blindly copy the Windows version number or any Windows package identity.

## User-facing behavior to match

1. Add **Object Reference…** on the right of the project toolbar, beside Labels &
   Objects. Open a dock next to the editing preview. Share/tab the right dock area
   with Labels & Objects, or provide an equivalent Mac layout. A toolbar click
   must reveal an inactive tab in ONE click; clicking its active panel can hide it.
2. Show a separate reference, not another editable copy of the user's image.
   References never enter processing, crop coordinates, labels, Undo/Redo,
   dirty state, saved projects or exports. Moving sliders/cropping never fetches
   or changes the reference. Keep the view responsive.
3. Suggest the original image field from a valid complete WCS, preferring a saved
   solved header. Use center pixel `(width-1)/2, (height-1)/2` and square field
   width `max(scaleX*width,scaleY*height)` in degrees, clamped to 0.05–10 degrees
   and rounded to five decimals. This is a full original-field guide, not an
   automatically registered/cropped overlay.
4. Without usable WCS, look up OBJECT locally. Match catalog aliases separated
   by `/`, normalize spaces/punctuation/leading zeros, and handle C56 → NGC246.
   Examples: `M 77`, `NGC 1068`, `C56`. Use a 0.5-degree initial width and explain
   the suggestion came from the name, not a solved image. An unknown object gets
   blank coordinates, not an accidental M77 suggestion. Users can select listed
   targets or enter RA/Dec (degrees) and field width themselves.
5. A native **Use current image’s object / sky position** button refreshes the
   suggestion explicitly. New image/project loads reset permission and context;
   New Project clears the field. Switching/hiding the dock cancels local work and
   revokes online permission. Busy load/stack/project operations disable the panel
   and cancel work. Closing the app cleans up its browser page before its profile.
6. Online loading requires the consent checkbox AND **Load online reference**.
   Opening the panel, selecting a target, editing the image and theme changes
   must not fetch anything. No API key/account is needed.
7. Default: DSS2 color via automatic same-survey mirror fallback. Manual mirror
   selection is available. An optional checked fallback tries NASA SkyView DSS2
   Red, clearly labeled **grayscale**, when color fails. Allow cancel and show
   readable status, errors and request details. A guide is not predicted output,
   recovered signal or a photometric color calibration.
8. **Open local reference…** accepts JPG/JPEG/PNG/WebP in memory without upload.
   Rotate 90°, flip horizontally, reset orientation and clear affect the guide
   only. State that scale/orientation are not registered to the user's image.
9. Save (default checked) retains up to five downloaded COLOR references locally,
   with coordinate/field keys, source captions/credits and ISO save timestamps.
   **Load saved reference (offline)** needs no consent/network. Clear removes
   only this feature's cache. Local reference/working files are never added by
   the color-cache code. Storage quota failure is a warning, not loss of the
   loaded image. Keep the original application's theme choices usable.

## Source map

All paths below are under windows-source/:

| File | Purpose |
| --- | --- |
| reference_view.py | Pointing suggestion, lazy Qt WebEngine panel, request gate, native bridge, profile and shutdown |
| assets/reference/reference.template.html | Reference-only UI, HiPS renderer iframe, mirror fallback, cache and orientation |
| assets/reference/reference.html | Prepared HTML with the pinned unmodified renderer embedded |
| assets/reference/vendor/aladin-lite/ | Unmodified JS, notices, exact corresponding source ZIP and SOURCE.txt |
| scripts/prepare_reference_assets.py | Reproducible pinned bundling and integrity verification |
| app.py | Search toggle_reference, toggle_labels, refresh_reference_context, set_theme, loaded, new_project, update_actions, project completion and closeEvent |
| object_identification.py | Strict celestial_wcs validation and bundled catalog loader (reuse Mac equivalents where present) |
| assets/catalogs/ | Existing local catalog and its separate attribution/licenses |
| reference_smoke.py | Offline packaged panel, cancellation and pixels/project-state isolation assertions |
| scripts/check_reference_live.py | Explicit public M77 live test; never reads a user's image |
| tests/test_reference_view.py | Service boundaries, WCS/name fallback and one-click tab switching |
| tests/test_gaia.py | Explicit UTF-8 policy test fix; preserve platform-independent decoding |
| PRIVACY.md, assets/privacy_policy.md | Matching public and in-app policy with Object Reference section |
| assets/reference/README.md | Renderer/survey attribution and replacement/build guidance |
| .github/workflows/windows.yml | Windows verification evidence and test-only software WebGL configuration |

The full source snapshot is for inspection and dependency context. Its Windows
installer, MSIX, identity, OpenCL and CI files are NOT an Apple replacement.

## Renderer and service details — preserve the tested choices

The current Apple source is Python/PySide6, so first evaluate Qt WebEngine there.
If Apple packaging requires a native WKWebView instead, adapt the small native
bridge and security controls; do not pretend the existing Qt bridge runs unchanged.

- Bundle Aladin Lite **3.8.2**, exact source commit
  `3476c535e682336d1bde3dac98cf7db54fcc749f`. The preparation script verifies the
  official npm SHA-512 before embedding its UNMODIFIED module in the HTML.
  Keep the separate module, licenses and complete matching source ZIP. There is
  no runtime JS CDN or survey-registry requirement. Read all upstream notices:
  LGPL v3 files are present; npm package metadata also says GPL-3.0.
- Load the prepared HTML as a LOCAL FILE. Qt setHtml uses a data URL with a size
  limit below this prepared page. Inject Qt's bundled qwebchannel.js into the
  main world at DocumentCreation; do not rely on a remote script. Set
  AA_ShareOpenGLContexts before QApplication for lazy browser creation.
- Create browser resources lazily. Use a dedicated local persistent profile,
  in-memory HTTP cache, no persistent cookies, and no download/pop-up/permission
  grants. Never allow arbitrary top-level navigation or file access. The request
  interceptor starts with HTTPS blocked and is enabled only after consent.
- Native context sent to the page is limited to name, RA, Dec, field width and a
  UI hint. The dedicated renderer receives only fixed mirror metadata, sky
  coordinates, width, a random token and the bundled library. NEVER pass pixels,
  filenames/paths, complete FITS headers, Astrometry API keys or native file APIs.
- Use the tested visible SAME-ORIGIN iframe. An opaque sandbox or offscreen
  iframe caused initialization/rAF hangs in the prototype. Verify message source,
  random token and generation. Restrict network access natively AND in CSP and
  renderer fetch guards. This iframe contains only bundled trusted renderer code;
  never load arbitrary web pages into it or expose extra native bridge methods.
- Construct `A.HiPS(mirrorURL, {imgFormat:'jpeg',requestCredentials:'omit',...})`
  and fetch FULL properties from that URL. Incomplete manually supplied metadata
  caused setup failures and unwanted registry fallback. Unknown renderer HTTP
  origins must stop the attempt, not enter a registry retry loop.
- Explicitly call gotoRaDec and setFoV after creating the view. Validate center
  (including RA wrap) and field width before accepting a reference.
- Confirm full JPEG tile responses, active requests settled and a quiet period
  before exporting. Keep the tested per-mirror/initialization timeouts. Validate
  nonblank image data, expected center/field and no failed tile responses. Never
  call a black placeholder success. getViewDataURL can return PNG despite asking
  for JPEG: accept validated PNG OR JPEG data URLs, with the size bound retained.
- Preserve Aladin's logo (`logo:true`), survey/provider captions and source links.
  Remove the renderer iframe after completion/cancel to stop its work.
- Native request allowlist is HTTPS GET/HEAD/OPTIONS to fixed path prefixes only.
  Keep the ESA CDN redirect allowance. Cookies are omitted in renderer fetches.
  Source/docs open in the user's browser only after a click; don't embed them.

Automatic DSS2 COLOR order (same survey, not different color products):

1. MAST: https://stpubdata.s3.us-east-1.amazonaws.com/mast/skybackgrounds/DSSColor
2. CSIRO: https://casda.csiro.au/hips/DSS2/color
3. China-VO: https://hips.china-vo.org/m/CDS_P_DSS2_color
4. ESA: https://skies.esac.esa.int/DSSColor
   (redirect may use https://cdn.skies.esac.esa.int/DSSColor)

NASA grayscale uses HTTPS skyview.gsfc.nasa.gov/current/cgi/runquery.pl with
Position=RA,Dec; Survey=DSS2 Red; Return=JPEG; Pixels=512; Size=field;
Projection=Tan; Coordinates=J2000; Scaling=Log. The older CDS HiPS2FITS cutout
endpoint failed during this work and is not a required color service.
Service availability can change; test at port time.

## GPU and Apple-specific work

The reference renderer uses browser **WebGL2**, independently of the application's
Use GPU switch for stack/adjustment processing. On supported machines it can use
the GPU; actual graphics selection is controlled by the browser/OS/driver. It is
not an OpenCL or Metal processing-kernel port. Preserve Apple's Metal code and the
existing GPU switch semantics. If WebGL2 is unavailable, offer grayscale, cached
or local references. Do NOT ship --no-sandbox, --ignore-gpu-blocklist,
--enable-unsafe-swiftshader, QTWEBENGINE_DISABLE_SANDBOX or hosted-runner software
flags as production defaults. Windows CI used software WebGL ONLY because its VM
has no supported GPU. Verify default rendering on real Apple hardware.

For PySide6/Qt WebEngine, inspect supported macOS/architecture/Qt/Python versions,
PyInstaller hooks and the added helper framework/resources/locales. Validate
QtWebEngineProcess/helper signing, hardened runtime and notarization with the
current Apple toolchain. Do not copy Windows flags or guess broad entitlements.
For an App Sandbox target, confirm outbound network permission, profile/cache
storage in the app's permitted container, browser-helper behavior, and local
reference file access through the existing security-scoped/native file chooser.
Qt's HTML file picker may need to be replaced with that native chooser. Process
local reference images in memory and preserve access lifetime; do not disable
sandboxing or weaken existing bookmarks to make it work. Confirm unsigned dev,
signed/notarized and App Store sandbox variants separately where applicable.

If using WKWebView, replace QWebChannel with a narrowly scoped message handler,
validate main-frame messages, preserve consent/request gating with controls that
actually cover subresources, local persistence/cancel behavior, and constrain file
read access. Maintain CSP. A navigation delegate alone is not a complete network
interceptor. Verify local module/WASM/HiPS CORS and cache behavior on WebKit rather
than assuming Chromium success transfers.

## Privacy and attribution

Port the Object Reference section from the bundled/public policy together, with
Mac-appropriate cache locations/wording. No online requests on opening/hovering,
no working-image uploads and no background searches. Disclose selected sky
position/field, survey requests, IP/connection information and the mirror/NASA
providers. Reset permission on hide/new image/project; cancel cannot withdraw
requests already received. Preserve explicit opt-in, cache controls and local-only
reference handling. Recheck actual behavior if the browser backend changes.
Keep the public policy synchronized before releasing a Mac build. Do not change
unrelated privacy terms, legal identity or feedback retention without instruction.

Survey credit: DSS / STScI / NASA; color HiPS preparation CDS / CNRS / Université
de Strasbourg. Mirror names accompany results. Aladin Lite (CDS) logo/credit and
its supplied licenses/source remain bundled. Existing catalog attribution is
separate. Check applicable terms before redistributing survey imagery.

## Apple acceptance checklist — run when implementation is authorized

- [ ] Confirm current Apple branch/version and earlier 1.6 processing changes.
- [ ] Opening panel, selecting target, theme changes and slider/crop edits produce
      zero reference network requests before consent and Load.
- [ ] Real public M77: RA 40.6696°, Dec -0.0133°, field 0.5°. Confirm a nonblank
      color image and correct field with default graphics settings on Apple.
- [ ] Block first mirror: same-survey fallback; all mirrors fail: optional NASA
      grayscale or clear error; no false success/black image.
- [ ] Revoke consent/cancel/close/hide/switch tabs/new image while loading: no stale
      result, old frame removed, no crash. One-click toolbar switching both ways.
- [ ] Good WCS, missing WCS/known alias, unknown object, RA wrap, bad/blank coords,
      field limits; no silent M77 default and no automatic solve/upload.
- [ ] Save color, restart app OFFLINE, load same field with consent unchecked;
      clear only reference cache; handle full/unavailable storage gracefully.
- [ ] Open local reference through Apple's sandbox/native access flow; rotate,
      flip, reset and clear without changing source files or editing state.
- [ ] Theme/light/dark, Retina/resizing, floating/docked layouts and keyboard use.
- [ ] Before/after operations compare original pixel arrays, project signature,
      crop, labels, Undo/Redo and exported files: reference never changes them.
- [ ] Confirm default WebGL GPU behavior; GPU switch still controls only existing
      processing. Verify graceful alternatives on unsupported hardware.
- [ ] Test real packaged app without network: prepared HTML, module/WASM, native
      bridge, helper resources and licenses load. No missing CDN dependency.
- [ ] Close page BEFORE browser profile; repeated open/close/launch is stable.
- [ ] Check signatures/notarization/sandbox and supported CPU architectures on Mac.
- [ ] Run existing Apple processing, Metal/CPU fallback, file access, project,
      preview, export and locale tests. Report skipped/unverified cases clearly.
- [ ] Match public and bundled UTF-8 policy. Review new network behavior and source
      attribution. Build/release only after Ken requests that step.

Do not treat this checklist or Windows success as approval to publish an Apple
update. This package was requested for a later handoff only.
