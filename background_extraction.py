"""User-selected sky samples and low-order, display-only background fits."""
import numpy as np


def validate_extraction(config):
    if config is None:return
    if not isinstance(config,dict) or config.get('order') not in (1,2):raise ValueError('Invalid sky fit order')
    points=config.get('points')
    if not isinstance(points,list) or not 6<=len(points)<=144:raise ValueError('Choose 6–144 clear sky samples')
    for point in points:
        if not isinstance(point,(list,tuple)) or len(point)!=2 or any(type(v) not in (int,float) or not np.isfinite(v) or not 0<=v<=1 for v in point):raise ValueError('Invalid sky sample')


def sky_grid():
    return [[float(x),float(y)] for y in np.linspace(.07,.93,8) for x in np.linspace(.07,.93,8) if ((x-.5)/.32)**2+((y-.5)/.32)**2>1]


def fit_sky(image,config):
    validate_extraction(config);h,w,_=image.shape;radius=max(2,min(128,round(min(h,w)*.025)))
    positions=[];samples=[]
    for px,py in config['points']:
        x=round(px*(w-1));y=round(py*(h-1));tile=image[max(0,y-radius):min(h,y+radius+1),max(0,x-radius):min(w,x+radius+1)]
        pixels=tile[np.isfinite(tile).all(axis=-1)&(tile>0).all(axis=-1)]
        if len(pixels)<tile.shape[0]*tile.shape[1]*.8:continue
        light=pixels.mean(axis=-1);mid=np.median(light);mad=max(1.4826*np.median(abs(light-mid)),abs(mid)*1e-6,1e-6)
        pixels=pixels[abs(light-mid)<=3*mad]
        if len(pixels)<4:continue
        positions.append([1,2*px-1,2*py-1,(2*px-1)**2,(2*px-1)*(2*py-1),(2*py-1)**2]);samples.append(np.median(pixels,axis=0))
    n=3 if config['order']==1 else 6
    if len(samples)<max(6,n+3):raise ValueError('Too few usable sky samples for this fit')
    matrix=np.asarray(positions)[:,:n];samples=np.asarray(samples)
    if np.ptp(matrix[:,1])<.8 or np.ptp(matrix[:,2])<.8 or np.linalg.matrix_rank(matrix)<n or np.linalg.cond(matrix)>1e4:raise ValueError('Spread sky samples across the image in both directions')
    # Samples are explicitly chosen by the user: do not silently discard an
    # extended object they have accidentally marked as sky.
    fit=np.linalg.lstsq(matrix,samples,rcond=None)[0];coefficients=np.zeros((6,3));coefficients[:n]=fit
    return coefficients,float(np.sqrt(np.mean((samples-matrix@fit)**2)))


def cropped_coefficients(coefficients,rect,shape):
    """Transform original normalized coordinates into the current cropped frame."""
    h,w,_=shape;x0,y0,x1,y1=rect
    ax=(x1-x0-1)/max(w-1,1);bx=(x0+x1-1)/max(w-1,1)-1
    ay=(y1-y0-1)/max(h-1,1);by=(y0+y1-1)/max(h-1,1)-1
    c=coefficients;out=np.zeros_like(c)
    out[0]=c[0]+bx*c[1]+by*c[2]+bx*bx*c[3]+bx*by*c[4]+by*by*c[5]
    out[1]=ax*c[1]+2*ax*bx*c[3]+ax*by*c[4];out[2]=ay*c[2]+bx*ay*c[4]+2*ay*by*c[5]
    out[3]=ax*ax*c[3];out[4]=ax*ay*c[4];out[5]=ay*ay*c[5]
    return out
