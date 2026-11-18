"""Validated display-only opening transfer; never changes linear source data."""
import math
import numpy as np


def validate_opening_stretch(value):
    if value is None:return None
    if not isinstance(value,(tuple,list)) or len(value)!=3:
        raise ValueError('Invalid adaptive opening stretch')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('Invalid adaptive opening stretch values')
    black,white,midtones=map(float,value)
    if black<0 or white<=black or not 0<midtones<1:
        raise ValueError('Invalid adaptive opening stretch range')
    return black,white,midtones


def opening_statistics(image):
    from review_stretch import review_statistics
    values=review_statistics(image,target=.20)
    if values is None:return None
    black,white,midtones=values
    return validate_opening_stretch([float(black),float(white),float(np.clip(midtones,1e-7,1-1e-7))])


def linked_midtones(image,midtones):
    light=image@np.array([.2126,.7152,.0722],dtype=np.float32)
    mapped=((midtones-1)*light)/((2*midtones-1)*light-midtones)
    ratio=np.divide(mapped,light,out=np.zeros_like(light),where=light>0)
    result=image*ratio[...,None]
    result/=np.maximum(np.max(result,axis=-1,keepdims=True),1)
    return np.clip(result,0,1)
