"""Bounded preview cache and rendering independent of Qt widgets."""
from collections import OrderedDict
import threading
import cv2
import numpy as np
from PySide6 import QtCore
import engine
from histogram import histogram_data
from astro_adjustments import star_preserving_denoise


# Histogram/normalization sampling must not change at pointer release or zoom.
REFERENCE_MAX_SIDE = 512


class PreviewRenderer:
    def __init__(self):
        self.lock=threading.RLock();self.clear()
    def clear(self):
        self.cache=OrderedDict();self.source=None;self.reference=None
        self.size=None;self.small=None;self.normalization_key=None;self.normalization=None

    @staticmethod
    def entry(small):
        return dict(small=small,key=None,normalization=None,noise_key=None,prepared=None,color_key=None,color_offsets=None,
                    histogram_key=None,histogram=None)

    @staticmethod
    def prepare(entry,key,settings,model,statistics,color_offsets=None):
        if key!=entry['key']:
            entry['normalization']=engine.normalize_image(entry['small'],settings[1],settings[4],settings[5],model,statistics)
            entry['key']=key
        noise=settings[10] if len(settings)>10 else 0
        protection=settings[11] if len(settings)>11 else 1
        neutralization=settings[14] if len(settings)>14 else 0
        if neutralization and color_offsets is None:
            if entry['color_key']!=key:
                entry['color_offsets']=engine.background_color_offsets(entry['normalization'][0],entry['normalization'][1])
                entry['color_key']=key
            color_offsets=entry['color_offsets']
        noise_key=(key,noise,protection,neutralization)
        if entry['noise_key']!=noise_key:
            adjusted=engine.neutralize_background(entry['normalization'][0],neutralization,entry['normalization'][1],color_offsets)
            entry['prepared']=star_preserving_denoise(adjusted,noise,protection,entry['normalization'][1])
            entry['noise_key']=noise_key

    @staticmethod
    def draw(entry,settings,model,gpu):
        return engine.render(entry['small'],*settings,model=model,gpu=gpu,
                             normalization=entry['normalization'],prepared=entry['prepared'])

    def render(self,source,size,settings,model,gpu,mark):
        with self.lock:
            if self.source is not source:
                self.clear();self.source=source
                step=max(1,int(np.ceil(max(source.shape[:2])/REFERENCE_MAX_SIDE)))
                # Preserve source pixel intensities rather than averaging them:
                # draft downsampling otherwise changes noise/percentile levels.
                sample=source if step==1 else source[::step,::step]
                self.reference=self.entry(sample)
            reference=self.reference
            key=(settings[1],settings[4],tuple(settings[5]),id(model))
            if key!=reference['key']:
                reference['statistics']=engine.normalization_statistics(reference['small'],settings[1],settings[4],settings[5],model)
            statistics=reference['statistics']
            self.prepare(reference,key,settings,model,statistics)
            histogram_key=(key,settings,id(gpu),bool(gpu is not None and gpu.disabled))
            reference_image=None
            if histogram_key!=reference['histogram_key']:
                reference_image=self.draw(reference,settings,model,gpu)
                reference['histogram']=histogram_data(reference_image,reference['normalization'][1])
                reference['histogram_key']=histogram_key

            entry=self.cache.pop(size,None)
            if entry is None:
                if reference['small'] is source and size==(source.shape[1],source.shape[0]):
                    entry=reference
                else:
                    small=source if size==(source.shape[1],source.shape[0]) else cv2.resize(source,size,interpolation=cv2.INTER_AREA)
                    entry=self.entry(small)
            self.cache[size]=entry
            while len(self.cache)>2:self.cache.popitem(last=False)
            self.prepare(entry,key,settings,model,statistics,reference['color_offsets'])
            self.size=size;self.small=entry['small']
            self.normalization=entry['normalization'];self.normalization_key=key
            image=reference_image if entry is reference and reference_image is not None else self.draw(entry,settings,model,gpu)
            bins,black,white=reference['histogram']
            pixels=np.ascontiguousarray(np.round(image*255).astype(np.uint8))
            if mark:
                valid=self.normalization[1]
                pixels[np.any(image<=0,axis=-1)&valid]=(45,105,255)
                pixels[np.any(image>=1,axis=-1)&valid]=(255,65,65)
            return dict(pixels=pixels,bins=bins,black=black,white=white,
                        source_size=(source.shape[1],source.shape[0]),settings=settings)


class PreviewWorker(QtCore.QThread):
    result=QtCore.Signal(int,object)
    failed=QtCore.Signal(int,str)
    def __init__(self,renderer,generation,request):
        super().__init__();self.renderer=renderer;self.generation=generation;self.request=request
    def run(self):
        try:self.result.emit(self.generation,self.renderer.render(*self.request))
        except Exception as exc:self.failed.emit(self.generation,str(exc))
