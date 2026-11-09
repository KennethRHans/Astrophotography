import time
import numpy as np
from astropy.io import fits
from PySide6 import QtCore,QtWidgets as W
from preview_render import PreviewRenderer
from histogram import histogram_data
from test_session_updates import app_and_window,settle,sample


def test_continuous_drag_updates_image_before_mouse_release(tmp_path):
    app,w=app_and_window(tmp_path);w.show();w.loaded(sample(),fits.Header());settle(app,w)
    frames=[];original=w.apply_preview
    def displayed(result):frames.append(result['settings']);original(result)
    w.apply_preview=displayed;slider=w.sliders['Saturation %'];slider.setSliderDown(True)
    for value in range(50,151,2):
        slider.setValue(value);deadline=time.monotonic()+.01
        while time.monotonic()<deadline:app.processEvents();time.sleep(.001)
    assert len(frames)>=3,'Continuous pointer movement must not postpone all image updates'
    slider.setSliderDown(False);settle(app,w)
    assert w._displayed_preview_settings==w.settings() and 'Live draft' not in w.zoom_label.text()
    w.close();settle(app,w)


def test_draft_cache_survives_settled_render_and_is_bounded(monkeypatch):
    import engine
    data=sample();renderer=PreviewRenderer();settings=(30,.1,1,0,0,(1,1,1),0,1,0);model=np.zeros((6,3))
    original=engine.normalize_image;calls=[]
    def normalize(*a,**k):calls.append(a[0].shape);return original(*a,**k)
    monkeypatch.setattr(engine,'normalize_image',normalize)
    renderer.render(data,(48,32),settings,model,None,False);renderer.render(data,(96,64),settings,model,None,False)
    renderer.render(data,(48,32),settings,model,None,False);assert len(calls)==2
    renderer.render(data,(24,16),settings,model,None,False);assert len(renderer.cache)==2
    renderer.render(data.copy(),(24,16),settings,model,None,False);assert len(renderer.cache)==1
    renderer.clear();assert renderer.source is None and not renderer.cache


def test_fast_histogram_matches_reference_including_edges_and_outliers():
    rng=np.random.default_rng(31);image=rng.uniform(-.1,1.1,(120,130,3)).astype('float32')
    image.flat[:6]=[0,1,np.nextafter(np.float32(.5),np.float32(0)),.5,np.nextafter(np.float32(.5),np.float32(1)),1.1]
    valid=rng.random(image.shape[:2])>.1;bins,black,white=histogram_data(image,valid);values=image[valid]
    expected=np.stack([np.histogram(values[:,i],bins=256,range=(0,1))[0] for i in range(3)])
    np.testing.assert_array_equal(bins,expected)
    assert black==np.mean(np.any(values<=0,axis=-1))*100 and white==np.mean(np.any(values>=1,axis=-1))*100


def test_friendly_units_and_advanced_controls_keep_project_keys(tmp_path):
    app,w=app_and_window(tmp_path);w.loaded(sample(),fits.Header());settle(app,w)
    assert '×100' not in w.slider_labels['Black percentile ×100'].text()
    assert w.slider_rows['Black percentile ×100'].value_label.text()=='0.10%'
    w.sliders['Brightness (stops ×100)'].setValue(25)
    assert w.slider_rows['Brightness (stops ×100)'].value_label.text()=='+0.25 stops'
    assert len(w.sliders)==15 and set(w.edit_state()['sliders'])==set(w.slider_defaults)
    assert not w.advanced_toggle.isChecked();w.advanced_toggle.setChecked(True);assert not w.advanced_panel.isHidden()
    w.close();settle(app,w)
