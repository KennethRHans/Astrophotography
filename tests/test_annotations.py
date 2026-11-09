import copy
import numpy as np
import pytest
from astropy.io import fits
from PIL import Image
from PySide6 import QtCore,QtGui,QtWidgets as W
from PySide6.QtTest import QTest
from app import Worker
from test_session_updates import app_and_window,settle,sample
from project_store import load_project,save_project,validate_state
import engine


def test_raster_import_preserves_rgb_and_orientation(tmp_path):
    for suffix in ('png','jpg'):
        p=tmp_path/f'Nebula.{suffix}';Image.new('RGB',(100,80),(100,0,200)).save(p)
        data,header=engine.read_image(p,'RGGB');assert header['EASRASTR'] and data.shape==(80,100,3)
        app,w=app_and_window(tmp_path);w.loaded(data,header);settle(app,w)
        shown=engine.render(w.linear,*w.settings(),model=w.background)
        np.testing.assert_allclose(shown,data,atol=1e-7)
        w.sliders['Stretch'].setValue(80);w.reset_adjustments();np.testing.assert_allclose(engine.render(w.linear,*w.settings(),model=w.background),data,atol=1e-7)
        assert not w.save_stack_button.isEnabled();w.close()
    source=Image.new('RGB',(80,40));exif=source.getexif();exif[274]=6
    source.save(tmp_path/'rotated.jpg',exif=exif)
    assert engine.read_image(tmp_path/'rotated.jpg')[0].shape==(80,40,3)


def test_annotation_click_crop_undo_and_project_roundtrip(tmp_path):
    app,w=app_and_window(tmp_path);w.show();w.loaded(sample(),fits.Header());settle(app,w)
    assert w.labels_action.isEnabled();w.labels_action.trigger();app.processEvents();assert w.labels_dock.isVisible()
    w.labels_panel.text.setText('C56');w.begin_label();assert w.preview.annotation_placing
    point=w.preview.mapFromScene(QtCore.QPointF(40,30));QTest.mouseClick(w.preview.viewport(),QtCore.Qt.LeftButton,pos=point)
    assert len(w.annotations)==1 and not w.preview.annotation_placing
    original=copy.deepcopy(w.annotations);w.select_crop(10,10,90,60);w.crop_selected()
    assert w.annotations==original and w.preview.annotation_crop==(10,10,90,60)
    w.undo_edit();assert w.linear.shape==(64,96,3) and w.annotations==original
    w.undo_edit();assert w.annotations==original  # crop selection is its own undo step
    w.undo_edit();assert not w.annotations
    w.redo_edit();assert w.annotations==original
    p=tmp_path/'labels.astro';w.save_project_path(p);settle(app,w);meta=load_project(p)[2]
    assert meta['state']['annotations']==original
    w.new_project(True);assert not w.labels_action.isEnabled() and not w.preview.annotations
    w.open_project_path(p);settle(app,w);assert w.annotations==original and not w._dirty
    w.labels_panel.text.setText('Edited');w.edit_label();assert w.annotations[0]['text']=='Edited'
    w.undo_edit();assert w.annotations==original
    w.close();settle(app,w)


def test_label_export_uses_current_crop_and_leaves_original_untouched(tmp_path,monkeypatch):
    app,w=app_and_window(tmp_path);data=sample();before=data.copy();w.loaded(data,fits.Header({'NCOMBINE':10,'OBJECT':'C56'}));settle(app,w)
    w.labels_panel.text.setText('Target');w.place_label(45,30)
    w.select_crop(10,10,90,60);w.crop_selected();w.labels_panel.visible.setChecked(False)
    unlabeled=w.labeled_image();w.labels_panel.visible.setChecked(True);labeled=w.labeled_image()
    assert unlabeled.size()==QtCore.QSize(80,50) and labeled!=unlabeled
    import app as application
    path=tmp_path/'full.fits';monkeypatch.setattr(W.QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    monkeypatch.setattr(application,'select_save_file',lambda *a,**k:str(path))
    w.save_stacked_fits();reopened,header=engine.read_fits(path)
    np.testing.assert_array_equal(reopened,before);np.testing.assert_array_equal(data,before);assert header['NCOMBINE']==10
    png=tmp_path/'labeled.png';monkeypatch.setattr(W.QFileDialog,'getSaveFileName',lambda *a,**k:(str(png),'PNG (*.png)'))
    monkeypatch.setattr(application,'select_export_file',lambda *a,**k:str(png))
    w.export_labeled_image();assert Image.open(png).size==(80,50)
    w.close();settle(app,w)


def test_old_project_migration_and_annotation_validation(tmp_path):
    app,w=app_and_window(tmp_path);data=sample();w.loaded(data,fits.Header());settle(app,w)
    meta=w.project_manifest()
    for state in [meta['state'],*meta['history']['states']]:state.pop('annotations');state.pop('labels_visible')
    p=tmp_path/'old.astro';save_project(p,data,fits.Header(),meta);w.open_project_path(p);settle(app,w)
    assert not w.annotations and w.labels_visible and not w._dirty
    state=w.edit_state();a=dict(kind='Text',text='Bad',color='#ffffff',size=24,x=float('nan'),y=0)
    state['annotations']=[a]
    with pytest.raises(ValueError):validate_state(state,data.shape)
    a['x']=2;a['text']='a'*201
    with pytest.raises(ValueError):validate_state(state,data.shape)
    w.close()


def test_stack_chime_success_only_and_persisted_setting(tmp_path,monkeypatch):
    app,w=app_and_window(tmp_path);calls=[];monkeypatch.setattr(w,'play_stack_chime',lambda:calls.append(1))
    w.pending_source_paths=['a.fit','b.fit','c.fit'];w.worker=Worker(w.pending_source_paths,'Auto');w.loaded(sample(),fits.Header({'NCOMBINE':2}))
    assert calls==[1] and '2 exposures combined; 1 skipped' in w.progress_text.text()
    w.chime_action.setChecked(False);w.loaded(sample(),fits.Header({'NCOMBINE':2}));assert calls==[1]
    w.processing_failed('Cancelled');assert calls==[1]
    w.worker.single=True;w.chime_action.setChecked(True);w.loaded(sample(),fits.Header());assert calls==[1]
    w.worker=None;w.chime_action.setChecked(False);w.close();settle(app,w)
    _,w=app_and_window(tmp_path);assert not w.chime_action.isChecked();w.close()
