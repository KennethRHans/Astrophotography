"""Opt-in Gaia DR3 cone search and local one-to-one star candidate matching."""
import csv
import io
import urllib.parse
import urllib.request
import warnings
import numpy as np
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy import units as u
from astropy.wcs.utils import skycoord_to_pixel

GAIA_URL='https://gea.esac.esa.int/tap-server/tap/sync'
MAX_SOURCES=5000


def query_region(wcs,crop):
    x0,y0,x1,y1=crop
    center=wcs.pixel_to_world((x0+x1-1)/2,(y0+y1-1)/2).icrs
    corners=wcs.pixel_to_world(np.array([x0,x1-1,x1-1,x0]),np.array([y0,y0,y1-1,y1-1])).icrs
    radius=float(np.max(center.separation(corners).deg))*1.1+.03
    if not np.isfinite(radius) or not 0<radius<=5:raise ValueError('Gaia matching supports a sky radius up to 5 degrees. Apply a smaller crop first.')
    return float(center.ra.deg),float(center.dec.deg),radius


class GaiaClient:
    def query(self,ra,dec,radius,magnitude,transport=None):
        values=np.asarray([ra,dec,radius,magnitude],dtype=float)
        if not np.isfinite(values).all() or not (0<=ra<360 and -90<=dec<=90 and 0<radius<=5 and -5<=magnitude<=22):raise ValueError('Invalid Gaia sky-region query')
        query=(f'SELECT TOP {MAX_SOURCES} source_id,ra,dec,ref_epoch,pmra,pmdec,phot_g_mean_mag '
               f'FROM gaiadr3.gaia_source WHERE CONTAINS(POINT(\'ICRS\',ra,dec),'
               f'CIRCLE(\'ICRS\',{ra:.10f},{dec:.10f},{radius:.10f}))=1 '
               f'AND phot_g_mean_mag <= {magnitude:.3f} ORDER BY phot_g_mean_mag ASC')
        payload=dict(REQUEST='doQuery',LANG='ADQL',FORMAT='csv',QUERY=query)
        if transport is not None:body=transport(payload)
        else:
            request=urllib.request.Request(GAIA_URL,data=urllib.parse.urlencode(payload).encode(),headers={'User-Agent':'EasyAstroStudio/1.4','Accept':'text/csv','Content-Type':'application/x-www-form-urlencoded'})
            try:
                with urllib.request.urlopen(request,timeout=30) as reply:body=reply.read(4*1024*1024+1)
            except Exception:raise RuntimeError('Gaia Archive query failed. Check your connection or try again later. No image or API key was sent to Gaia.') from None
        if not isinstance(body,bytes) or len(body)>4*1024*1024:raise ValueError('Gaia response exceeded the size limit.')
        try:
            reader=csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
            required={'source_id','ra','dec','ref_epoch','pmra','pmdec','phot_g_mean_mag'}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):raise ValueError()
            rows=[]
            for r in reader:
                if len(rows)>=MAX_SOURCES:break
                ident=r['source_id'].strip()
                if not ident.isascii() or not ident.isdigit() or len(ident)>20:continue
                item=dict(id='Gaia DR3:'+ident,name='Gaia DR3 '+ident,category='Stars',ra=float(r['ra']),dec=float(r['dec']),epoch=float(r['ref_epoch']),pmra=0. if r['pmra'].strip().lower() in ('','nan','null','none') else float(r['pmra']),pmdec=0. if r['pmdec'].strip().lower() in ('','nan','null','none') else float(r['pmdec']),mag=float(r['phot_g_mean_mag']),priority=2)
                if not np.isfinite([item[k] for k in ('ra','dec','epoch','pmra','pmdec','mag')]).all():continue
                if not (0<=item['ra']<360 and -90<=item['dec']<=90 and 1800<=item['epoch']<=2200 and item['mag']<=magnitude):continue
                rows.append(item)
            return rows
        except (ValueError,TypeError,KeyError,UnicodeError):raise ValueError('Gaia Archive returned an unreadable catalog response. Try again later.') from None


def match_candidates(wcs,header,crop,gaia,sources,tolerance=5.,limit=100):
    if not 0<tolerance<=15:raise ValueError('Gaia matching tolerance must be between 0 and 15 arcseconds.')
    if not gaia or not sources['x']:return []
    stars=SkyCoord(ra=np.array([r['ra'] for r in gaia])*u.deg,dec=np.array([r['dec'] for r in gaia])*u.deg,
                   pm_ra_cosdec=np.array([r['pmra'] for r in gaia])*u.mas/u.yr,pm_dec=np.array([r['pmdec'] for r in gaia])*u.mas/u.yr,
                   obstime=Time([r['epoch'] for r in gaia],format='jyear'),frame='icrs')
    if header.get('DATE-OBS'):
        try:
            date=Time(header['DATE-OBS'])
            if 1800<float(date.jyear)<2200:
                with warnings.catch_warnings():warnings.simplefilter('ignore');stars=stars.apply_space_motion(new_obstime=date)
        except (ValueError,TypeError):pass
    # Extraction uses FITS one-based coordinates; WCS projection uses origin 0.
    sx=np.asarray(sources['x'])-1;sy=np.asarray(sources['y'])-1
    x0,y0,x1,y1=crop;keep=(sx>=x0)&(sx<x1)&(sy>=y0)&(sy<y1)
    sx,sy=sx[keep],sy[keep]
    if not sx.size:return []
    detected=wcs.pixel_to_world(sx,sy).icrs
    index,separation,_=detected.match_to_catalog_sky(stars)
    used=set();matches=[]
    for i in np.argsort(separation.arcsec):
        j=int(index[i]);distance=float(separation[i].arcsec)
        if distance>tolerance or j in used:continue
        used.add(j);r=dict(gaia[j]);r.update(x=float(sx[i]),y=float(sy[i]),match_arcsec=distance)
        matches.append(r)
    matches.sort(key=lambda r:(r['mag'],r['match_arcsec']))
    return matches[:max(1,min(int(limit),300))]


def gaia_matches(image,header,crop,magnitude,limit,tolerance=5.,progress=lambda text:None,cancelled=lambda:False,client=None,sources=None):
    from object_identification import celestial_wcs,extract_sources
    def check():
        if cancelled():raise InterruptedError('Cancelled Gaia matching')
    wcs=celestial_wcs(header,image.shape);region=query_region(wcs,crop);check()
    progress('Querying Gaia DR3 for the current sky region…')
    rows=(client or GaiaClient()).query(*region,magnitude);check()
    if not rows:return []
    progress('Matching Gaia positions to stars detected locally…')
    if sources is None:sources=extract_sources(image,cancelled,minimum=1)
    result=match_candidates(wcs,header,crop,rows,sources,tolerance,limit);check();return result
