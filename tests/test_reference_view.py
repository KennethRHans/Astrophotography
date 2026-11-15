"""Pointing fallback and fixed-service boundaries for the optional reference."""
from astropy.io import fits
from reference_view import allowed_remote,reference_context

def test_reference_consent_service_boundaries():
    assert allowed_remote('https://casda.csiro.au/hips/DSS2/color/properties')
    assert allowed_remote('https://stpubdata.s3.us-east-1.amazonaws.com/mast/skybackgrounds/DSSColor/Norder3/Dir0/Npix1.jpg')
    for url in ['http://casda.csiro.au/hips/DSS2/color/properties','https://casda.csiro.au/other',
                'https://casda.csiro.au.evil.example/hips/DSS2/color/',
                'https://user:secret@casda.csiro.au/hips/DSS2/color/properties',
                'https://casda.csiro.au:444/hips/DSS2/color/properties','file:///capture.fits']:
        assert not allowed_remote(url)

def test_unknown_object_is_not_silently_m77():
    context=reference_context(fits.Header({'OBJECT':'unknown capture'}),(100,100,3))
    assert context['ra'] is None and context['dec'] is None

def test_valid_sky_solution_takes_priority_over_name():
    from astropy.wcs import WCS
    wcs=WCS(naxis=2);wcs.wcs.ctype=['RA---TAN','DEC--TAN'];wcs.wcs.crpix=[50.5,50.5]
    wcs.wcs.crval=[12.,30.];wcs.wcs.cdelt=[-.001,.001]
    header=wcs.to_header();header['OBJECT']='M77'
    context=reference_context(header,(100,100,3))
    assert abs(context['ra']-12)<1e-6 and abs(context['dec']-30)<1e-6
    assert abs(context['fov']-.1)<1e-6
    assert set(context)=={'name','ra','dec','fov','hint'}

def test_catalog_aliases_suggest_without_network():
    for name,ra in [('M 77',40.6696),('NGC 1068',40.6696),('C56',11.763)]:
        context=reference_context(fits.Header({'OBJECT':name}),(100,100,3))
        assert abs(context['ra']-ra)<.01
        assert 'object name' in context['hint']
