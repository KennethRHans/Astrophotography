# Easy Astro Studio 1.7.1 — Windows release

## What's new

New FITS images open with an adaptive linked-RGB stretch for a darker, more useful
starting preview. Opening preview in step 4 lets you switch to the previous
Legacy view. Reset, Compare and Undo/Redo work with the selected opening transfer.
Object Reference, including color survey mirrors and offline/local references,
remains available.

## Existing preferences and projects

The regular application uses its established Astrivanta/EasyAstroStudio preference
namespace and normal application/browser storage identity. GPU selection, last
input folder, theme and other saved production preferences continue to apply.
The portable test's separate preferences are not imported.

Existing projects lacking an adaptive transfer keep their saved Legacy appearance,
slider settings, crop and history. Adaptive projects store the transfer in current
and Undo states, so reopening/cropping/zooming does not re-estimate the opening
look. They use .astro format 2 and require version 1.7.1 or later. All-Legacy
histories can remain format 1. Keep separate copies if you still use version 1.7.0
or another application that only supports format 1. Projects from the 1.7.1
portable test are supported here.

## Image data and controls

The opening transfer is display processing. It changes preview and raster exports
(TIFF/PNG/JPG), not original files, stacking data, Save stacked FITS or linear
FITS export. Imported JPG/PNG images retain display-encoded handling.
Adaptive starts extra Stretch and additional percentile Black point at zero;
its base shared black point/midtones transfer is already active. Mode changes
reset Stretch, Black point, Exposure and Shadows while preserving other edits;
Undo restores the prior state. Background extraction is still separately chosen.
The 20% sky estimate can be biased by gradients/extended nebulosity and can clip
some shadows. It is not photometric color calibration or a guarantee that every
faint structure is visible.

Adaptive preparation is shared by CPU and the existing GPU path; the established
CPU fallback remains. Object Reference uses WebGL2 separately from the image
processing GPU switch. Adaptive opening introduces no network requests, accounts
or API keys. Existing Reference consent/privacy behavior is unchanged.

## Packaging

The regular Program Files installer and unsigned Microsoft Store MSIX retain the
existing app/Store identity. Microsoft signs the accepted Store submission; upload
the unsigned .msix from the Store upload ZIP to Partner Center. The installer-only
ZIP avoids duplicating the portable payload in the download.

## Suggested Store 'What's new'

FITS files now open with an adaptive stretch for a darker, more balanced starting
view. Switch between Adaptive and Legacy previews while editing. Existing saved
projects retain their previous appearance, and new projects remember the selected
opening transfer. Object Reference and offline references remain available.
