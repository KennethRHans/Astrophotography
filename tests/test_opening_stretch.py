import json
from zipfile import ZipFile
import numpy as np
import pytest
from astropy.io import fits
from opening_stretch import opening_statistics,validate_opening_stretch
from review_stretch import apply_review_stretch
from preview_render import PreviewRenderer
from project_store import save_project,load_project
import engine
from test_session_updates import app_and_window,settle

LUMA=np.array([.2126,.7152,.0722])

def image():
    rng=np.random.default_rng(827)
    data=rng.normal(.108,.0008,(240,360,3)).astype('float32')
    data[...,0]+=np.linspace(0,.006,240)[:,None]
    data[60:63,120:123]=[.8,.5,.3]
    data[120:124,260:264]=[.3,.6,.9]
    data[:4]=0
    return data

def test_adaptive_matches_audited_transfer_and_keeps_raw_values():
    data=image();original=data.copy();statistics=opening_statistics(data)
    model=dict(opening_stretch=statistics,background=np.zeros((6,3)))
    result=engine.render(data,stretch=0,black=0,model=model)
    np.testing.assert_allclose(result,apply_review_stretch(data,statistics),atol=2e-6)
    assert .17<np.median((result@LUMA)[4:])<.23
    np.testing.assert_array_equal(data,original)
    assert not result[:4].any()
    assert np.isfinite(result).all()

def test_preview_zoom_and_export_share_adaptive_transfer(tmp_path):
    data=image();model=dict(opening_stretch=opening_statistics(data),background=np.zeros((6,3)))
    settings=(0,0,1,0,0,(1,1,1),0,1,0)
    renderer=PreviewRenderer()
    a=renderer.render(data,(180,120),settings,model,None,False)
    b=renderer.render(data,(360,240),settings,model,None,False)
    np.testing.assert_array_equal(a['bins'],b['bins'])
    full=engine.render(data,*settings,model=model)
    np.testing.assert_array_equal(b['pixels'],np.round(full*255).astype('uint8'))
    source=tmp_path/'linear.fits';engine.save(source,data,None,fits.Header())
    restored,_=engine.read_fits(source)
    np.testing.assert_array_equal(restored,data)

@pytest.mark.parametrize('bad',[[0,1,0],[0,1,1],[1,1,.5],[-1,1,.5],[0,float('nan'),.5],[0,float('inf'),.5],['0',1,.5],[0,1]])
def test_invalid_saved_transfers_rejected(bad):
    with pytest.raises(ValueError):validate_opening_stretch(bad)

def test_modes_undo_reset_crop_and_project_compatibility(tmp_path):
    qt,w=app_and_window(tmp_path);data=image();w.loaded(data,fits.Header());settle(qt,w)
    assert w.opening_stretch is not None and w.sliders['Stretch'].value()==0
    initial=list(w.opening_stretch);adaptive=engine.render(w.linear,*w.settings(),model=w.background)
    w.opening_mode.setCurrentIndex(1);settle(qt,w)
    assert w.opening_stretch is None and w.sliders['Stretch'].value()==30
    legacy=engine.render(w.linear,*w.settings(),model=w.background)
    assert np.median(legacy@LUMA)>np.median(adaptive@LUMA)*2
    w.undo_edit();settle(qt,w);assert w.opening_stretch==initial
    w.sliders['Brightness (stops ×100)'].setValue(30);w.reset_adjustments();settle(qt,w)
    assert w.opening_stretch==initial and w.settings()[0]==0 and w.settings()[6]==0
    path=tmp_path/'adaptive.astro';save_project(path,data,w.original_header,w.project_manifest())
    with ZipFile(path) as z:assert json.loads(z.read('project.json'))['version']==2
    restored,header,meta=load_project(path)
    w._project_io_path=str(path);w._project_opened((restored,header,meta));settle(qt,w)
    assert w.opening_stretch==initial
    np.testing.assert_allclose(engine.render(w.linear,*w.settings(),model=w.background),adaptive)
    # A pre-update project lacks the field entirely and keeps legacy rendering.
    w.opening_mode.setCurrentIndex(1);settle(qt,w)
    old=w.project_manifest();old['state'].pop('opening_stretch',None)
    for state in old['history']['states']:state.pop('opening_stretch',None)
    old['history']={'states':[old['state'].copy()],'index':0}
    oldpath=tmp_path/'old.astro';save_project(oldpath,data,w.original_header,old)
    with ZipFile(oldpath) as z:assert json.loads(z.read('project.json'))['version']==1
    restored,header,meta=load_project(oldpath)
    w._project_io_path=str(oldpath);w._project_opened((restored,header,meta));settle(qt,w)
    assert w.opening_stretch is None and not w._dirty
    assert w.edit_state()==w.history.states[w.history.index]
    np.testing.assert_allclose(engine.render(w.linear,*w.settings(),model=w.background),legacy)
    w.close();settle(qt,w)

def test_raster_images_do_not_get_auto_stretched(tmp_path):
    qt,w=app_and_window(tmp_path);data=np.full((50,60,3),.25,dtype='float32')
    w.loaded(data,fits.Header({'EASRASTR':True}));settle(qt,w)
    assert w.opening_stretch is None and not w.opening_mode.isEnabled()
    np.testing.assert_allclose(engine.render(w.linear,*w.settings(),model=w.background),data)
    w.close();settle(qt,w)


def test_gpu_failure_retries_exact_same_adaptive_pixels():
    data=image();model=dict(opening_stretch=opening_statistics(data),background=np.zeros((6,3)))
    class Failing:
        disabled=False
        def process(self,*args):raise RuntimeError('synthetic device failure')
    gpu=Failing();expected=engine.render(data,stretch=0,black=0,model=model)
    actual=engine.render(data,stretch=0,black=0,model=model,gpu=gpu)
    assert gpu.disabled
    np.testing.assert_array_equal(actual,expected)

def test_opencl_adaptive_matches_cpu_if_available():
    cl=pytest.importorskip('pyopencl')
    try:devices=[d for p in cl.get_platforms() for d in p.get_devices()]
    except cl.Error:pytest.skip('No OpenCL runtime')
    if not devices:pytest.skip('No OpenCL device')
    from gpu import GpuProcessor
    processor=GpuProcessor(context=cl.Context([devices[0]]))
    data=image();model=dict(opening_stretch=opening_statistics(data),background=np.zeros((6,3)))
    for stretch,exposure in [(0,0),(7,.2),(0,-.3)]:
        kwargs=dict(stretch=stretch,black=0,brightness=exposure,saturation=1.2,midtones=.1,model=model)
        expected=engine.render(data,**kwargs);actual=engine.render(data,gpu=processor,**kwargs)
        assert not processor.disabled
        np.testing.assert_allclose(actual,expected,atol=3e-5,rtol=3e-5)
