# Seestar Studio — preview 0.2

A Windows desktop prototype for Seestar color FITS exposures and existing stacks.
Built for Windows 11; CPU processing. The RTX 5070 is not used yet.

## Download status
This is a source preview, not a tested Windows installer. Build on Windows with
Python 3.12 x64 installed (python.org installer, include Python Launcher).
Double-click Build-Windows.cmd. Internet is needed to install build dependencies.
Then open dist\SeestarStudio\SeestarStudio.exe. The entire SeestarStudio folder
can be copied to another computer; Python is not required there.
For an installer, install Inno Setup 6 and compile installer.iss after building.
The included GitHub Actions workflow performs tests and produces both artifacts
when the project is uploaded to a GitHub repository. No repository is published
and no Windows build has been run by providing these files.

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
GPU acceleration or automatic updates. Background percentile subtraction is a
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
