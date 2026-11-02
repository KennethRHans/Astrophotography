import os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from scipy.ndimage import gaussian_filter
from astropy.io import fits
from PySide6 import QtWidgets as W
from frame_quality import measure,rate_batch
from frame_review import FrameReviewDialog
from app import Window


def stars(sigma=1.3,seed=5):
    rng=np.random.default_rng(seed);image=np.zeros((256,256),dtype=np.float32)
    for y in range(30,230,36):
        for x in range(30,230,36):image[y,x]=rng.uniform(6000,10000)
    image=gaussian_filter(image,sigma)+300+rng.normal(0,2,image.shape)
    return np.repeat(image.astype(np.float32)[...,None],3,axis=-1)


def test_quality_favors_sharp_round_stars_and_keeps_groups_separate():
    header=fits.Header({'OBJECT':'Test target','EXPTIME':20})
    sharp=measure(stars(),header);blurred=measure(stars(2.8),header);trailed=measure(stars((3.,1.3)),header)
    assert sharp['stars']>=20 and blurred['stars']>=20
    assert sharp['fwhm']<blurred['fwhm'] and trailed['elongation']>sharp['elongation']
    results=rate_batch({'sharp':sharp,'blurred':blurred,'trailed':trailed})
    assert results['sharp']['score']>results['blurred']['score']
    assert results['sharp']['score']>results['trailed']['score']
    other=measure(stars(),fits.Header({'OBJECT':'Different target','EXPTIME':20}))
    assert rate_batch({'sharp':sharp,'other':other})['sharp']['score'] is None
    noise=measure(np.repeat(np.random.default_rng(1).normal(300,2,(256,256,1)).astype('float32'),3,axis=-1),header)
    assert noise['stars']<6 and rate_batch({'noise':noise})['noise']['score'] is None
    assert sharp['score'] is None  # rating never mutates original measurements


def finish(app,dialog):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
        if dialog.worker is None:return
    raise AssertionError('Exposure review worker did not finish')


def test_review_preview_analysis_reference_and_main_image_preservation(tmp_path,monkeypatch):
    app=W.QApplication.instance() or W.QApplication([])
    paths=[]
    for i,sigma in enumerate([2.8,1.3,(3.,1.3)]):
        p=tmp_path/f'{i}.fit';fits.writeto(p,stars(sigma)[...,0],fits.Header({'OBJECT':'Test','EXPTIME':20}));paths.append(str(p))
    dialog=FrameReviewDialog(paths,'None');dialog.show();app.processEvents();finish(app,dialog)
    assert not dialog.view.item.pixmap().isNull()
    dialog.start_analysis();finish(app,dialog)
    assert len(dialog.records)==3 and dialog.best.isEnabled()
    assert max(dialog.records,key=lambda p:dialog.records[p]['score'])==paths[1]
    dialog.select_best();finish(app,dialog)
    assert dialog.selected_path()==paths[1]
    dialog.choose_reference();assert dialog.chosen_path==paths[1] and dialog.result()==W.QDialog.Accepted
    window=Window(ask_on_close=False);window.files.addItems(paths)
    data=stars();window.loaded(data,fits.Header({'OBJECT':'Loaded stack'}));original=window.linear
    window.sliders['Stretch'].setValue(47);before=window.edit_state()
    def choose(self):self.chosen_path=paths[1];return W.QDialog.Accepted
    monkeypatch.setattr(FrameReviewDialog,'exec',choose)
    window.review_exposures()
    assert window.files.item(0).text()==paths[1]
    assert window.files.count()==3 and window.linear is original and window.edit_state()==before
    captured=[];monkeypatch.setattr(W.QMessageBox,'about',lambda *args:captured.append(args[-1]))
    window.about_action.trigger();assert 'Version 0.15.0' in captured[0]
    window.close()


def test_closing_review_cancels_worker_before_dialog_is_destroyed(tmp_path):
    app=W.QApplication.instance() or W.QApplication([])
    paths=[]
    for i in range(3):
        path=tmp_path/f'{i}.fits';fits.writeto(path,stars()[...,0]);paths.append(str(path))
    dialog=FrameReviewDialog(paths,'None');dialog.show()
    dialog.start_analysis();assert dialog.worker is not None
    dialog.reject();assert dialog._closing
    finish(app,dialog)
    assert not dialog.isVisible() and dialog.result()==W.QDialog.Rejected


def test_review_sorts_all_columns_and_keeps_metrics_with_their_files():
    from PySide6 import QtCore
    app=W.QApplication.instance() or W.QApplication([])
    dialog=FrameReviewDialog(['c.fit','a.fit','b.fit'],'None',selected='c.fit')
    rows={p:dict(score=v,stars=int(v),fwhm=v,elongation=v,status=p,group=('same',)) for p,v in [('c.fit',2.),('a.fit',100.),('b.fit',10.)]}
    for path,row in rows.items():dialog.receive_row(path,row)
    for column in range(6):
        for order in (QtCore.Qt.AscendingOrder,QtCore.Qt.DescendingOrder):
            dialog.table.sortItems(column,order)
            values=[dialog.table.item(i,column).text() if column in (0,5) else dialog.table.item(i,column).data(QtCore.Qt.UserRole) for i in range(3)]
            assert values==sorted(values,reverse=order==QtCore.Qt.DescendingOrder)
            assert dialog.selected_path()=='c.fit'
    dialog.table.sortItems(1,QtCore.Qt.DescendingOrder)
    rows['c.fit'].update(score=120.,stars=120,fwhm=12.,elongation=1.2)
    dialog.receive_row('c.fit',rows['c.fit'])
    for i in range(3):
        path=dialog.table.item(i,0).data(QtCore.Qt.UserRole)
        assert dialog.table.item(i,1).data(QtCore.Qt.UserRole)==rows[path]['score']
        assert dialog.table.item(i,2).data(QtCore.Qt.UserRole)==rows[path]['stars']
        assert dialog.table.item(i,3).data(QtCore.Qt.UserRole)==rows[path]['fwhm']
    assert dialog.selected_path()=='c.fit'
    dialog.close()
