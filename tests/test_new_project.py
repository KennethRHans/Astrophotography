import time
import numpy as np
from astropy.io import fits
from PySide6 import QtCore, QtWidgets
from app import Window
from project_store import load_project


def make_window(tmp_path, ask=True):
    qt=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    store=QtCore.QSettings(str(tmp_path/'settings.ini'),QtCore.QSettings.IniFormat)
    store.setValue('files/last_fits_directory','/chosen/exposures')
    window=Window(ask_on_close=ask,settings=store)
    image=np.random.default_rng(2).uniform(100,1000,(30,40,3)).astype('float32')
    window.loaded(image,fits.Header())
    window.files.addItem('/chosen/exposures/light.fit')
    window.sliders['Sky brightness (stops ×100)'].setValue(50)
    window.commit_history()
    return qt,window,image


def test_new_project_cancel_and_discard_preserve_preferences(tmp_path,monkeypatch):
    qt,window,image=make_window(tmp_path)
    monkeypatch.setattr(QtWidgets.QMessageBox,'question',lambda *args:QtWidgets.QMessageBox.Cancel)
    window.new_project()
    assert window.linear is image and window.files.count()==1
    gpu=window.gpu;theme=window.theme_name
    actions=window.findChild(QtWidgets.QToolBar).actions()
    assert actions.index(window.new_project_action)+1==actions.index(window.open_project_action)
    monkeypatch.setattr(QtWidgets.QMessageBox,'question',lambda *args:QtWidgets.QMessageBox.Discard)
    window.new_project()
    assert window.linear is None and window.original_linear is None
    assert window.files.count()==0 and not window.history.can_undo
    assert not window.save_project_action.isEnabled() and not window.undo_action.isEnabled()
    assert window.preview.item.pixmap().isNull() and not window._dirty
    assert window.settings_store.value('files/last_fits_directory')=='/chosen/exposures'
    assert window.gpu is gpu and window.theme_name==theme
    window.loaded(image,fits.Header())
    assert window.export.isEnabled() and window.sliders['Sky brightness (stops ×100)'].value()==0
    window.ask_on_close=False;window.close()


def test_new_project_saves_before_clearing(tmp_path,monkeypatch):
    qt,window,image=make_window(tmp_path)
    path=tmp_path/'saved.astro'
    monkeypatch.setattr(QtWidgets.QMessageBox,'question',lambda *args:QtWidgets.QMessageBox.Save)
    monkeypatch.setattr(window,'save_project_dialog',lambda **kwargs:window.save_project_path(path,kwargs['after_save']))
    window.new_project()
    assert window.linear is image
    deadline=time.monotonic()+15
    while (window.project_worker is not None or window.linear is not None) and time.monotonic()<deadline:
        qt.processEvents();time.sleep(.01)
    assert window.linear is None
    restored,header,meta=load_project(path)
    np.testing.assert_array_equal(restored,image)
    assert meta['state']['sliders']['Sky brightness (stops ×100)']==50
    window.close()


def test_toolbar_review_selects_files_then_opens_existing_analysis(tmp_path,monkeypatch):
    qt=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window=Window(ask_on_close=False)
    seen=[]
    monkeypatch.setattr(window,'add_files',lambda:window.files.addItem('/selected/light.fit'))
    monkeypatch.setattr(window,'review_exposures',lambda:seen.append(window.files.item(0).text()))
    window.exposure_review_action.trigger()
    assert seen==['/selected/light.fit']
    window.worker=object();window.update_actions()
    assert not window.new_project_action.isEnabled() and not window.exposure_review_action.isEnabled()
    window.worker=None;window.close()
