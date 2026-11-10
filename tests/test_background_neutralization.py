import numpy as np
import pytest
import tifffile
from astropy.io import fits
import engine
from preview_render import PreviewRenderer
from project_store import load_project,save_project
from test_session_updates import app_and_window,settle


def colored_sky():
    rng=np.random.default_rng(81)
    sky=.09+rng.normal(0,.003,(120,160,1))
    image=np.asarray(np.repeat(sky,3,axis=-1)+[.04,0,-.015]+rng.normal(0,1,(120,160,3))*[.01,.003,.006],dtype='float32')
    image[50:53,70:73]+=[.3,.2,.1]
    return image


def test_neutral_sky_and_preserved_star_excess_without_clipping():
    image=colored_sky();before=image.copy()
    shown=engine.neutralize_background(image,1)
    luma=image@np.array([.2126,.7152,.0722],dtype=np.float32)
    low,high=np.percentile(luma,[25,60]);sky=(luma>=low)&(luma<=high)
    color=np.median(shown[sky],axis=0)
    assert np.ptp(color)<1e-6
    np.testing.assert_allclose(shown[51,71]-shown[30,40],image[51,71]-image[30,40],atol=1e-7)
    np.testing.assert_allclose(shown@np.array([.2126,.7152,.0722]),luma,atol=1e-7)
    np.testing.assert_array_equal(image,before)
    assert engine.neutralize_background(image,0) is image
    middle=engine.neutralize_background(image,.5)
    assert np.ptp(np.median(middle[sky],axis=0))<np.ptp(np.median(image[sky],axis=0))


def test_invalid_coverage_tiny_samples_and_amounts():
    image=colored_sky();valid=np.ones(image.shape[:2],bool);valid[:10]=False;image[:10]=0
    shown=engine.neutralize_background(image,1,valid)
    assert not shown[:10].any()
    np.testing.assert_array_equal(engine.background_color_offsets(np.zeros((2,3,3))),np.zeros(3))
    for amount in (-.1,1.1,float('nan')):
        with pytest.raises(ValueError):engine.neutralize_background(image,amount)


def test_render_off_exact_identity_linear_fits_unchanged_and_cpu_fallback(tmp_path):
    image=colored_sky()*10000;before=image.copy()
    baseline=engine.render(image)
    np.testing.assert_array_equal(engine.render(image,background_neutralization=0),baseline)
    neutral=engine.render(image,background_neutralization=1)
    assert not np.array_equal(neutral,baseline)
    class FailedGPU:
        disabled=False;last_error=None
        def process(self,*args):raise RuntimeError('Unavailable')
    np.testing.assert_array_equal(engine.render(image,background_neutralization=1,gpu=FailedGPU()),neutral)
    path=tmp_path/'linear.fits';engine.save(path,image,neutral,fits.Header())
    np.testing.assert_array_equal(engine.read_fits(path)[0],before)
    np.testing.assert_array_equal(image,before)
    raster=tmp_path/'rendered.tiff';engine.save(raster,image,neutral,fits.Header())
    np.testing.assert_array_equal(tifffile.imread(raster),np.round(neutral*65535).astype(np.uint16))


def test_preview_release_and_amount_changes_keep_shared_offsets():
    image=np.tile(colored_sky(),(5,5,1))*10000
    settings=(30,.1,1,0,0,(1,1,1),0,1,0,0,0,1,(0,250,500,750,1000),1)
    renderer=PreviewRenderer();draft=renderer.render(image,(400,300),settings,None,None,False)
    offset=renderer.reference['color_offsets']
    settled=renderer.render(image,(800,600),settings,None,None,False)
    np.testing.assert_array_equal(draft['bins'],settled['bins'])
    assert renderer.reference['color_offsets'] is offset
    off=renderer.render(image,(800,600),(*settings[:-1],0),None,None,False)
    assert not np.array_equal(off['bins'],settled['bins'])


def test_neutralization_undo_project_roundtrip_and_old_project_migration(tmp_path):
    app,w=app_and_window(tmp_path);image=colored_sky()*10000
    w.loaded(image,fits.Header());settle(app,w)
    slider=w.sliders['Background neutralization %'];assert slider.value()==0
    slider.setValue(75);w.commit_history();settle(app,w)
    w.undo_edit();assert slider.value()==0
    w.redo_edit();assert slider.value()==75
    path=tmp_path/'neutral.astro';w.save_project_path(path);settle(app,w)
    w.new_project(True);w.open_project_path(path);settle(app,w)
    assert slider.value()==75 and not w._dirty
    w.baseline.setChecked(True);assert w.settings()[-1]==0
    w.baseline.setChecked(False);assert w.settings()[-1]==.75
    w.reset_adjustments();assert slider.value()==0
    w.undo_edit();assert slider.value()==75
    metadata=load_project(path)[2]
    for state in [metadata['state'],*metadata['history']['states']]:state['sliders'].pop('Background neutralization %')
    old=tmp_path/'old.astro';save_project(old,image,fits.Header(),metadata)
    w.open_project_path(old);settle(app,w)
    assert slider.value()==0 and not w._dirty
    assert all(state['sliders']['Background neutralization %']==0 for state in w.history.states)
    w.close();settle(app,w)
