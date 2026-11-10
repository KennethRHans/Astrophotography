import copy
import numpy as np
import pytest
from astropy.io import fits
from PySide6 import QtCore
from PySide6.QtTest import QTest
import engine
from background_extraction import fit_sky,sky_grid,cropped_coefficients,validate_extraction
from background_dialog import BackgroundDialog
from test_session_updates import app_and_window,settle


def field():
    y,x=np.mgrid[-1:1:240j,-1:1:300j];gradient=80*x+45*y;target=300*np.exp(-((x-.1)**2+(y+.05)**2)/.14)
    data=np.repeat((5000+gradient+target)[...,None],3,axis=-1).astype('float32')
    points=[[float(px),float(py)] for py in np.linspace(.05,.95,8) for px in np.linspace(.05,.95,8) if (2*px-1-.1)**2+(2*py-1+.05)**2>1]
    return data,dict(order=1,points=points),target,gradient


def test_selected_sky_protects_extended_target_and_crop_coordinates():
    data,config,target,gradient=field();original=data.copy();model,rms=fit_sky(data,config);corrected=engine.correct_background(data,1,model)
    assert rms<1
    assert abs((corrected[...,0].max()-np.median(corrected[:10,:,0]))-300)<3
    assert np.std((corrected[...,0]-target)[target<1])<1
    automatic=engine.correct_background(data,1,engine.background_model(data))
    assert np.std((corrected[...,0]-target)[target<1])<np.std((automatic[...,0]-target)[target<1])
    rect=(30,20,250,200);cropped=data[20:200,30:250];new=cropped_coefficients(model,rect,data.shape)
    # The fitted constant is intentionally retained, so cropped output differs
    # by a constant but has identical spatial correction and target structure.
    a=engine.correct_background(cropped,1,new);b=corrected[20:200,30:250]
    assert np.std(a-b)<.002
    np.testing.assert_array_equal(data,original)
    with pytest.raises(ValueError):fit_sky(data,dict(order=2,points=[[.5,.5]]*12))
    with pytest.raises(ValueError):validate_extraction(dict(order=1,points=[[float('nan'),.5]]*6))


def test_background_dialog_undo_project_reset_and_crop(tmp_path):
    app,w=app_and_window(tmp_path);data,config,_,_=field();w.loaded(data,fits.Header());settle(app,w)
    dialog=BackgroundDialog(data,config);dialog.show();app.processEvents()
    before=len(dialog.view.points);dialog.point(.5,.5);assert len(dialog.view.points)==before+1;dialog.point(.5,.5);assert len(dialog.view.points)==before
    dialog.apply();assert dialog.config==config;dialog.close()
    w.commit_history();w.background_fit=copy.deepcopy(config);w.background=w.make_background(w.linear);w.sliders['Background correction %'].setValue(100);w.commit_history();settle(app,w)
    saved=w.edit_state();w.undo_edit();assert w.background_fit is None;w.redo_edit();assert w.background_fit==config
    path=tmp_path/'sky.astro';w.save_project_path(path);settle(app,w);w.new_project(True);w.open_project_path(path);settle(app,w)
    assert w.edit_state()==saved and not w._dirty
    w.select_crop(30,20,250,200);w.crop_selected();w.undo_edit();assert w.background_fit==config
    w.reset_adjustments();assert w.background_fit is None;w.undo_edit();assert w.background_fit==config
    w.close();settle(app,w)


def test_editor_controls_real_clicks_restore_automatic_and_raster_export(tmp_path,monkeypatch):
    from PySide6 import QtWidgets as W,QtGui
    from PIL import Image
    app,w=app_and_window(tmp_path);data,config,_,_=field();w.loaded(data,fits.Header());settle(app,w)
    w.select_crop(30,20,250,200);w.crop_selected();settle(app,w)
    dialog=BackgroundDialog(w.original_linear,config,w);dialog.show();app.processEvents()
    assert dialog.view.source_size==(300,240)  # Full original field, despite crop.
    point=dialog.view.mapFromScene(QtCore.QPointF(150,120));before=len(dialog.view.points)
    QTest.mouseClick(dialog.view.viewport(),QtCore.Qt.LeftButton,pos=point);app.processEvents()
    assert len(dialog.view.points)==before+1
    QTest.mouseClick(dialog.view.viewport(),QtCore.Qt.LeftButton,pos=point);app.processEvents()
    assert len(dialog.view.points)==before
    start=dialog.view.transform().m11()
    wheel=QtGui.QWheelEvent(QtCore.QPointF(point),QtCore.QPointF(dialog.view.mapToGlobal(point)),QtCore.QPoint(),QtCore.QPoint(0,120),QtCore.Qt.NoButton,QtCore.Qt.NoModifier,QtCore.Qt.NoScrollPhase,False)
    W.QApplication.sendEvent(dialog.view.viewport(),wheel);app.processEvents()
    assert dialog.view.transform().m11()>start
    QTest.mousePress(dialog.view.viewport(),QtCore.Qt.RightButton,pos=point)
    assert dialog.view.pan_start is not None
    QTest.mouseMove(dialog.view.viewport(),point+QtCore.QPoint(10,10))
    QTest.mouseRelease(dialog.view.viewport(),QtCore.Qt.RightButton,pos=point+QtCore.QPoint(10,10))
    assert dialog.view.pan_start is None
    dialog.apply();monkeypatch.setattr('app.BackgroundDialog',lambda *a:dialog)
    monkeypatch.setattr(dialog,'exec',lambda:W.QDialog.Accepted)
    w.edit_background();settle(app,w)
    assert w.background_fit==config and w.sliders['Background correction %'].value()==100
    assert w._dirty
    fits_path=tmp_path/'linear.fits';png_path=tmp_path/'shown.png'
    rendered=engine.render(w.linear,*w.settings(),model=w.background)
    engine.save(fits_path,w.linear,rendered,w.header);engine.save(png_path,w.linear,rendered,w.header)
    np.testing.assert_array_equal(engine.read_fits(fits_path)[0],data[20:200,30:250])
    with Image.open(png_path) as shown:np.testing.assert_array_equal(np.asarray(shown),np.round(rendered*255).astype('uint8'))
    w.restore_full_frame();assert w.background_fit==config and w.linear.shape==data.shape
    dialog.restore_auto();w.edit_background();settle(app,w);assert w.background_fit is None
    w.undo_edit();assert w.background_fit==config
    w.new_project(True);assert w.background_fit is None
    w.close();settle(app,w)
