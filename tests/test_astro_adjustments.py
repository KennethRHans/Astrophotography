import copy
import time
import numpy as np
import pytest
from scipy.ndimage import gaussian_filter
from astropy.io import fits
from PySide6 import QtCore,QtWidgets as W
from PySide6.QtTest import QTest
from astro_adjustments import NEUTRAL_CURVE,tone_adjust,star_preserving_denoise,validate_curve
from preview_render import PreviewRenderer
from project_store import save_project,load_project
from test_session_updates import app_and_window,settle,sample
import engine


def test_neutral_tone_exact_identity_midtones_monotonic_endpoints_and_color_ratios():
    rng=np.random.default_rng(71);image=rng.uniform(0,1,(30,40,3)).astype('float32')
    np.testing.assert_array_equal(tone_adjust(image),image)
    ramp=np.repeat(np.linspace(0,1,1001,dtype='float32')[None,:,None],3,axis=-1)
    for amount in (-1,-.4,.4,1):
        shown=tone_adjust(ramp,amount)
        assert shown[0,0,0]==0 and np.isclose(shown[0,-1,0],1) and np.min(np.diff(shown[0,:,0]))>=-1e-6
    assert tone_adjust(ramp,.5)[0,300,0]>ramp[0,300,0]>tone_adjust(ramp,-.5)[0,300,0]
    colored=np.array([[[.7,.3,.1],[.1,.2,.4]]],dtype='float32');changed=tone_adjust(colored,.8,(0,400,700,900,1000))
    np.testing.assert_allclose(changed[...,0]/changed[...,1],colored[...,0]/colored[...,1],rtol=1e-6)
    assert np.isfinite(changed).all() and changed.min()>=0 and changed.max()<=1


def test_curve_validation_and_monotone_curve_preserves_black_white():
    for bad in [(0,500,250,750,1000),(1,250,500,750,1000),(0,250,500,750,999),(0,250.,500,750,1000)]:
        with pytest.raises(ValueError):validate_curve(bad)
    ramp=np.repeat(np.linspace(0,1,1001,dtype='float32')[None,:,None],3,axis=-1)
    result=tone_adjust(ramp,0,(0,100,500,900,1000));assert result[0,100,0]<ramp[0,100,0] and result[0,900,0]>ramp[0,900,0]
    assert result[0,0,0]==0 and result[0,-1,0]==1 and np.min(np.diff(result[0,:,0]))>=0


def star_field():
    y,x=np.mgrid[:200,:240];clean=np.ones((200,240),dtype='float32')*.15
    for py,px in [(60,60),(100,140),(150,185)]:clean+=.6*np.exp(-((x-px)**2+(y-py)**2)/(2*1.4**2))
    rng=np.random.default_rng(9);return np.clip(np.repeat(clean[...,None],3,axis=-1)+rng.normal(0,.012,(200,240,3)),0,1).astype('float32')


def test_noise_reduction_reduces_background_and_preserves_cores_and_source():
    data=star_field();original=data.copy();out=star_preserving_denoise(data,.8,1)
    assert np.std(out[10:40,10:40])<np.std(data[10:40,10:40])*.85
    for py,px in [(60,60),(100,140),(150,185)]:
        np.testing.assert_array_equal(out[py-1:py+2,px-1:px+2],data[py-1:py+2,px-1:px+2])
        assert abs(float(out[py-4:py+5,px-4:px+5].sum()-data[py-4:py+5,px-4:px+5].sum()))<.25
    np.testing.assert_array_equal(data,original);np.testing.assert_array_equal(star_preserving_denoise(data,0),data)
    valid=np.ones(data.shape[:2],bool);valid[:5]=False;data[:5]=0
    edges=star_preserving_denoise(data,1,1,valid);np.testing.assert_array_equal(edges[:8],data[:8])


def test_prepared_noise_cache_reused_for_tone_changes(monkeypatch):
    import preview_render
    normalize=preview_render.star_preserving_denoise;calls=[]
    def counted(*a,**k):calls.append(1);return normalize(*a,**k)
    monkeypatch.setattr(preview_render,'star_preserving_denoise',counted)
    data=star_field();model=np.zeros((6,3));renderer=PreviewRenderer();settings=(30,.1,1,0,0,(1,1,1),0,1,0,0,.5,1,NEUTRAL_CURVE)
    renderer.render(data,(240,200),settings,model,None,False)
    changed=list(settings);changed[9]=.3;renderer.render(data,(240,200),tuple(changed),model,None,False)
    changed[-1]=(0,300,600,800,1000);renderer.render(data,(240,200),tuple(changed),model,None,False);assert len(calls)==1
    changed[10]=.8;renderer.render(data,(240,200),tuple(changed),model,None,False);assert len(calls)==2


def test_curve_drag_undo_reset_project_and_old_project_migration(tmp_path):
    app,w=app_and_window(tmp_path);w.show();data=sample();w.loaded(data,fits.Header());settle(app,w)
    # Scroll the editor into view for the real pointer gesture.
    w.sidebar_scroll.ensureWidgetVisible(w.curve);app.processEvents()
    p=w.curve.point(2).toPoint();q=p+QtCore.QPoint(0,-25)
    QTest.mousePress(w.curve,QtCore.Qt.LeftButton,pos=p);QTest.mouseMove(w.curve,q);QTest.mouseRelease(w.curve,QtCore.Qt.LeftButton,pos=q)
    assert w.curve.values!=NEUTRAL_CURVE and not w.curve.dragging
    changed=w.curve.values;w.undo_edit();assert w.curve.values==NEUTRAL_CURVE;w.redo_edit();assert w.curve.values==changed
    w.sliders['Midtones %'].setValue(35);w.sliders['Star-preserving noise reduction %'].setValue(40);w.commit_history();saved=w.edit_state()
    path=tmp_path/'tone.astro';w.save_project_path(path);settle(app,w);w.new_project(True);w.open_project_path(path);settle(app,w)
    assert w.edit_state()==saved and not w._dirty
    w.reset_curve.click();assert w.curve.values==NEUTRAL_CURVE;w.undo_edit();assert w.edit_state()==saved
    meta=w.project_manifest()
    for state in [meta['state'],*meta['history']['states']]:
        state.pop('curve',None)
        for key in ('Midtones %','Star-preserving noise reduction %','Star protection %'):state['sliders'].pop(key,None)
    old=tmp_path/'old.astro';save_project(old,data,fits.Header(),meta);w.open_project_path(old);settle(app,w)
    assert w.curve.values==NEUTRAL_CURVE and w.sliders['Midtones %'].value()==0 and w.sliders['Star protection %'].value()==100
    assert not w._dirty
    w.close();settle(app,w)


def test_linear_fits_export_unchanged_with_new_display_tools(tmp_path):
    data=sample();before=data.copy();shown=engine.render(data,midtones=.4,star_denoise=.8,curve=(0,350,650,850,1000))
    path=tmp_path/'linear.fits';engine.save(path,data,shown,fits.Header())
    np.testing.assert_array_equal(engine.read_fits(path)[0],before);np.testing.assert_array_equal(data,before)
