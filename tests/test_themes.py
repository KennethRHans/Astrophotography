import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from astropy.io import fits
from PySide6 import QtCore,QtGui,QtWidgets as W
from app import Window
from themes import THEMES


def test_theme_persistence_and_image_history_are_independent(tmp_path,monkeypatch):
    app=W.QApplication.instance() or W.QApplication([])
    path=str(tmp_path/'appearance.ini')
    def settings():return QtCore.QSettings(path,QtCore.QSettings.IniFormat)
    window=Window(ask_on_close=False,settings=settings())
    data=np.random.default_rng(7).uniform(100,500,(32,40,3)).astype('float32')
    window.loaded(data,fits.Header());window.commit_history()
    rendered=window.preview.item.pixmap().toImage().copy();state=window.edit_state();history=list(window.history.states)
    # Switching UI themes must not invoke scientific rendering.
    monkeypatch.setattr(window,'update_preview',lambda:(_ for _ in ()).throw(AssertionError('Theme rerendered image')))
    for name,colors in THEMES.items():
        window.theme_actions[name].trigger()
        assert window.theme_name==name and window.theme_actions[name].isChecked()
        assert app.palette().color(QtGui.QPalette.WindowText).name()==colors['fg']
        assert 'https://planner.astrivanta.com' in window.planner_banner.text()
        assert window.linear is data and window.edit_state()==state and window.history.states==history
        assert window.preview.item.pixmap().toImage()==rendered
    window.theme_actions['Light'].trigger();window.close()
    reopened=Window(ask_on_close=False,settings=settings())
    assert reopened.theme_name=='Light' and reopened.theme_actions['Light'].isChecked()
    reopened.close()
    broken=settings();broken.setValue('appearance/theme','Missing theme')
    fallback=Window(ask_on_close=False,settings=broken);assert fallback.theme_name=='Dark';fallback.close()
