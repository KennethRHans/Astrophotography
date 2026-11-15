# Object Reference assets

The installed panel uses reference.html, built from reference.template.html by
python scripts/prepare_reference_assets.py. This bundles the unmodified Aladin
Lite 3.8.2 renderer (CDS) and its exact corresponding source archive, LICENSE,
COPYING and COPYING.LESSER under vendor/aladin-lite. See SOURCE.txt for the pin.
Aladin Lite is distributed under LGPL v3; the npm package metadata also says
GPL-3.0. All upstream notices are preserved. You may replace the module and
rebuild the HTML using the preparation script while respecting these licenses.
The library is dynamically imported as a separate unmodified JavaScript module.
Its logo is retained in reference images.

Survey data: Digitized Sky Survey / STScI / NASA, color HiPS preparation by
CDS / CNRS / Université de Strasbourg. Mirrors: MAST, CSIRO, China-VO, ESA.
Grayscale service: NASA SkyView / HEASARC (DSS2 Red).
These are independent survey observations, not predicted output, a color
calibration, or automatically registered overlays. Review source terms before
redistributing survey images. Runtime has no CDN or survey-registry dependency.
