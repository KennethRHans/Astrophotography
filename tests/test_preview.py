import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from PySide6 import QtCore,QtGui,QtWidgets as W
from PySide6.QtTest import QTest
from astropy.io import fits
from app import Window,WheelSlider


def test_crop_edges_and_zoom_keep_source_pixels():
    app=W.QApplication.instance() or W.QApplication([])
    window=Window(ask_on_close=False);window.show();app.processEvents()
    data=np.random.default_rng(9).uniform(100,400,(800,1200,3)).astype('float32')
    window.loaded(data,fits.Header({'OBJECT':'C 56'}));app.processEvents()
    assert not hasattr(window,'crop_margins')
    window.select_crop(300,200,900,600)
    window.preview.set_zoom(1);window.preview.centerOn(850,400);app.processEvents()
    view=window.preview
    start=view.mapFromScene(QtCore.QPointF(900,400));end=view.mapFromScene(QtCore.QPointF(850,400))
    assert view.viewport().rect().contains(start)
    QTest.mousePress(view.viewport(),QtCore.Qt.LeftButton,pos=start)
    QTest.mouseMove(view.viewport(),end);QTest.mouseRelease(view.viewport(),QtCore.Qt.LeftButton,pos=end)
    assert window.crop_bounds == (300,200,850,600)
    saved_bounds=window.crop_bounds
    window.zoom_out.click();window.zoom_fit.click();app.processEvents()
    assert window.crop_bounds==saved_bounds
    window.apply_crop.click()
    np.testing.assert_array_equal(window.linear,data[200:600,300:850])
    window.restore_crop.click();assert window.linear is data
    assert window.use_gpu.parentWidget() is not window.step_adjust
    window.close()


def test_wheel_sensitive_area_is_ten_percent_narrower():
    app=W.QApplication.instance() or W.QApplication([])
    slider=WheelSlider(QtCore.Qt.Horizontal);slider.resize(200,36);slider.setRange(0,100);slider.setValue(50)
    def wheel(x):
        event=QtGui.QWheelEvent(QtCore.QPointF(x,18),QtCore.QPointF(x,18),QtCore.QPoint(),QtCore.QPoint(0,120),QtCore.Qt.NoButton,QtCore.Qt.NoModifier,QtCore.Qt.NoScrollPhase,False)
        W.QApplication.sendEvent(slider,event)
        return event
    event=wheel(5)
    assert slider.value()==50 and not event.isAccepted()
    wheel(100);assert slider.value()!=50
