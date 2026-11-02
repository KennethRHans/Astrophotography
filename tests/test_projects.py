import copy,json
from zipfile import ZipFile,ZIP_DEFLATED
import numpy as np
import pytest
from astropy.io import fits
import project_store as projects
from histogram import histogram_data


def state(shape=(30,40,3)):
    return dict(sliders={'Stretch':30},compare=False,applied_crop=[0,0,shape[1],shape[0]],selection=[0,0,shape[1],shape[0]],ratio='Free',guides='Off')


def test_portable_project_roundtrip_with_history(tmp_path):
    data=np.moveaxis(np.random.default_rng(2).normal(5000,20,(3,30,40)).astype('float32'),0,-1)
    initial=state();changed=copy.deepcopy(initial);changed['sliders']['Stretch']=60;changed['applied_crop']=[3,4,37,29];changed['selection']=[0,0,34,25]
    meta=dict(state=changed,history=dict(states=[initial,changed],index=1),input_files=['missing/path/light.fit'],source_name='C56')
    path=tmp_path/'C56.astro';header=fits.Header({'OBJECT':'C 56','CRPIX1':20.,'CRPIX2':15.})
    projects.save_project(path,data,header,meta)
    restored,hdr,loaded=projects.load_project(path)
    np.testing.assert_array_equal(restored,data)
    assert hdr['CRPIX1']==20 and loaded['state']==changed
    assert loaded['history']['states'][0]==initial
    assert loaded['input_files']==['missing/path/light.fit']


def test_failed_save_preserves_existing_project(tmp_path,monkeypatch):
    path=tmp_path/'work.astro';path.write_bytes(b'existing project')
    def fail(*args,**kwargs):raise OSError('Disk full')
    monkeypatch.setattr(projects.np,'save',fail)
    with pytest.raises(OSError,match='Disk full'):projects.save_project(path,np.ones((30,40,3),dtype='float32'),fits.Header(),dict(state=state()))
    assert path.read_bytes()==b'existing project'
    assert list(tmp_path.glob('*.tmp'))==[]


def test_project_rejects_invalid_arrays_and_metadata(tmp_path):
    data=np.ones((30,40,3),dtype='float32');path=tmp_path/'bad.astro'
    projects.save_project(path,data,fits.Header(),dict(state=state()))
    with ZipFile(path) as archive:entries={name:archive.read(name) for name in archive.namelist()}
    meta=json.loads(entries['project.json']);meta['state']['applied_crop']=[0,0,999,999]
    entries['project.json']=json.dumps(meta)
    with ZipFile(path,'w',ZIP_DEFLATED) as archive:
        for key,value in entries.items():archive.writestr(key,value)
    with pytest.raises(ValueError,match='crop'):projects.load_project(path)
    import io
    stream=io.BytesIO();np.save(stream,np.array([object()],dtype=object),allow_pickle=True)
    entries['linear.npy']=stream.getvalue()
    with ZipFile(path,'w') as archive:
        for key,value in entries.items():archive.writestr(key,value)
    with pytest.raises(ValueError,match='array'):projects.load_project(path)


def test_undo_redo_branches_without_copying_images():
    history=projects.EditHistory(limit=3);initial=state();history.reset(initial)
    for value in (40,50):
        current=copy.deepcopy(initial);current['sliders']['Stretch']=value;history.push(current)
    assert history.undo()['sliders']['Stretch']==40
    assert history.redo()['sliders']['Stretch']==50
    history.undo();replacement=copy.deepcopy(initial);replacement['sliders']['Stretch']=70;history.push(replacement)
    assert not history.can_redo and history.undo()['sliders']['Stretch']==40
    assert initial['sliders']['Stretch']==30


def test_histogram_reports_any_channel_clipping_and_ignores_missing_coverage():
    image=np.array([[[0,.3,.4],[.4,.5,1],[.2,.3,.4],[0,0,0]]],dtype='float32')
    bins,black,white=histogram_data(image,np.array([[True,True,True,False]]))
    assert bins.shape==(3,256) and np.all(bins.sum(axis=1)==3)
    assert black==pytest.approx(100/3) and white==pytest.approx(100/3)
