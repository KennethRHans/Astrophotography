"""Portable, atomic project storage. JSON + FITS header + non-pickled NumPy data."""
import copy
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile,ZIP_DEFLATED
import numpy as np
from astropy.io import fits

MAX_IMAGE_BYTES=2*1024**3
MAX_MANIFEST_BYTES=2*1024**2


class EditHistory:
    def __init__(self,limit=100):self.limit=limit;self.states=[];self.index=-1
    def reset(self,state):self.states=[copy.deepcopy(state)];self.index=0
    def push(self,state):
        if self.index>=0 and state==self.states[self.index]:return False
        self.states=self.states[:self.index+1]+[copy.deepcopy(state)]
        if len(self.states)>self.limit:self.states=self.states[-self.limit:]
        self.index=len(self.states)-1
        return True
    @property
    def can_undo(self):return self.index>0
    @property
    def can_redo(self):return self.index+1<len(self.states)
    def undo(self):
        if self.can_undo:self.index-=1
        return copy.deepcopy(self.states[self.index])
    def redo(self):
        if self.can_redo:self.index+=1
        return copy.deepcopy(self.states[self.index])


def validate_state(state,shape,slider_ranges=None):
    if not isinstance(state,dict):raise ValueError('Invalid editing state')
    h,w,_=shape
    crop=state.get('applied_crop')
    if not isinstance(crop,list) or len(crop)!=4 or any(type(x) is not int for x in crop):raise ValueError('Invalid applied crop')
    x0,y0,x1,y1=crop
    if not (0<=x0<x1<=w and 0<=y0<y1<=h):raise ValueError('Applied crop exceeds saved image')
    selection=state.get('selection')
    if not isinstance(selection,list) or len(selection)!=4 or any(type(x) is not int for x in selection):raise ValueError('Invalid crop selection')
    a,b,c,d=selection
    if not (0<=a<c<=x1-x0 and 0<=b<d<=y1-y0):raise ValueError('Crop selection exceeds image')
    sliders=state.get('sliders')
    if not isinstance(sliders,dict) or len(sliders)>40 or any(not isinstance(k,str) or type(v) is not int for k,v in sliders.items()):raise ValueError('Invalid slider settings')
    if slider_ranges is not None:
        if set(sliders)!=set(slider_ranges):raise ValueError('Project adjustments are incompatible with this app version')
        for key,value in sliders.items():
            low,high=slider_ranges[key]
            if not low<=value<=high:raise ValueError(f'Project value outside range: {key}')
    if type(state.get('compare')) is not bool:raise ValueError('Invalid comparison setting')
    for key in ('ratio','guides'):
        if not isinstance(state.get(key),str) or len(state[key])>100:raise ValueError('Invalid view setting')
    from annotations import validate_annotations
    validate_annotations(state.get('annotations',[]),shape)
    if type(state.get('labels_visible',True)) is not bool:raise ValueError('Invalid label visibility')
    return state


def save_project(path,linear,header,manifest):
    path=Path(path)
    if path.suffix.lower()!='.astro':raise ValueError('Project filenames must end with .astro')
    if linear.ndim!=3 or linear.shape[-1]!=3 or linear.nbytes>MAX_IMAGE_BYTES:raise ValueError('Unsupported project image size')
    meta=copy.deepcopy(manifest);meta['format']='astro-studio-project';meta['version']=1
    validate_state(meta['state'],linear.shape)
    encoded=json.dumps(meta,ensure_ascii=False,allow_nan=False).encode('utf-8')
    if len(encoded)>MAX_MANIFEST_BYTES:raise ValueError('Project metadata is too large')
    fd,temp=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.tmp',dir=path.parent);os.close(fd)
    try:
        with ZipFile(temp,'w',ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
            archive.writestr('project.json',encoded)
            archive.writestr('header.txt',header.tostring(sep='\n',endcard=True,padding=False))
            with archive.open('linear.npy','w',force_zip64=True) as stream:
                np.save(stream,np.asarray(linear,dtype=np.float32),allow_pickle=False)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def load_project(path):
    with ZipFile(path) as archive:
        names=archive.namelist()
        if len(names)!=3 or set(names)!={'project.json','header.txt','linear.npy'}:raise ValueError('Unrecognized project contents')
        if archive.getinfo('project.json').file_size>MAX_MANIFEST_BYTES or archive.getinfo('header.txt').file_size>1024**2:raise ValueError('Project metadata is too large')
        meta=json.loads(archive.read('project.json').decode('utf-8'))
        if not isinstance(meta,dict) or meta.get('format')!='astro-studio-project' or meta.get('version')!=1:raise ValueError('Unsupported project format/version')
        entry=archive.getinfo('linear.npy')
        if entry.file_size>MAX_IMAGE_BYTES+4096:raise ValueError('Project image is too large')
        with archive.open(entry) as stream:
            version=np.lib.format.read_magic(stream)
            if version==(1,0):shape,fortran,dtype=np.lib.format.read_array_header_1_0(stream,max_header_size=4096)
            elif version==(2,0):shape,fortran,dtype=np.lib.format.read_array_header_2_0(stream,max_header_size=4096)
            else:raise ValueError('Unsupported array format')
            if len(shape)!=3 or shape[-1]!=3 or any(type(n) is not int or n<1 for n in shape) or dtype!=np.dtype('float32'):raise ValueError('Invalid project RGB array')
            size=int(shape[0])*int(shape[1])*3*4
            if size>MAX_IMAGE_BYTES or stream.tell()+size!=entry.file_size:raise ValueError('Invalid project image length')
        validate_state(meta.get('state'),shape)
        for key in ('input_files','source_files'):
            files=meta.get(key,[])
            if not isinstance(files,list) or len(files)>10000 or any(not isinstance(p,str) or len(p)>4096 for p in files):raise ValueError('Invalid input file list')
        if not isinstance(meta.get('source_name','image'),str) or len(meta.get('source_name','image'))>4096:raise ValueError('Invalid source name')
        if meta.get('bayer','Auto') not in ('Auto','None','RGGB','BGGR','GRBG','GBRG'):raise ValueError('Invalid Bayer setting')
        view=meta.get('view',{})
        if not isinstance(view,dict):raise ValueError('Invalid saved view')
        for key in ('fit','gpu','mark_clipping'):
            if key in view and type(view[key]) is not bool:raise ValueError('Invalid saved view flag')
        zoom=view.get('zoom',1)
        if type(zoom) not in (float,int) or not np.isfinite(zoom) or not 0<zoom<1e6:raise ValueError('Invalid saved zoom')
        center=view.get('center',[0,0])
        if not isinstance(center,list) or len(center)!=2 or any(type(v) not in (float,int) or not np.isfinite(v) or abs(v)>1e9 for v in center):raise ValueError('Invalid saved view center')
        history=meta.get('history',{})
        if not isinstance(history,dict):raise ValueError('Invalid project history')
        if history:
            states=history.get('states');index=history.get('index')
            if not isinstance(states,list) or not 1<=len(states)<=100 or type(index) is not int or not 0<=index<len(states):raise ValueError('Invalid project history')
            for state in states:validate_state(state,shape)
            if states[index]!=meta['state']:raise ValueError('Project history does not match current edits')
        with archive.open(entry) as stream:linear=np.load(stream,allow_pickle=False,max_header_size=4096)
        if not np.isfinite(linear).all():raise ValueError('Project image contains nonfinite pixels')
        header=fits.Header.fromstring(archive.read('header.txt').decode('ascii'),sep='\n')
    return linear,header,meta
