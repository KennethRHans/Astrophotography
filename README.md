# Standalone reference-view test 0.3

This prototype displays DSS2 color references assembled directly from mirrored HiPS tiles, bypassing the failed cutout service. Automatic mirror order: MAST, CSIRO, China-VO, ESA. Includes source/loading status, cancellation, optional NASA grayscale fallback, and a five-reference browser-local offline cache. Local working/reference files are never uploaded or saved in that cache.

Extract the artifact ZIP and open Reference-View-Test.html in Edge/Chrome. Read START-HERE and THIRD-PARTY-NOTICES. The unmodified, integrity-checked Aladin Lite 3.8.2 renderer is embedded locally; matching source and licenses are bundled under vendor/aladin-lite. It starts only after online consent. No runtime CDN download is required in the packaged test.

The workflow verifies real M77 color rendering, sky coordinates, and saved-image offline decoding. It also deliberately blocks the first mirror to test automatic fallback to another mirror of the same color survey. Browser availability can change, so refer to the run’s logs and result.

This isolated branch builds only the standalone HTML test ZIP, not an Easy Astro Studio update or installer.
