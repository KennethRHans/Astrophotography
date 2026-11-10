"""Display-only single-exposure stretch for inspecting stars against darker sky."""
import cv2
import numpy as np

LUMA=np.array([.2126,.7152,.0722],dtype=np.float32)


def review_statistics(image,target=.16):
    if image.ndim!=3 or image.shape[2]!=3 or not image.size:
        raise ValueError('Exposure preview requires a nonempty RGB image')
    if not 0<target<1:raise ValueError('Preview background target must be between 0 and 1')
    step=max(1,int(np.ceil(max(image.shape[:2])/512)))
    sample=image[::step,::step]
    valid=np.isfinite(sample).all(axis=-1)&(sample>0).all(axis=-1)
    if not np.any(valid):return None
    light=sample[valid]@LUMA
    sky=float(np.median(light))
    noise=1.4826*float(np.median(np.abs(light-sky)))
    noise=max(noise,abs(sky)*1e-6,1e-12)
    black=max(0.,sky-3*noise)
    # Preserve the actual bright end, rather than treating the top of the
    # background-noise distribution as white in a sparse single exposure.
    peak=float(np.max(image))
    if not np.isfinite(peak):raise ValueError('Exposure contains nonfinite pixels')
    white=max(peak,sky+12*noise,black+1e-12)
    background=np.clip((sky-black)/(white-black),1e-12,1-1e-7)
    midtone=float(background*(1-target)/(background+target-2*background*target))
    return black,white,midtone


def apply_review_stretch(image,statistics):
    if statistics is None:return np.zeros_like(image,dtype=np.float32)
    black,white,m=statistics
    valid=np.isfinite(image).all(axis=-1)&(image>0).all(axis=-1)
    normalized=np.clip((image-black)/(white-black),0,1)
    light=normalized@LUMA
    mapped=((m-1)*light)/((2*m-1)*light-m)
    ratio=np.divide(mapped,light,out=np.zeros_like(light),where=light>0)
    result=normalized*ratio[...,None]
    # Common RGB scaling keeps hue ratios, including on bright colored stars.
    result/=np.maximum(np.max(result,axis=-1,keepdims=True),1)
    result=np.clip(result,0,1)
    result[~valid]=0
    return result


def render_review(image,size=None):
    statistics=review_statistics(image)
    small=image if size is None or size==(image.shape[1],image.shape[0]) else cv2.resize(image,size,interpolation=cv2.INTER_AREA)
    return apply_review_stretch(small,statistics)
