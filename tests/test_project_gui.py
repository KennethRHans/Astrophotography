import os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from astropy.io import fits
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from app import Window


def finish_io(app,window):
    deadline=time.monotonic()+15
    while window.project_worker is not None and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    assert window.project_worker is None
    assert window._project_io_ok


def test_undo_crop_reset_and_project_reopen(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    window=Window(ask_on_close=True);window.show();app.processEvents()
    data=np.random.default_rng(17).uniform(100,1000,(120,160,3)).astype('float32')
    window.loaded(data,fits.Header({'OBJECT':'C 56','CRPIX1':80.,'CRPIX2':60.}));app.processEvents()
    window.sliders['Stretch'].setSliderDown(True)
    window.sliders['Stretch'].setValue(40);QTest.qWait(450)
    assert window.history.index==0
    window.sliders['Stretch'].setValue(65);window.sliders['Stretch'].setSliderDown(False)
    assert window.history.index==1
    window.sliders['Saturation %'].setValue(140);window.commit_history()
    window.undo_action.trigger();assert window.sliders['Saturation %'].value()==100
    window.redo_action.trigger();assert window.sliders['Saturation %'].value()==140
    window.select_crop(10,20,150,110);window.crop_selected()
    assert window.applied_crop==(10,20,150,110)
    window.undo_edit();np.testing.assert_array_equal(window.linear,data)
    window.redo_edit();np.testing.assert_array_equal(window.linear,data[20:110,10:150])
    before=window.edit_state();window.reset_adjustments();window.undo_edit();assert window.edit_state()==before
    window.files.addItem('C:/missing/light.fit')
    path=tmp_path/'C56.astro';window.save_project_path(path);finish_io(app,window)
    assert not window._dirty
    original_display=window.linear.copy();saved=window.edit_state()
    window.sliders['Stretch'].setValue(80);window.commit_history();assert window._dirty
    window.open_project_path(path);finish_io(app,window)
    assert window.edit_state()==saved and not window._dirty
    np.testing.assert_array_equal(window.linear,original_display)
    assert window.files.item(0).text()=='C:/missing/light.fit'
    assert window.histogram.bins.sum()>0
    assert window.undo_action.isEnabled()
    window.undo_edit();assert window.edit_state()!=saved
    monkeypatch.setattr(QMessageBox,'question',lambda *args,**kwargs: QMessageBox.Save)
    window.close();finish_io(app,window);app.processEvents()
    assert not window.isVisible()
    from project_store import load_project
    assert load_project(path)[2]['state']==window.edit_state()


def test_new_brand_bayer_guidance_and_gpu_worker(monkeypatch):
    from PySide6.QtWidgets import QLabel
    from app import Worker
    import engine,gpu
    app=QApplication.instance() or QApplication([])
    window=Window(ask_on_close=False)
    assert window.windowTitle().startswith('Easy Astro Studio')
    assert not any('Not affiliated' in label.text() for label in window.findChildren(QLabel))
    assert window.artwork_path.name=='easy-astro-logo.png'
    for pattern in ('RGGB','BGGR','GRBG','GBRG','None','Auto'):
        window.bayer.setCurrentText(pattern)
        assert window.bayer_help.text()
    window.bayer.setCurrentText('GRBG');assert 'Seestar S50 Pro' in window.bayer_help.text()
    window.close()
    class Device:
        name='Test device'
    monkeypatch.setattr(gpu,'GpuProcessor',Device)
    calls=[]
    def stack(*args,**kwargs):
        calls.append(kwargs['gpu']);return np.ones((2,2,3),dtype='float32'),fits.Header()
    monkeypatch.setattr(engine,'stack',stack)
    worker=Worker(['a.fit','b.fit'],'Auto',use_gpu=True)
    messages=[];worker.message.connect(messages.append);worker.run()
    assert isinstance(calls[-1],Device)
    def fail():raise RuntimeError('No GPU')
    monkeypatch.setattr(gpu,'GpuProcessor',fail)
    worker.run()
    assert calls[-1] is None and any('bounded CPU chunks' in line for line in messages)


def test_sandbox_project_restores_image_without_reusing_source_access(tmp_path, monkeypatch):
    import app as application
    monkeypatch.setattr(application, 'sandboxed', lambda: True)
    qt = QApplication.instance() or QApplication([])
    window = Window(ask_on_close=False)
    pixels = np.ones((30, 40, 3), dtype='float32') * 100
    window.loaded(pixels, fits.Header())
    window.source_paths = ['/unselected/light.fit']
    window.files.addItem('/unselected/light.fit')
    path = tmp_path / 'portable.astro'
    window.save_project_path(path)
    finish_io(qt, window)
    window.open_project_path(path)
    finish_io(qt, window)
    np.testing.assert_array_equal(window.original_linear, pixels)
    assert window.source_paths == ['/unselected/light.fit']
    assert window.files.count() == 0
    assert not window.run.isEnabled()
    assert window.export.isEnabled()
    assert 'select them with Add exposures' in window.log.toPlainText()
    window.close()
