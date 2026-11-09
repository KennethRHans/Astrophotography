import io
from pathlib import Path
import numpy as np
import pytest
from astropy.wcs import WCS
from astropy.io import fits
from PySide6 import QtCore,QtGui,QtWidgets as W
from gaia_matching import GaiaClient,query_region,match_candidates,gaia_matches
from object_identification import IdentificationWorker
from identify_dialog import IdentifyDialog
from privacy_viewer import PrivacyDialog
from test_session_updates import app_and_window,settle,sample
from test_identification import sky_header,wait_dialog


def catalog_row(ident='1234567890123456789',ra=10.68470833,dec=41.26875):
    return dict(id='Gaia DR3:'+ident,name='Gaia DR3 '+ident,category='Stars',ra=ra,dec=dec,epoch=2016.,pmra=0.,pmdec=0.,mag=12.,priority=2)


def test_gaia_csv_exact_ids_query_privacy_and_null_motion():
    seen=[]
    def transport(payload):
        seen.append(payload);return b'source_id,ra,dec,ref_epoch,pmra,pmdec,phot_g_mean_mag\n1234567890123456789,10.68,41.26,2016,NaN,null,12.2\n'
    rows=GaiaClient().query(10.68,41.26,.1,16,transport)
    assert rows[0]['id']=='Gaia DR3:1234567890123456789' and rows[0]['pmra']==0
    payload=seen[0];assert set(payload)=={'REQUEST','LANG','FORMAT','QUERY'}
    assert 'gaiadr3.gaia_source' in payload['QUERY'] and 'TOP 5000' in payload['QUERY']
    assert not any(k in payload for k in ('image','x','y','apikey','header','path'))
    for bad in [b'<html>failure</html>',b'source_id,ra\n2,3\n']:
        with pytest.raises(ValueError):GaiaClient().query(10,20,.1,16,lambda p:bad)
    with pytest.raises(ValueError):GaiaClient().query(float('nan'),20,.1,16,transport)


def test_gaia_match_is_one_to_one_with_residual_and_crop():
    header=sky_header();wcs=WCS(header)
    rows=[catalog_row()];sources=dict(x=[51.,51.1,99.],y=[41.,41.,75.])
    result=match_candidates(wcs,header,(0,0,100,80),rows,sources,5,100)
    assert len(result)==1 and result[0]['match_arcsec']<1e-4
    assert result[0]['x']==50 and result[0]['y']==40
    assert match_candidates(wcs,header,(0,0,20,20),rows,sources,5,100)==[]
    far=dict(x=[91.],y=[71.]);assert match_candidates(wcs,header,(0,0,100,80),rows,far,1,100)==[]


def test_gaia_proper_motion_propagation_and_large_field_guard():
    header=sky_header();header['DATE-OBS']='2026-01-01T12:00:00';wcs=WCS(header)
    moving=catalog_row();moving['pmra']=1000
    # Ten years at 1000 mas/year exceeds a one-arcsecond tolerance.
    import warnings
    from astropy.coordinates import SkyCoord
    from astropy.time import Time
    from astropy import units as u
    coord=SkyCoord(ra=moving['ra']*u.deg,dec=moving['dec']*u.deg,pm_ra_cosdec=1000*u.mas/u.yr,pm_dec=0*u.mas/u.yr,obstime=Time(2016,format='jyear'))
    with warnings.catch_warnings():warnings.simplefilter('ignore');new=coord.apply_space_motion(new_obstime=Time(header['DATE-OBS']))
    from astropy.wcs.utils import skycoord_to_pixel
    x,y=skycoord_to_pixel(new,wcs,origin=0)
    sources=dict(x=[float(x)+1],y=[float(y)+1]);assert len(match_candidates(wcs,header,(0,0,100,80),[moving],sources,1,100))==1
    no_date=header.copy();del no_date['DATE-OBS'];assert not match_candidates(wcs,no_date,(0,0,100,80),[moving],sources,1,100)
    wide=WCS(sky_header(scale=.2))
    with pytest.raises(ValueError,match='smaller crop'):query_region(wide,(0,0,100,80))


def test_gaia_work_requires_query_consent_and_prominent_error(tmp_path):
    app,w=app_and_window(tmp_path);d=IdentifyDialog(sample(),sky_header(),(0,0,96,64),w)
    assert d.start.isEnabled();d.gaia.setChecked(True);assert not d.start.isEnabled()
    d.gaia_consent.setChecked(True);assert d.start.isEnabled()
    d.categories['Stars'].setChecked(False);assert not d.start.isEnabled()
    d.failed('Example service failure');assert d.status.text().startswith('ERROR — ') and 'Example service failure' in d.status.text()
    assert 'border:2px' in d.status.styleSheet() and 'font-weight:bold' in d.status.styleSheet()
    assert d.key_link.text()=='Get Free API Key…' and not hasattr(d,'controls_scroll')
    d.reject();w.close()


def test_gaia_pipeline_cancellation_and_worker_failure_preserves_local_results(tmp_path,monkeypatch):
    import gaia_matching
    app,w=app_and_window(tmp_path)
    class Empty:
        def query(self,*a):return []
    assert gaia_matches(sample(),sky_header(),(0,0,96,64),16,100,client=Empty())==[]
    with pytest.raises(InterruptedError):gaia_matches(sample(),sky_header(),(0,0,96,64),16,100,client=Empty(),cancelled=lambda:True)
    def fail(*a,**k):raise RuntimeError('Gaia unavailable')
    monkeypatch.setattr(gaia_matching,'gaia_matches',fail)
    worker=IdentificationWorker(sample(),sky_header(),(0,0,96,64),dict(gaia=True,categories=['Galaxies','Stars']))
    done=[];warnings=[];worker.done.connect(lambda rows,h:done.append(rows));worker.warning.connect(warnings.append);worker.run()
    assert done and done[0] and warnings and 'Gaia unavailable' in warnings[0]
    w.close()


def test_gaia_matches_survive_project_roundtrip(tmp_path):
    app,w=app_and_window(tmp_path);w.loaded(sample(),fits.Header());settle(app,w)
    item=catalog_row();item.update(x=50.,y=40.,match_arcsec=.2)
    w.add_identified_objects([item],sky_header());assert w.annotations[0]['catalog_id']==item['id']
    path=tmp_path/'gaia.astro';w.save_project_path(path);settle(app,w);w.new_project(True);w.open_project_path(path);settle(app,w)
    assert w.annotations[0]['catalog_id']==item['id'];w.close();settle(app,w)


def test_bundled_privacy_policy_matches_public_text_and_opens_without_browser(tmp_path,monkeypatch):
    app,w=app_and_window(tmp_path);opened=[]
    monkeypatch.setattr(QtGui.QDesktopServices,'openUrl',lambda url:opened.append(url.toString()) or True)
    d=PrivacyDialog(w);assert d.policy_text==Path('PRIVACY.md').read_text()
    assert 'Optional Gaia star matching' in d.browser.toPlainText() and not opened
    d.reject();w.close()


def test_worker_merges_gaia_candidates_with_bundled_objects(tmp_path,monkeypatch):
    import gaia_matching
    app,w=app_and_window(tmp_path)
    a=catalog_row();a.update(x=70.,y=50.,match_arcsec=.3)
    b=catalog_row('2345678901234567890');b.update(x=80.,y=55.,match_arcsec=.6)
    monkeypatch.setattr(gaia_matching,'gaia_matches',lambda *args,**kwargs:[a,b])
    worker=IdentificationWorker(sample(),sky_header(),(0,0,96,64),dict(gaia=True,categories=['Galaxies','Stars'],limit=4))
    result=[];errors=[];worker.done.connect(lambda rows,h:result.append(rows));worker.failed.connect(errors.append);worker.run()
    assert not errors and len(result)==1 and len(result[0])<=4
    assert sum('match_arcsec' in row for row in result[0])==2
    assert any(row['category']=='Galaxies' for row in result[0])
    w.close()


def test_gaia_immediate_http_and_tls_errors_are_specific_not_retried():
    import ssl,urllib.error
    for error,expected in [(urllib.error.HTTPError('https://example.invalid',403,'Forbidden',{},None),'HTTP 403'),(urllib.error.URLError(ssl.SSLCertVerificationError('secret text must not appear')),'TLS certificate verification failed')]:
        calls=[]
        def opener(*args,**kwargs):calls.append(1);raise error
        with pytest.raises(RuntimeError) as exc:GaiaClient(opener=opener,wait=lambda sec:None).query(10,20,.5,16)
        assert expected in str(exc.value) and 'secret text' not in str(exc.value) and len(calls)==1


def test_gaia_transient_retry_and_cancellation():
    import urllib.error
    attempts=[];delays=[];messages=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self,*a):return b'source_id,ra,dec,ref_epoch,pmra,pmdec,phot_g_mean_mag\n1234567890123456789,10,20,2016,,,12\n'
    def opener(request,timeout):
        assert timeout==60;attempts.append(1)
        if len(attempts)==1:raise urllib.error.HTTPError(request.full_url,503,'Unavailable',{'Retry-After':'8'},None)
        return Response()
    rows=GaiaClient(opener=opener,wait=delays.append,progress=messages.append).query(10,20,.5,16)
    assert rows and len(attempts)==2 and delays==[8] and any('Retrying' in m for m in messages)
    state=[]
    def timeout(*a,**k):raise TimeoutError('redacted')
    with pytest.raises(InterruptedError):GaiaClient(opener=timeout,wait=lambda sec:state.append(True),cancelled=lambda:bool(state)).query(10,20,.5,16)


def test_gaia_timeout_has_bounded_attempts_and_safe_diagnostics():
    calls=[]
    def opener(*a,**k):calls.append(1);raise TimeoutError('no raw exception text')
    with pytest.raises(RuntimeError) as exc:GaiaClient(opener=opener,wait=lambda sec:None).query(10,20,1.6,16)
    assert len(calls)==3 and 'timed out' in str(exc.value) and '1.600 degrees' in str(exc.value) and 'attempts 3' in str(exc.value)
    assert 'no raw exception text' not in str(exc.value)


def test_reset_crop_clears_all_crops_and_ratio_in_one_undo(tmp_path):
    app,w=app_and_window(tmp_path);data=sample();header=fits.Header({'CRPIX1':48.,'CRPIX2':32.});w.loaded(data,header);settle(app,w)
    w.labels_panel.text.setText('Target');w.place_label(40,30);w.sliders['Brightness (stops ×100)'].setValue(25)
    w.crop_ratio.setCurrentText('Square (1:1)');w.select_crop(10,8,50,48);w.crop_selected()
    before=w.edit_state();adjustments={name:s.value() for name,s in w.sliders.items()};labels=list(w.annotations)
    w.reset_crop_preview.click()
    np.testing.assert_array_equal(w.linear,data)
    assert w.crop_bounds==(0,0,96,64) and w.applied_crop==(0,0,96,64) and w.crop_ratio.currentText()=='Free'
    assert w.header['CRPIX1']==48 and w.annotations==labels and {name:s.value() for name,s in w.sliders.items()}==adjustments
    w.undo_edit();assert w.edit_state()==before
    w.redo_edit();assert w.crop_ratio.currentText()=='Free' and w.linear.shape==data.shape
    w.select_crop(5,5,50,50);w.restore_crop.click();assert w.crop_bounds==(0,0,96,64)
    w.new_project(True);assert not w.reset_crop_preview.isEnabled();w.close();settle(app,w)


def test_auto_sky_darkens_display_preserves_source_and_undo(tmp_path):
    import engine
    app,w=app_and_window(tmp_path)
    rng=np.random.default_rng(23);data=rng.normal(200,10,(120,160,3)).astype('float32');data[20:25,30:35]=1000
    original=data.copy();w.loaded(data,fits.Header());settle(app,w);w.labels_panel.text.setText('Target');w.place_label(40,30)
    before=w.edit_state();settings=w.settings();shape=w.preview_request()[1]
    def level(values):
        import cv2
        small=cv2.resize(data,shape,interpolation=cv2.INTER_AREA)
        return np.median(engine.render(small,*values,model=w.background))
    previous=level(settings);w.auto_sky_preview.click()
    assert level(w.settings())<previous and w.annotations==before['annotations']
    assert w.sliders['Black percentile ×100'].value()==before['sliders']['Black percentile ×100']
    np.testing.assert_array_equal(data,original);w.undo_edit();assert w.edit_state()==before
    w.redo_edit();assert level(w.settings())<previous
    path=tmp_path/'linear.fits';engine.save(path,w.linear,None,w.header);np.testing.assert_array_equal(engine.read_fits(path)[0],original)
    w.new_project(True);assert not w.auto_sky_preview.isEnabled();w.close();settle(app,w)


def test_gaia_long_retry_after_is_respected_without_retrying_early():
    import urllib.error
    calls=[]
    def opener(*a,**k):calls.append(1);raise urllib.error.HTTPError('https://example.invalid',429,'Rate limited',{'Retry-After':'120'},None)
    with pytest.raises(RuntimeError) as exc:GaiaClient(opener=opener,wait=lambda sec:None).query(10,20,1,16)
    assert len(calls)==1 and '120 seconds' in str(exc.value) and 'HTTP 429' in str(exc.value)
