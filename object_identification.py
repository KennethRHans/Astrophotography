"""Catalog projection and optional Astrometry.net source-list solving."""
import gzip
from network_tls import https_context
import http.cookiejar
import io
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path
import warnings
import cv2
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS,NoConvergence
from astropy.wcs.utils import skycoord_to_pixel,proj_plane_pixel_scales
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy import units as u
from PySide6 import QtCore

SERVICE='https://nova.astrometry.net'
CATEGORIES=('Galaxies','Nebulae','Clusters','Stars')


def celestial_wcs(header,shape):
    """Reject placeholders, missing scales and unsupported distortion tables."""
    if any(str(k).startswith(('CPDIS','D2IMDIS')) for k in header):raise ValueError('This WCS requires external distortion tables. Solve online instead.')
    if not all(k in header for k in ('CTYPE1','CTYPE2','CRPIX1','CRPIX2','CRVAL1','CRVAL2')):raise ValueError('No complete celestial WCS in this image.')
    if not (all(k in header for k in ('CDELT1','CDELT2')) or any(str(k).startswith('CD1_') for k in header)):raise ValueError('Sky-coordinate pixel scale is missing.')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore');wcs=WCS(header,naxis=2).celestial
    if not wcs.has_celestial or wcs.pixel_n_dim!=2 or wcs.wcs.lngtyp!='RA' or wcs.wcs.lattyp!='DEC':raise ValueError('A two-dimensional RA/Dec sky solution is required.')
    scales=proj_plane_pixel_scales(wcs)*3600
    if not np.isfinite(scales).all() or np.any(scales<.01) or np.any(scales>3600):raise ValueError('Sky-coordinate pixel scale is not usable.')
    h,w=shape[:2];points=np.array([[w/2,h/2],[0,0],[w-1,h-1]],dtype=float)
    world=wcs.all_pix2world(points,0);back=wcs.all_world2pix(world,0)
    if not np.isfinite(world).all() or not np.isfinite(back).all() or np.max(np.abs(points-back))>1:raise ValueError('Sky coordinates do not round-trip correctly.')
    return wcs


@lru_cache(maxsize=1)
def catalog():
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'/'catalogs'
    with gzip.open(root/'objects.json.gz','rt',encoding='utf-8') as stream:return json.load(stream)


def identify_catalog(header,shape,crop=None,categories=CATEGORIES,magnitude=16,limit=100,include_unknown=True,objects=None,cancelled=lambda:False):
    wcs=celestial_wcs(header,shape);h,w=shape[:2];crop=crop or (0,0,w,h)
    rows=catalog() if objects is None else objects
    chosen=[r for r in rows if r['category'] in categories and ((r['mag'] is None and include_unknown) or (r['mag'] is not None and r['mag']<=magnitude))]
    if not chosen:return []
    if cancelled():raise InterruptedError('Cancelled')
    ra=np.array([r['ra'] for r in chosen]);dec=np.array([r['dec'] for r in chosen])
    # HYG proper motions are in mas/year; pmra already contains cos(dec).
    try:
        year=Time(header.get('DATE-OBS','2000-01-01T12:00:00')).jyear;dt=float(year)-2000
        if not np.isfinite(dt) or abs(dt)>300:dt=0
    except (ValueError,TypeError):dt=0
    for i,r in enumerate(chosen):
        if r['category']=='Stars':
            cosine=max(abs(math.cos(math.radians(dec[i]))),1e-5)
            ra[i]+=r.get('pmra',0)*dt/(3600000*cosine);dec[i]+=r.get('pmdec',0)*dt/3600000
    coordinates=SkyCoord(ra=ra*u.deg,dec=dec*u.deg,frame='icrs')
    # Avoid projecting the whole sphere through a local distorted TAN solution.
    center=wcs.pixel_to_world((w-1)/2,(h-1)/2)
    edge=wcs.pixel_to_world(np.array([0,w-1,w-1,0,(w-1)/2,(w-1)/2,0,w-1]),np.array([0,0,h-1,h-1,0,h-1,(h-1)/2,(h-1)/2]))
    radius=min(180,float(np.max(center.separation(edge).deg))*1.1+.02)
    nearby=np.asarray(coordinates.separation(center).deg<=radius)
    chosen=[r for r,keep in zip(chosen,nearby) if keep];coordinates=coordinates[nearby]
    if not chosen:return []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        try:x,y=skycoord_to_pixel(coordinates,wcs,origin=0,mode='all')
        except NoConvergence as exc:
            pixels=np.asarray(exc.best_solution,dtype=float).copy()
            for indices in (exc.divergent,exc.slow_conv):
                if indices is not None:pixels[indices]=np.nan
            x,y=pixels.T
    x0,y0,x1,y1=crop
    found=[]
    for r,px,py in zip(chosen,x,y):
        if cancelled():raise InterruptedError('Cancelled')
        if np.isfinite(px) and np.isfinite(py) and x0<=px<x1 and y0<=py<y1:
            found.append(dict(r,x=float(px),y=float(py)))
    found.sort(key=lambda r:(r.get('priority',1),r['mag'] if r['mag'] is not None else 99,r['name']))
    return found[:max(1,min(int(limit),500))]


def extract_sources(image,cancelled=lambda:False,minimum=10):
    """Return 1-based star coordinates in full original image pixels."""
    import sep
    h,w=image.shape[:2];scale=min(1.,2048/max(h,w))
    small=image if scale==1 else cv2.resize(image,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_AREA)
    data=np.ascontiguousarray(np.mean(small,axis=-1),dtype=np.float32)
    if min(data.shape)<16:raise ValueError('Image is too small to solve. Use the original uncropped image.')
    if cancelled():raise InterruptedError('Cancelled')
    background=sep.Background(data);data-=background.back()
    noise=max(float(background.globalrms),float(np.std(data))*.02,1e-8)
    sources=sep.extract(data,4.,err=noise,minarea=5,filter_kernel=None)
    keep=(sources['flux']>0)&(sources['b']>.45)&(sources['a']/np.maximum(sources['b'],1e-8)<3)&(sources['x']>3)&(sources['y']>3)&(sources['x']<data.shape[1]-4)&(sources['y']<data.shape[0]-4)
    sources=sources[keep];sources=sources[np.argsort(sources['flux'])[::-1]][:2000]
    if len(sources)<minimum:raise ValueError('Fewer than 10 usable stars were found. Try the original FITS stack or a less cropped/processed image.' if minimum==10 else 'No usable stars were found for Gaia matching. Try a less processed image or a wider crop.')
    return dict(x=((sources['x']+.5)*w/data.shape[1]+.5).tolist(),y=((sources['y']+.5)*h/data.shape[0]+.5).tolist(),image_width=w,image_height=h)


class NovaClient:
    """Fixed HTTPS service; no key/session values are returned in errors/logs."""
    def __init__(self,transport=None):
        self.transport=transport
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), urllib.request.HTTPSHandler(context=https_context()))
    def request(self,path,payload=None,binary=False):
        data=None if payload is None else urllib.parse.urlencode({'request-json':json.dumps(payload,allow_nan=False)}).encode()
        if self.transport is not None:return self.transport(path,payload,binary)
        request=urllib.request.Request(SERVICE+path,data=data,headers={'User-Agent':'EasyAstroStudio/1.3','Content-Type':'application/x-www-form-urlencoded'})
        try:
            with self.opener.open(request,timeout=20) as response:
                body=response.read(2*1024*1024+1)
            if len(body)>2*1024*1024:raise ValueError('Response exceeded the size limit.')
            result=body if binary else json.loads(body)
        except Exception as exc:
            # Do not echo remote response text or urllib error URLs with credentials.
            raise RuntimeError('Astrometry.net request failed. Check your connection, API key and service availability.') from None
        if not binary and (not isinstance(result,dict) or result.get('status')=='error'):
            raise RuntimeError('Astrometry.net did not accept this request. Check your API key and try again.')
        return result
    def solve(self,sources,key,progress=lambda text:None,cancelled=lambda:False,wait=None,timeout=600):
        def check():
            if cancelled():raise InterruptedError('Cancelled; an uploaded request may continue on the service.')
        def pause():
            if wait is not None:wait();check();return
            for _ in range(50):check();time.sleep(.1)
        check();progress('Signing in to Astrometry.net…')
        login=self.request('/api/login',{'apikey':key});session=login.get('session')
        if not isinstance(session,str) or not session:raise RuntimeError('Astrometry.net sign-in failed. Check the API key.')
        check();progress('Sending extracted star positions (no image pixels)…')
        result=self.request('/api/upload',dict(sources,session=session,publicly_visible='n',allow_commercial_use='n',allow_modifications='n',crpix_center=True,tweak_order=2))
        subid=result.get('subid')
        if type(subid) is not int or subid<1:raise RuntimeError('The service did not return a submission number.')
        progress(f'Waiting for solver • submission {subid}…');deadline=time.monotonic()+timeout;jobids=[]
        while time.monotonic()<deadline:
            check()
            # Submission preprocessing and astrometric jobs have separate
            # lifecycles. processing_finished may be the STRING 'None', and
            # even a timestamp does not mean a queued solving job has failed.
            sub=self.request(f'/api/submissions/{subid}')
            if sub.get('error_message'):
                raise RuntimeError(f'Astrometry.net could not process the star-list submission {subid}. Check that submission on the service or try again later.')
            raw_jobs=sub.get('jobs') or []
            if not isinstance(raw_jobs,list):raise RuntimeError('Astrometry.net returned an invalid job list. Try again later.')
            jobids=list(dict.fromkeys(j for j in raw_jobs if type(j) is int and j>0))
            pending_jobs=not raw_jobs or any(type(j) is not int or j<=0 for j in raw_jobs)
            if not jobids:progress(f'Queued for solving • submission {subid} • waiting for a solver job…')
            states=[]
            for job in jobids:
                check();status=self.request(f'/api/jobs/{job}').get('status');states.append(status)
                progress(f'Plate solving • submission {subid}, job {job}: {status or "queued"}')
                if status=='success':
                    check();raw=self.request(f'/wcs_file/{job}',binary=True)
                    try:
                        with fits.open(io.BytesIO(raw),memmap=False) as hdus:header=hdus[0].header.copy()
                        celestial_wcs(header,(sources['image_height'],sources['image_width'],3))
                    except Exception:raise RuntimeError('The service returned an invalid sky solution.') from None
                    return header,job
            if states and not pending_jobs and all(s=='failure' for s in states):raise RuntimeError(f'Astrometry.net reported a failed solve for submission {subid}, job(s) '+', '.join(map(str,jobids))+'. Try the original stack or a different reference image.')
            pause()
        raise TimeoutError(f'Submission {subid} is still pending after ten minutes. You can check it on Astrometry.net and try again later.')


class IdentificationWorker(QtCore.QThread):
    warning=QtCore.Signal(str)
    progress=QtCore.Signal(str);done=QtCore.Signal(object,object);failed=QtCore.Signal(str)
    def __init__(self,image,header,crop,options,key=None,client=None):
        super().__init__();self.image=image;self.header=header.copy();self.crop=crop;self.options=options;self.key=key;self.client=client or NovaClient()
    def run(self):
        try:
            header=self.header;sources=None
            options=dict(self.options);use_gaia=options.pop('gaia',False);tolerance=options.pop('gaia_tolerance',5.)
            if self.key is not None:
                self.progress.emit('Finding stars locally…');sources=extract_sources(self.image,self.isInterruptionRequested)
                header,job=self.client.solve(sources,self.key,self.progress.emit,self.isInterruptionRequested)
                if self.header.get('DATE-OBS'):header['DATE-OBS']=self.header['DATE-OBS']
            self.progress.emit('Matching bundled catalog positions…')
            rows=identify_catalog(header,self.image.shape,crop=self.crop,cancelled=self.isInterruptionRequested,**options)
            if use_gaia:
                from gaia_matching import gaia_matches
                if 'Stars' not in options.get('categories',CATEGORIES):raise ValueError('Select the Stars category for Gaia matching.')
                try:candidates=gaia_matches(self.image,header,self.crop,options.get('magnitude',16),options.get('limit',100),tolerance,self.progress.emit,self.isInterruptionRequested,sources=sources)
                except InterruptedError:raise
                except Exception as exc:
                    self.warning.emit('Gaia matching did not complete: '+str(exc)+' Bundled catalog results and any completed sky solution are still available.');candidates=[]
                # Prefer named bundled stars over a Gaia candidate at the same position.
                pixels_per_arcsec=1/max(float(np.mean(proj_plane_pixel_scales(celestial_wcs(header,self.image.shape))))*3600,1e-9)
                candidates=[r for r in candidates if not any(a['category']=='Stars' and np.hypot(a['x']-r['x'],a['y']-r['y'])<tolerance*pixels_per_arcsec for a in rows)]
                maximum=options.get('limit',100);candidates=candidates[:max(1,maximum//2)]
                rows=rows[:maximum-len(candidates)]+candidates
            if self.isInterruptionRequested():raise InterruptedError('Cancelled')
            self.done.emit(rows,header)
        except Exception as exc:self.failed.emit(str(exc))
        finally:self.key=None
