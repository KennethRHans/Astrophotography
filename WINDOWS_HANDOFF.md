# Windows handoff: preview and background-color updates

Source branch: `codex/macos-1.5`. Apply the shared processing changes selectively;
do not merge macOS packaging, sandbox access or Metal support into Windows.

## Changes to port

1. **Stable histogram during slider release.** Commit `d6d8aa5` uses one bounded
   source-pixel sample for normalization statistics, RGB histogram and clipping
   percentages across draft, settled and zoomed previews. Port `engine.py`,
   `preview_render.py` and their corresponding tests selectively. This commit
   precedes the new background/review changes and is already included in this
   macOS package. Full-resolution export normalization remains unchanged.
2. **Optional Background color neutralization.** New Advanced slider, 0–100%,
   default off. `engine.background_color_offsets` estimates a global sky cast
   from middle-low luminance pixels; `neutralize_background` removes an adjustable
   fraction before stretching and protected denoising. `preview_render.py` shares
   estimated offsets across preview sizes and includes strength in cache keys.
   Port the slider/settings and old-project/history migration in `app.py` too.
   Existing projects default to zero; undo/redo/reset/compare/project save work.
3. **Darker exposure review.** Add `review_stretch.py` and the `frame_review.py`
   worker/dialog changes. Auto stretch (darker sky) is the default; Standard
   stretch remains selectable. Estimate median/MAD from original pixels before
   resizing, preserve the full bright end and target approximately 16% sky
   luminance using linked-RGB midtones. Measurements and relative scores still
   use original linear data, unaffected by preview mode.

## Integration details

The Mac rendering settings append background neutralization at index 14, after
legacy Mac sky brightness at index 13. Windows may lack that legacy parameter:
adapt indices/signatures rather than copying a full settings tuple blindly.
Apply neutralization on CPU before passing data to the Windows GPU renderer;
verify GPU/CPU agreement and failure fallback. No new third-party dependency.
Carry over `tests/test_background_neutralization.py`, `tests/test_review_stretch.py`
and relevant live-preview tests, adapting platform-specific settings and fixtures.
`tests/test_metal.py` is Mac-only; use equivalent Windows GPU coverage.

## Color/export findings and remaining work

The supplied RGB stack decodes without swapping channels, and FITS save/reopen
preserves tested pixels exactly. Its red sky bias is present in the linear data;
the supplied raw Light also has a red bias. Another application's stretch can
emphasize it. These observations do not establish that all external-viewer color
behavior has the same cause or that debayering/color calibration is fully audited.

**This package does not add color-corrected linear FITS export.** Both Save stacked
FITS and FITS export retain linear source pixels without display adjustments,
including the new neutralization slider. TIFF/PNG/JPEG use the rendered image.
Do not silently bake nonlinear preview stretching into a file labeled linear.
An explicit calibrated/neutralized linear export needs a separate implementation.
Background neutralization is not photometric calibration; colored nebulosity can
bias it, and strong settings can increase shadow clipping. Default stays off.

Mixed 20/30-second captures explain the supplied stack's total exposure. The
stack currently copies EXPTIME from the reference while recording NCOMBINE and
TOTALEXP for all accepted inputs. Exposure normalization/weighting and clearer
mixed-exposure metadata are separate remaining work; they are not changed here.

## Validation to repeat on Windows

Run the shared suite, Windows GPU/CPU parity/fallback checks, and packaged smoke.
Manually check slider release/zoom, preview mode/full-resolution switching,
project migration/undo, and linear FITS versus rendered TIFF export. User-supplied
astronomy images and private diagnostic files are excluded from the repository.
