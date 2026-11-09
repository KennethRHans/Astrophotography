import os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from astropy.io import fits
from PySide6 import QtCore,QtGui,QtWidgets as W
from app import Window
import engine
from project_store import load_project,save_project
from preview_render import PreviewRenderer


def app_and_window(tmp_path,ask=False):
    app=W.QApplication.instance() or W.QApplication([])
    settings=QtCore.QSettings(str(tmp_path/'prefs.ini'),QtCore.QSettings.IniFormat)
    return app,Window(ask_on_close=ask,settings=settings)


def settle(app,window):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.005)
        if window.preview_worker is None and window.project_worker is None and not window.timer.isActive() and not window._preview_pending:return
    raise AssertionError('Background work did not finish')


def sample():return np.random.default_rng(2).uniform(100,1000,(64,96,3)).astype('float32')


def test_new_project_cancel_and_save_preserve_data_and_clear_workspace(tmp_path,monkeypatch):
    app,window=app_and_window(tmp_path,ask=True);window.show()
    data=sample();window.loaded(data,fits.Header({'OBJECT':'Sample'}));window.files.addItem('light.fit')
    window.sliders['Sky background %'].setValue(20);window.commit_history();settle(app,window)
    monkeypatch.setattr(W.QMessageBox,'question',lambda *a,**k:W.QMessageBox.Cancel)
    window.new_project_action.trigger();assert window.linear is data and window.files.count()==1
    path=tmp_path/'saved-before-new.astro'
    monkeypatch.setattr(W.QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    import app as application
    monkeypatch.setattr(application,'select_save_file',lambda *a,**k:str(path))
    monkeypatch.setattr(W.QMessageBox,'question',lambda *a,**k:W.QMessageBox.Save)
    window.new_project_action.trigger();settle(app,window);app.processEvents()
    assert window.linear is None and window.project_path is None and window.files.count()==0
    assert window.preview.item.pixmap().isNull() and window.history.index==-1
    assert not window.step_adjust.isEnabled() and not window.export.isEnabled()
    assert all(s.value()==window.slider_defaults[name] for name,s in window.sliders.items())
    original,header,meta=load_project(path)
    np.testing.assert_array_equal(original,data);assert meta['state']['sliders']['Sky background %']==20
    window.close()


def test_last_fits_folder_and_gpu_preference_survive_reopen_and_new_project(tmp_path,monkeypatch):
    import gpu
    class Device:
        name='Test GPU';disabled=False
        def process(self,image,*a):return image.copy()
    monkeypatch.setattr(gpu,'create_gpu_processor',lambda **kwargs:Device())
    app,window=app_and_window(tmp_path)
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir();window.remember_fits_folder(a/'one.fit')
    seen=[]
    def choose(*args,**kwargs):seen.append(args[2]);return [str(a/'one.fit'),str(a/'two.fit')],''
    import app as application
    def native_choose(title, extensions, multiple=False, initial_directory=None):
        if multiple:
            seen.append(initial_directory);return [str(a/'one.fit'),str(a/'two.fit')]
        return [str(b/'chosen.fit')]
    monkeypatch.setattr(application,'select_files',native_choose)
    monkeypatch.setattr(W.QFileDialog,'getOpenFileNames',choose)
    window.add_files();assert seen==[str(a)]
    monkeypatch.setattr(W.QFileDialog,'getOpenFileName',lambda *a,**k:(str(b/'chosen.fit'),''))
    monkeypatch.setattr(window,'allow_replace',lambda:False)
    window.start(True);assert window.fits_folder()==str(b)
    window.use_gpu.setChecked(True);assert window.gpu.name=='Test GPU'
    window.new_project();assert window.fits_folder()==str(b) and window.use_gpu.isChecked()
    window.close()
    _,reopened=app_and_window(tmp_path)
    assert reopened.use_gpu.isChecked() and reopened.gpu.name=='Test GPU' and reopened.fits_folder()==str(b)
    reopened.use_gpu.setChecked(False);reopened.close()
    _,last=app_and_window(tmp_path);assert not last.use_gpu.isChecked();last.close()


def test_sky_adjustment_changes_shadows_not_bright_stars_and_fits_stays_linear(tmp_path):
    image=np.array([[[.05,.05,.05],[.8,.8,.8],[1,1,1]]],dtype='float32')
    lighter=engine.adjust_sky(image,.5);darker=engine.adjust_sky(image,-.1)
    assert lighter[0,0,0]>image[0,0,0]>darker[0,0,0]
    np.testing.assert_array_equal(lighter[0,1:],image[0,1:])
    data=sample();data[:2]=0;original=data.copy()
    shown=engine.render(data,sky=.5);assert np.all(shown[:2]==0)
    path=tmp_path/'sky.fits';engine.save(path,data,shown,fits.Header())
    reopened,_=engine.read_fits(path);np.testing.assert_array_equal(reopened,original)
    np.testing.assert_array_equal(data,original)


def test_older_project_gets_neutral_sky_setting(tmp_path,monkeypatch):
    import gpu
    class Device:
        name='Test GPU';disabled=False
        def process(self,image,*args):return image.copy()
    monkeypatch.setattr(gpu,'create_gpu_processor',lambda **kwargs:Device())
    app,window=app_and_window(tmp_path);data=sample();window.loaded(data,fits.Header());settle(app,window)
    meta=window.project_manifest();meta['view']['gpu']=True
    for state in [meta['state'],*meta['history']['states']]:state['sliders'].pop('Sky background %')
    path=tmp_path/'old.astro';save_project(path,data,fits.Header(),meta)
    window.sliders['Sky background %'].setValue(60)
    window.open_project_path(path);settle(app,window)
    assert window.use_gpu.isChecked() and window.settings_store.value('processing/use_gpu',False,type=bool)
    assert window.sliders['Sky background %'].value()==0
    assert all(state['sliders']['Sky background %']==0 for state in window.history.states)
    np.testing.assert_array_equal(window.linear,data);window.close()


def test_preview_keeps_ui_alive_coalesces_requests_and_new_project_rejects_old_result(tmp_path,monkeypatch):
    app,window=app_and_window(tmp_path);window.show();data=sample();window.loaded(data,fits.Header());window.preview.set_zoom(1);settle(app,window)
    window.files.addItems([f'frame-{i}.fit' for i in range(546)])
    render=window.preview_renderer.render;calls=[]
    def slow(*args):calls.append(args[2]);time.sleep(.15);return render(*args)
    monkeypatch.setattr(window.preview_renderer,'render',slow)
    beats=[];timer=QtCore.QTimer();timer.setInterval(10);timer.timeout.connect(lambda:beats.append(1));timer.start()
    window.sliders['Sky background %'].setValue(10);window.request_preview()
    for value in range(20,81,5):window.sliders['Sky background %'].setValue(value)
    settle(app,window);timer.stop()
    assert len(beats)>=5 and len(calls)<=3
    assert window._displayed_preview_settings==window.settings()
    image=window.preview.item.pixmap().toImage().convertToFormat(QtGui.QImage.Format_RGB888)
    actual=np.frombuffer(image.bits(),np.uint8).reshape(image.height(),image.bytesPerLine())[:,:image.width()*3].reshape(image.height(),image.width(),3)
    expected=np.round(engine.render(data,*window.settings(),model=window.background)*255).astype('uint8')
    np.testing.assert_array_equal(actual,expected)
    window.sliders['Sky background %'].setValue(-50);window.request_preview();window.new_project()
    settle(app,window)
    assert window.linear is None and window.preview.item.pixmap().isNull() and window.preview_renderer.source is None
    window.close()


def test_preview_reuses_normalization_for_tone_changes(monkeypatch):
    data=sample();renderer=PreviewRenderer();normalize=engine.normalize_image;calls=[]
    def counted(source,*args):
        if source is data:calls.append(1)
        return normalize(source,*args)
    monkeypatch.setattr(engine,'normalize_image',counted)
    settings=(30,.1,1,0,0,(1,1,1),0,1,0)
    model=np.zeros((6,3))
    renderer.render(data,(96,64),settings,model,None,False)
    changed=list(settings);changed[-1]=.2
    result=renderer.render(data,(96,64),tuple(changed),model,None,False)
    assert len(calls)==1
    np.testing.assert_array_equal(result['pixels'],np.round(engine.render(data,*changed,model=model)*255).astype('uint8'))
    before=len(calls);changed[1]=.5;renderer.render(data,(96,64),tuple(changed),model,None,False)
    assert len(calls)==before+1


def test_closing_with_a_preview_in_flight_prompts_only_once(tmp_path,monkeypatch):
    app,window=app_and_window(tmp_path,ask=True);window.show();window.loaded(sample(),fits.Header());settle(app,window)
    original=window.preview_renderer.render
    def slow(*args):time.sleep(.15);return original(*args)
    monkeypatch.setattr(window.preview_renderer,'render',slow)
    prompts=[]
    monkeypatch.setattr(W.QMessageBox,'question',lambda *a,**k:prompts.append(1) or W.QMessageBox.Discard)
    window.sliders['Sky background %'].setValue(20);window.request_preview();window.close()
    settle(app,window);app.processEvents()
    assert prompts==[1] and not window.isVisible() and window.preview_worker is None
