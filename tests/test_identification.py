import io,time,copy
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS,Sip
from PySide6 import QtCore,QtWidgets as W
from scipy.ndimage import gaussian_filter
from object_identification import celestial_wcs,identify_catalog,extract_sources,NovaClient,catalog,IdentificationWorker
from identify_dialog import IdentifyDialog
from test_session_updates import app_and_window,settle,sample


def sky_header(ra=10.68470833,dec=41.26875,scale=1/3600):
    w=WCS(naxis=2);w.wcs.crpix=[51,41];w.wcs.cd=np.array([[-scale,0],[0,scale]]);w.wcs.crval=[ra,dec];w.wcs.ctype=['RA---TAN','DEC--TAN'];return w.to_header()


def row(name='Test',x=10.68470833,y=41.26875,category='Galaxies',mag=5.):return dict(id='test:'+name,name=name,category=category,ra=x,dec=y,mag=mag,priority=1)


def test_wcs_projection_rotation_mirror_sip_and_crop():
    for transform in [np.array([[-1,0],[0,1]]),np.array([[0,1],[1,0]]),np.array([[.8,.6],[-.6,.8]])]:
        w=WCS(sky_header());w.wcs.cd=transform/3600
        a=np.zeros((3,3));a[2,0]=1e-5;w.sip=Sip(a,a,None,None,w.wcs.crpix);w.wcs.ctype=['RA---TAN-SIP','DEC--TAN-SIP']
        header=w.to_header(relax=True)
        positions=np.array([[50,40],[60,30],[85,75]])
        coordinates=w.all_pix2world(positions,0)
        objects=[row(str(i),*world) for i,world in enumerate(coordinates)]
        matches=identify_catalog(header,(80,100,3),objects=objects,crop=(40,20,70,50))
        assert len(matches)==2
        for r in matches:np.testing.assert_allclose([r['x'],r['y']],positions[int(r['name'])],atol=1e-3)
    header=sky_header(ra=359.999,dec=85)
    matches=identify_catalog(header,(80,100,3),objects=[row(x=359.999,y=85)])
    assert len(matches)==1 and abs(matches[0]['x']-50)<1e-5


def test_rejects_header_placeholders_and_invalid_scales():
    zero=sky_header();zero['CDELT1']=0;zero['CDELT2']=0
    for header in [fits.Header(),fits.Header({'RA':10,'DEC':20}),zero,sky_header(scale=10)]:
        with pytest.raises(Exception):celestial_wcs(header,(80,100,3))
    header=sky_header();header['CPDIS1']='LOOKUP'
    with pytest.raises(ValueError,match='external'):celestial_wcs(header,(80,100,3))


def test_real_catalog_known_target_filters_unknown_and_limits():
    data=catalog();assert len(data)>14000 and all(r['category'] in ('Galaxies','Nebulae','Clusters','Stars') for r in data)
    m31=next(r for r in data if r['id']=='OpenNGC:NGC0224')
    header=sky_header(m31['ra'],m31['dec'])
    matches=identify_catalog(header,(80,100,3),categories=['Galaxies'])
    match=next(r for r in matches if r['id']==m31['id']);assert 'M 31' in match['name'];np.testing.assert_allclose([match['x'],match['y']],[50,40],atol=1e-5)
    objects=[row('Bright',mag=2),row('Faint',mag=19),row('Unknown',mag=None),row('Star',category='Stars')]
    matches=identify_catalog(sky_header(),(80,100,3),objects=objects,categories=['Galaxies'],magnitude=10,include_unknown=False)
    assert [r['name'] for r in matches]==['Bright']
    assert len(identify_catalog(sky_header(),(80,100,3),objects=objects,limit=1))==1


def test_source_extraction_coordinates_no_pixels_and_hot_pixel_rejection():
    rng=np.random.default_rng(7);image=np.zeros((512,640),dtype='float32');points=[]
    for y in range(40,480,60):
        for x in range(40,600,60):image[y,x]=rng.uniform(300,800);points.append((x,y))
    image=gaussian_filter(image,1.4)+rng.normal(100,.1,image.shape).astype('float32');image[10,10]=5000
    data=np.repeat(image[...,None],3,axis=-1);sources=extract_sources(data)
    assert set(sources)=={'x','y','image_width','image_height'} and len(sources['x'])>40
    for x,y in zip(sources['x'],sources['y']):assert min(np.hypot(x-1-px,y-1-py) for px,py in points)<1
    with pytest.raises(ValueError,match='Fewer'):extract_sources(np.ones((40,40,3),dtype='float32'))


def wcs_bytes(header):
    stream=io.BytesIO();fits.PrimaryHDU(header=header).writeto(stream);return stream.getvalue()


def test_nova_api_contract_private_source_list_queue_and_failure():
    header=sky_header();seen=[];polled=[]
    def transport(path,payload,binary):
        seen.append((path,payload,binary))
        if path=='/api/login':return {'status':'success','session':'test-session'}
        if path=='/api/upload':return {'status':'success','subid':123}
        if path=='/api/submissions/123':return {'jobs':[None,456]}
        if path=='/api/jobs/456':polled.append(1);return {'status':'solving' if len(polled)==1 else 'success'}
        if path=='/wcs_file/456':return wcs_bytes(header)
        raise AssertionError(path)
    sources=dict(x=[1.,2.],y=[3.,4.],image_width=100,image_height=80)
    solved,job=NovaClient(transport).solve(sources,'fake-key',wait=lambda:None)
    assert job==456;celestial_wcs(solved,(80,100,3))
    upload=next(payload for path,payload,binary in seen if path=='/api/upload')
    assert upload['publicly_visible']=='n' and upload['allow_commercial_use']=='n' and upload['allow_modifications']=='n'
    assert set(sources)<=set(upload) and 'apikey' not in upload and not any(k in upload for k in ('filename','image','header','file'))
    with pytest.raises(InterruptedError):NovaClient(transport).solve(sources,'fake-key',cancelled=lambda:True)
    with pytest.raises(TimeoutError):NovaClient(transport).solve(sources,'fake-key',timeout=-1)
    bad=NovaClient(lambda *a:{'status':'error'})
    with pytest.raises(RuntimeError):bad.solve(sources,'fake-key')


def wait_dialog(app,d):
    deadline=time.monotonic()+10
    while d.worker is not None and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
    assert d.worker is None


def test_dialog_consent_offline_review_and_no_key_persistence(tmp_path,monkeypatch):
    app,w=app_and_window(tmp_path);image=sample();d=IdentifyDialog(image,fits.Header(),(0,0,96,64),w)
    assert d.method.currentIndex()==0 and not d.start.isEnabled()
    assert not d.image_thumbnail.pixmap().isNull() and 'Image loaded' in d.source_summary.text()
    assert 'no usable sky-coordinate' in d.local_note.text()
    d.choose_online.click();assert d.method.currentIndex()==1 and not d.start.isEnabled()
    d.key.setText('fake-key');assert not d.start.isEnabled()
    d.consent.setChecked(True);assert d.start.isEnabled()
    d.consent.setChecked(False);assert not d.start.isEnabled();d.reject();assert not d.key.text()
    header=sky_header();d=IdentifyDialog(np.ones((80,100,3),dtype='float32'),header,(0,0,100,80),w)
    assert d.method.currentIndex()==0 and d.start.isEnabled()
    d.identify();wait_dialog(app,d);assert d.table.rowCount()>0 and d.apply.isEnabled()
    d.table.sortItems(1,QtCore.Qt.DescendingOrder);selected=d.selected_rows();assert all('x' in r for r in selected)
    d.check_rows(QtCore.Qt.Unchecked);assert not d.apply.isEnabled();d.check_rows(QtCore.Qt.Checked);assert d.apply.isEnabled()
    d.reject();w.close()


def test_identified_labels_dedupe_undo_project_and_new_project(tmp_path):
    from project_store import load_project
    app,w=app_and_window(tmp_path);w.loaded(sample(),fits.Header());settle(app,w)
    matches=[dict(row(),x=50.,y=40.)];header=sky_header()
    w.add_identified_objects(matches,header);assert len(w.annotations)==1 and w._dirty
    w.add_identified_objects(matches,header);assert len(w.annotations)==1
    w.undo_edit();assert not w.annotations;w.redo_edit();assert len(w.annotations)==1
    path=tmp_path/'identified.astro';w.save_project_path(path);settle(app,w)
    meta=load_project(path)[2];assert 'fake-key' not in str(meta) and 'identification_wcs' in meta
    w.new_project(True);assert w.solution_header is None
    w.open_project_path(path);settle(app,w);assert w.solution_header is not None and len(w.annotations)==1 and not w._dirty
    w.close();settle(app,w)


def test_cancel_dialog_waits_for_worker_without_destroying_thread(tmp_path):
    app,w=app_and_window(tmp_path)
    class Slow(QtCore.QThread):
        progress=QtCore.Signal(str);done=QtCore.Signal(object,object);failed=QtCore.Signal(str)
        def __init__(self,*a,**k):super().__init__()
        def run(self):
            for i in range(50):
                if self.isInterruptionRequested():return
                self.msleep(10)
    d=IdentifyDialog(sample(),sky_header(),(0,0,96,64),w,worker_factory=Slow);d.show();d.identify();d.reject()
    assert d.worker is not None and d.closing
    wait_dialog(app,d);app.processEvents();assert not d.isVisible();w.close()


def test_https_form_encoding_and_sanitized_network_failures():
    import json,urllib.parse
    client=NovaClient();seen=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return b'{"status":"success","session":"session"}'
    class Opener:
        def open(self,request,timeout):seen.append((request,timeout));return Response()
    client.opener=Opener();result=client.request('/api/login',{'apikey':'test-secret'})
    request,timeout=seen[0];assert request.full_url=='https://nova.astrometry.net/api/login' and timeout==20
    assert json.loads(urllib.parse.parse_qs(request.data.decode())['request-json'][0])=={'apikey':'test-secret'}
    assert result['session']=='session'
    class Broken:
        def open(self,*args,**kwargs):raise OSError('test-secret must not be logged')
    client.opener=Broken()
    with pytest.raises(RuntimeError) as exc:client.request('/api/login',{'apikey':'test-secret'})
    assert 'test-secret' not in str(exc.value)


def test_full_catalog_projection_through_sip_does_not_fail_on_far_away_objects():
    w=WCS(sky_header());a=np.zeros((3,3));a[2,0]=1e-5;w.sip=Sip(a,a,None,None,w.wcs.crpix);w.wcs.ctype=['RA---TAN-SIP','DEC--TAN-SIP']
    matches=identify_catalog(w.to_header(relax=True),(80,100,3))
    assert any(r['id']=='OpenNGC:NGC0224' for r in matches)


def test_main_window_identifies_current_image_and_shows_filename_preview(tmp_path,monkeypatch):
    import app as app_module
    app,w=app_and_window(tmp_path);data=sample();w.loaded(data,fits.Header({'OBJECT':'M77'}));settle(app,w)
    w.source_paths=['C:/Pictures/Stacked_M77.fit'];w.select_crop(5,4,90,60);w.crop_selected()
    captured=[]
    class Capture(IdentifyDialog):
        def exec(self):
            captured.append(self)
            assert self.image is w.original_linear
            assert self.crop==w.applied_crop==(5,4,90,60)
            assert 'Stacked_M77.fit' in self.source_summary.text()
            assert '96 × 64' in self.source_summary.text() and '85 × 56' in self.source_summary.text()
            assert not self.image_thumbnail.pixmap().isNull()
            assert self.method.currentIndex()==0 and not self.start.isEnabled()
            return W.QDialog.Rejected
    monkeypatch.setattr(app_module,'IdentifyDialog',Capture)
    w.identify_objects();assert len(captured)==1
    w.close();settle(app,w)
