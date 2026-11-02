"""Advisory star metrics for comparing like-for-like raw exposures."""
import re
import cv2
import numpy as np
import sep
import engine


def measure(data, header):
    if engine.frame_count(header)>1:
        raise ValueError('Already stacked; use Open existing FITS stack.')
    h,w,_=data.shape
    scale=max(1.,max(h,w)/1600.)
    small=cv2.resize(data,(max(1,round(w/scale)),max(1,round(h/scale))),interpolation=cv2.INTER_AREA) if scale>1 else data
    gray=np.ascontiguousarray(small.mean(axis=-1),dtype=np.float32)
    sky=sep.Background(gray)
    signal=gray-sky.back()
    noise=max(float(sky.globalrms),float(np.finfo(np.float32).eps))
    objects=sep.extract(signal,5.,err=noise,minarea=6)
    if len(objects):
        a=objects['a'];b=objects['b']
        widths=2.35482*np.sqrt((a*a+b*b)/2)*scale
        ratio=a/np.maximum(b,1e-12)
        good=(objects['flag']==0)&(b>0)&(widths>=1)&(widths<=25)&(ratio<10)&(objects['npix']>=6)
        good&=(objects['x']>8)&(objects['y']>8)&(objects['x']<gray.shape[1]-9)&(objects['y']<gray.shape[0]-9)
        # Broad nebulosity and most isolated hot pixels are excluded by shape
        # and area. Remaining detections still require visual review.
        widths=widths[good];ratio=ratio[good]
    else:widths=ratio=np.array([])
    count=len(widths)
    exposure=float(header.get('EXPTIME',header.get('EXPOSURE',0)))
    group=(h,w,re.sub(r'\s+','',str(header.get('OBJECT','')).casefold()),round(exposure,3),str(header.get('FILTER','')).strip().casefold())
    return dict(stars=count,fwhm=float(np.median(widths)) if count else None,
                elongation=float(np.median(ratio)) if count else None,
                background=float(sky.globalback),noise=noise,group=group,
                status='Ready' if count>=6 else 'Too few reliable stars; inspect manually',score=None)


def rate_batch(records):
    """Relative score only within matching target/dimensions/exposure/filter."""
    result={p:dict(r,score=None) for p,r in records.items()}
    groups={}
    for path,row in result.items():
        if row.get('stars',0)>=6 and row.get('fwhm') and row.get('elongation'):
            groups.setdefault(row['group'],[]).append(path)
    for paths in groups.values():
        if len(paths)<2:
            result[paths[0]]['status']='Needs another comparable frame for a relative score';continue
        best_width=min(result[p]['fwhm'] for p in paths)
        most_stars=max(result[p]['stars'] for p in paths)
        for p in paths:
            row=result[p]
            sharp=min(1.,best_width/row['fwhm'])**2
            roundness=min(1.,1/row['elongation'])**2
            coverage=np.sqrt(row['stars']/most_stars)
            row['score']=round(float(100*(.55*sharp+.25*roundness+.20*coverage)),1)
            row['status']='Relative score; review preview'
    return result
