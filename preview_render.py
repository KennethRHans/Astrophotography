"""Bounded preview cache and rendering independent of Qt widgets."""
from collections import OrderedDict
import threading
import cv2
import numpy as np
from PySide6 import QtCore
import engine
from histogram import histogram_data


class PreviewRenderer:
    def __init__(self):
        self.lock=threading.RLock();self.clear()
    def clear(self):
        self.cache=OrderedDict();self.source=None;self.size=None;self.small=None;self.normalization_key=None;self.normalization=None
    def render(self,source,size,settings,model,gpu,mark):
        with self.lock:
            if self.source is not source:self.clear();self.source=source
            entry=self.cache.pop(size,None)
            if entry is None:
                small=source if size==(source.shape[1],source.shape[0]) else cv2.resize(source,size,interpolation=cv2.INTER_AREA)
                entry=dict(small=small,key=None,normalization=None)
            self.cache[size]=entry
            while len(self.cache)>2:self.cache.popitem(last=False)
            self.size=size;self.small=entry['small']
            key=(settings[1],settings[4],tuple(settings[5]),id(model))
            if key!=entry['key']:
                entry['normalization']=engine.normalize_image(self.small,settings[1],settings[4],settings[5],model);entry['key']=key
            self.normalization=entry['normalization'];self.normalization_key=key
            image=engine.render(self.small,*settings,model=model,gpu=gpu,normalization=self.normalization)
            valid=self.normalization[1]
            bins,black,white=histogram_data(image,valid)
            pixels=np.ascontiguousarray(np.round(image*255).astype(np.uint8))
            if mark:
                pixels[np.any(image<=0,axis=-1)&valid]=(45,105,255)
                pixels[np.any(image>=1,axis=-1)&valid]=(255,65,65)
            return dict(pixels=pixels,bins=bins,black=black,white=white,source_size=(source.shape[1],source.shape[0]),settings=settings)


class PreviewWorker(QtCore.QThread):
    result=QtCore.Signal(int,object)
    failed=QtCore.Signal(int,str)
    def __init__(self,renderer,generation,request):
        super().__init__();self.renderer=renderer;self.generation=generation;self.request=request
    def run(self):
        try:self.result.emit(self.generation,self.renderer.render(*self.request))
        except Exception as exc:self.failed.emit(self.generation,str(exc))
