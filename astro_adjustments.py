"""Display-only monotone tone tools and conservative edge/star-protected denoising."""
from functools import lru_cache
import cv2
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.interpolate import PchipInterpolator

NEUTRAL_CURVE=(0,250,500,750,1000)
LUMA=np.array([.2126,.7152,.0722],dtype=np.float32)


def validate_curve(values):
    if not isinstance(values,(tuple,list)) or len(values)!=5 or any(type(v) is not int or not 0<=v<=1000 for v in values):raise ValueError('Invalid tone curve')
    if values[0]!=0 or values[-1]!=1000 or any(a>b for a,b in zip(values,values[1:])):raise ValueError('Tone curve must be monotone with fixed black/white endpoints')
    return tuple(values)


@lru_cache(maxsize=16)
def curve_lut(values):
    values=validate_curve(values);x=np.linspace(0,1,4096,dtype=np.float32)
    return x,np.clip(PchipInterpolator(np.linspace(0,1,5),np.array(values)/1000)(x),0,1).astype(np.float32)


def tone_adjust(image,midtones=0,curve=NEUTRAL_CURVE):
    values=validate_curve(curve)
    if midtones==0 and values==NEUTRAL_CURVE:return image
    if not -1<=midtones<=1:raise ValueError('Midtones must be between -1 and 1')
    light=image@LUMA;m=.5-.45*midtones
    mapped=light if midtones==0 else ((m-1)*light)/((2*m-1)*light-m)
    if values!=NEUTRAL_CURVE:
        x,y=curve_lut(values);mapped=np.interp(mapped,x,y).astype(np.float32)
    ratio=np.divide(mapped,light,out=np.zeros_like(light),where=light>1e-8)
    result=image*ratio[...,None]
    result/=np.maximum(np.max(result,axis=-1,keepdims=True),1)
    return np.clip(result,0,1)


def star_preserving_denoise(image,amount=0,protection=1,valid=None):
    """Bilateral noise reduction blended with a soft bright-structure mask.

    Preserves detected cores/wings at full protection, but cannot guarantee
    preservation of every faint source. Does not synthesize detail or fix hot pixels.
    """
    if amount==0:return image
    if not 0<=amount<=1 or not 0<=protection<=1:raise ValueError('Noise reduction/protection must be between 0 and 1')
    h,w=image.shape[:2]
    if min(h,w)<3:return image.copy()
    step=max(1,max(h,w)//512)
    delta=image[::step,1:w:step]-image[::step,0:w-1:step]
    centers=np.median(delta,axis=(0,1));noise=float(np.median(np.abs(delta-centers))/.67448975/np.sqrt(2))
    if not np.isfinite(noise) or noise<1e-7:return image.copy()
    noise=min(noise,.1)
    filtered=cv2.bilateralFilter(np.ascontiguousarray(image,dtype=np.float32),7,float(noise*(1+3*amount)),1.2+amount)
    light=image@LUMA;detail=light-gaussian_filter(light,2.)
    cores=(detail>max(4.5*noise*.75,.004)).astype(np.uint8)
    mask=cv2.dilate(cores,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5))).astype(np.float32)
    mask=np.maximum(mask,gaussian_filter(mask,1.)) * protection
    if valid is not None:
        borders=cv2.dilate((~valid).astype(np.uint8),np.ones((7,7),np.uint8)).astype(bool)
        mask[borders]=1
    return np.clip(image+(filtered-image)*(amount*(1-mask))[...,None],0,1)
