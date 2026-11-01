import numpy as np
import pytest
from astropy.io import fits
from scipy.ndimage import gaussian_filter, shift, rotate
import engine


def test_rgb_roundtrip_and_exports(tmp_path):
    data = np.random.default_rng(1).uniform(100, 1000, (32, 40, 3)).astype('float32')
    header = fits.Header({'BAYERPAT': 'RGGB'})
    path = tmp_path/'linear.fits'
    rendered = engine.render(data)
    engine.save(path, data, rendered, header)
    result, hdr = engine.read_fits(path)
    np.testing.assert_array_equal(result, data)
    assert 'BAYERPAT' not in hdr
    engine.save(tmp_path/'image.tif', data, rendered, header)
    import tifffile
    tiff = tifffile.imread(tmp_path/'image.tif')
    assert tiff.dtype == np.uint16 and tiff.shape == data.shape
    engine.save(tmp_path/'image.png', data, rendered, header)
    np.testing.assert_array_equal(data, result)


def test_bayer_color(tmp_path):
    raw = np.zeros((30, 30), dtype='uint16')
    raw[0::2, 0::2] = 3000
    raw[0::2, 1::2] = raw[1::2, 0::2] = 2000
    raw[1::2, 1::2] = 1000
    path = tmp_path/'raw.fit'
    fits.writeto(path, raw, fits.Header({'BAYERPAT':'RGGB'}))
    rgb, _ = engine.read_fits(path)
    np.testing.assert_allclose(rgb[5, 5], [3000, 2000, 1000], atol=1)


def test_align_rotated_translated_stars_and_reduce_noise(tmp_path):
    rng = np.random.default_rng(42)
    sky = np.zeros((180, 180), dtype='float32')
    for y, x in rng.integers(20, 160, (50, 2)):
        sky[y, x] += rng.uniform(3000, 8000)
    sky = gaussian_filter(sky, 1.2)+100
    paths = []
    for i in range(8):
        image = rotate(sky, i*.15, reshape=False, mode='constant', cval=100)
        image = shift(image, (i*.25, -i*.2), mode='constant', cval=100)
        image += rng.normal(0, 3, image.shape)
        path = tmp_path/f'{i}.fits'
        fits.writeto(path, image.astype('float32'), fits.Header({'EXPTIME':20., 'TOTALEXP':20.})); paths.append(path)
    events = []
    result, header = engine.stack(paths, report_progress=lambda done, total, phase: events.append((done, total, phase)))
    assert events[0] == (1, 8, "Aligning exposures")
    assert (8, 8, "Aligning exposures") in events
    assert events[-1] == (180, 180, "Combining image rows")
    assert header['NCOMBINE'] >= 6
    assert header['TOTALEXP'] == header['NCOMBINE'] * 20.
    # Central field must recover the same star locations, with less noise.
    residual = result[25:-25, 25:-25, 0]-sky[25:-25, 25:-25]
    assert np.median(np.abs(residual)) < 3
    assert np.corrcoef(result[25:-25,25:-25,0].ravel(), sky[25:-25,25:-25].ravel())[0,1] > .98


def test_cancel_and_invalid(tmp_path):
    path = tmp_path/'bad.fits'
    fits.writeto(path, np.full((10,10), np.nan))
    with pytest.raises(ValueError, match='nonfinite'): engine.read_fits(path)
    with pytest.raises(ValueError): engine.stack([path])


def test_seestar_rgb_stack_with_retained_bayer_header(tmp_path):
    data = np.arange(3*12*10, dtype='uint16').reshape(3,12,10)
    header = fits.Header({'BAYERPAT':'GRBG', 'STACKCNT':299, 'EXPTIME':20., 'TOTALEXP':5980., 'OBJECT':'C 56'})
    path = tmp_path/'seestar.fit'
    fits.writeto(path, data, header)
    rgb, hdr = engine.read_fits(path)
    np.testing.assert_array_equal(rgb, np.moveaxis(data,0,-1))
    assert '299 exposure(s)' in engine.image_summary(rgb,hdr)
    assert '5980 seconds' in engine.image_summary(rgb,hdr)
    with pytest.raises(ValueError, match='already stacked'):
        engine.stack([path,path])


def test_background_fit_preserves_compact_signal_and_original():
    h, w = 240, 300
    y, x = np.mgrid[-1:1:complex(h), -1:1:complex(w)]
    gradient = 150*x+80*y+35*x*y+25*y*y
    object_signal = 300*np.exp(-((x-.2)**2+(y+.1)**2)/.002)
    rng = np.random.default_rng(19)
    image = np.repeat((5000+gradient+object_signal)[...,None],3,axis=-1)
    image += rng.normal(0,2,image.shape)
    original = image.copy()
    model = engine.background_model(image)
    corrected = engine.correct_background(image, 1, model)
    background = object_signal < 1
    assert np.std(corrected[...,0][background]) < 4
    assert corrected[...,0].max()-np.median(corrected[...,0]) > 270
    np.testing.assert_array_equal(image,original)
    np.testing.assert_array_equal(engine.correct_background(image,0), image.astype('float32'))


def test_color_controls_and_missing_coverage():
    data = np.ones((60,60,3),dtype='float32')*100
    data[20:40,20:40] = [200,200,200]
    data[0:2] = 0
    neutral = engine.render(data, stretch=0)
    warm = engine.render(data, stretch=0,gains=(2,1,1))
    assert warm[30,30,0] > warm[30,30,1]
    assert neutral[30,30,0] == neutral[30,30,1]
    assert np.all(warm[:2] == 0)
    assert np.isfinite(engine.render(np.zeros_like(data))).all()
