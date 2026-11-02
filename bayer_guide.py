"""Camera examples are guidance, never overrides for a file's actual metadata."""
BAYER_GUIDE = {
    'Auto': 'Recommended for Seestar and most color cameras. Reads the pattern in each FITS header. Tested Seestar S50 Pro raw exposures report GRBG. Already-color RGB stacks need no debayering.',
    'RGGB': 'Common examples: ZWO ASI2600MC, ASI533MC and ASI6200MC color cameras used with refractors, reflectors or SCTs. Confirm BAYERPAT in your files; capture software can change the stored orientation.',
    'BGGR': 'Used by some color camera/file orientations; it is also a 180°-rotated RGGB layout. No telescope model uniquely identifies this pattern. Choose only when your FITS header or camera/software documentation specifies BGGR.',
    'GRBG': 'Confirmed in tested Seestar S50 Pro raw FITS exposures. Other cameras can store this layout too. Use Auto when the header is present; do not assume all Seestar models or software versions write the same pattern.',
    'GBRG': 'Used by some color camera/file orientations; it is also a 180°-rotated GRBG layout. No telescope model uniquely identifies this pattern. Choose only when your FITS header or camera/software documentation specifies GBRG.',
    'None': 'For monochrome cameras (for example ASI2600MM or ASI533MM), grayscale files, or a single-channel image that should stay grayscale. Three-channel RGB stacks bypass Bayer conversion automatically.',
}
