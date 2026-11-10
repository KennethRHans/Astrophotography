import time
import numpy as np
import pytest
from scipy.ndimage import gaussian_filter
from astropy.io import fits
from PySide6 import QtWidgets
import engine
from review_stretch import render_review,apply_review_stretch
from frame_review import ReviewWorker,FrameReviewDialog

LUMA=np.array([.2126,.7152,.0722])


def faint_exposure():
    rng=np.random.default_rng(52)
    stars=np.zeros((512,768),dtype='float32')
    for y,x in [(100,150),(180,360),(340,550),(430,210)]:stars[y,x]=4000
    signal=gaussian_filter(stars,1.3)
    image=(5000+rng.normal(0,20,(512,768,3))+signal[...,None]).astype('float32')
    image[250,600]=65535  # An isolated bright/hot pixel must not whiten the sky.
    return image


def test_auto_preview_darkens_noisy_sky_and_preserves_raw_pixels():
    image=faint_exposure();before=image.copy()
    standard=engine.render(image);auto=render_review(image)
    assert np.median(standard@LUMA)>.5
    assert .12<np.median(auto@LUMA)<.2
    assert auto[100,150].mean()>np.median(auto)+.2
    np.testing.assert_array_equal(image,before)
    smaller=render_review(image,(384,256))
    assert abs(np.median(smaller@LUMA)-np.median(auto@LUMA))<.02


def test_auto_stretch_valid_masks_flat_frames_and_hue_ratios():
    image=faint_exposure();image[:10]=0
    assert not render_review(image)[:10].any()
    assert not render_review(np.zeros((2,3,3),dtype='float32')).any()
    flat=render_review(np.ones((3,4,3),dtype='float32'))
    assert np.isfinite(flat).all() and .1<float(flat.mean())<.25
    color=np.array([[[.8,.4,.2]]],dtype='float32')
    shown=apply_review_stretch(color,(0.,1.,.3))
    np.testing.assert_allclose(shown[0,0,0]/shown[0,0,1],2,rtol=1e-6)
    np.testing.assert_allclose(shown[0,0,1]/shown[0,0,2],2,rtol=1e-6)
    with pytest.raises(ValueError):render_review(np.zeros((10,10)))


def write_frame(tmp_path):
    path=tmp_path/'light.fit'
    fits.writeto(path,np.moveaxis(faint_exposure(),-1,0),fits.Header({'OBJECT':'Synthetic','EXPTIME':20.}))
    return str(path)


def test_worker_stretch_does_not_change_analysis(tmp_path):
    path=write_frame(tmp_path);rows=[];previews=[]
    for automatic in (True,False):
        worker=ReviewWorker([path],'Auto',scan=True,auto_stretch=automatic)
        worker.rowReady.connect(lambda p,row:rows.append(row));worker.run()
        preview=ReviewWorker([path],'Auto',auto_stretch=automatic)
        preview.previewReady.connect(lambda p,payload,caption:previews.append((payload,caption)));preview.run()
    assert rows[0]==rows[1]
    assert 'Auto stretch' in previews[0][1] and 'Standard stretch' in previews[1][1]
    assert np.median(previews[0][0][0])<np.median(previews[1][0][0])*.5


def test_dialog_defaults_to_auto_and_mode_switch_reloads_preview(tmp_path):
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog=FrameReviewDialog([write_frame(tmp_path)],'Auto');dialog.show()
    def wait_preview():
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
            if dialog.worker is None and not dialog.view.item.pixmap().isNull():return
        raise AssertionError('Exposure preview timed out')
    wait_preview()
    assert dialog.stretch_mode.currentIndex()==0 and 'Auto stretch' in dialog.caption.text()
    dialog.stretch_mode.setCurrentIndex(1);wait_preview()
    assert 'Standard stretch' in dialog.caption.text() and dialog.records=={}
    assert dialog.stretch_mode.isEnabled()
    dialog.close();app.processEvents()
