import numpy as np
import pytest
from astropy.io import fits
from scipy.ndimage import gaussian_filter
import engine
from stack_store import AlignedFrames,combine,clipped_mean,robust_weighted_mean
from stack_quality import quality_weights


def test_robust_rejects_masked_small_stack_trail_and_keeps_real_signal():
    # Two trail samples inflate standard deviation enough to survive old 3-sigma.
    data=np.full((8,2,3,3),100,dtype=np.float32);data[:2,0]=10000
    data[:,1]=300;weights=np.ones(8);weights[0]=4
    assert clipped_mean(data)[0,0,0]>1000
    result=robust_weighted_mean(data,weights)
    np.testing.assert_array_equal(result[0],100);np.testing.assert_array_equal(result[1],300)
    low=data[:7];expected=np.average(low.astype(np.float64),axis=0,weights=weights[:7])
    np.testing.assert_allclose(robust_weighted_mean(low,weights[:7]),expected,rtol=1e-6)
    data[:,1]=np.nan;data[0,1,0]=42
    result=robust_weighted_mean(data,weights);assert result[1,0,0]==42 and np.isnan(result[1,1]).all()


def test_weighted_chunks_parity_fallback_budget_and_invalid_weights():
    rng=np.random.default_rng(6);data=rng.normal(100,2,(25,9,13,3)).astype('float32');data[0,:2]=5000;data[:,:1,:1]=np.nan
    weights=np.linspace(.25,4,25).astype('float32');original=data.copy()
    class Broken:
        calls=0
        def combine_input_limit(self):return 8192
        def combine_weighted(self,*args):self.calls+=1;raise RuntimeError('Disconnected')
    gpu=Broken();messages=[]
    with AlignedFrames(data.shape[1:]) as store:
        for image in data:store.append(image)
        expected=np.nan_to_num(robust_weighted_mean(data,weights),nan=0)
        actual=combine(store,gpu=gpu,weights=weights,rejection='robust',input_bytes=2048,progress=messages.append)
        np.testing.assert_array_equal(actual,expected);assert gpu.calls==1
        assert any('continuing on CPU' in line for line in messages)
        with pytest.raises(ValueError):combine(store,weights=np.zeros(25),rejection='robust')
    np.testing.assert_array_equal(data,original)


def test_weights_bounded_comparable_and_improve_noise_and_star_width():
    y,x=np.mgrid[:96,:96];sharp=np.exp(-((x-48)**2+(y-48)**2)/(2*1.4**2));blur=gaussian_filter(sharp,2.8)
    rng=np.random.default_rng(11);images=[];rows=[]
    for i in range(30):
        good=i<15;noise=.03 if good else .12
        images.append(np.repeat((sharp if good else blur)[...,None],3,axis=-1)+rng.normal(0,noise,(96,96,3)))
        rows.append(dict(stars=40,noise=noise,fwhm=3.3 if good else 7.4,elongation=1,group=('same',)))
    weights=quality_weights(rows);assert weights.min()>=.25 and weights.max()<=4 and weights[:15].mean()>weights[15:].mean()
    equal=np.mean(images,axis=0);weighted=np.average(images,axis=0,weights=weights)
    assert np.std(weighted[:20])<np.std(equal[:20])*.8
    assert weighted[48,48,0]>equal[48,48,0]*1.3
    assert quality_weights([None,dict(rows[0],stars=2),dict(rows[0],group=('different',))]).tolist()==[1,1,1]


def test_stack_exposure_normalization_and_metadata(tmp_path,monkeypatch):
    paths=[]
    for i,t in enumerate([20,30]):
        path=tmp_path/f'{i}.fits';fits.writeto(path,np.ones((3,40,40),dtype='float32')*t*5,fits.Header({'EXPTIME':t,'OBJECT':'Synthetic'}));paths.append(path)
    monkeypatch.setattr(engine.astroalign,'find_transform',lambda *a:(None,None))
    monkeypatch.setattr(engine.astroalign,'apply_transform',lambda t,image,ref:(image.copy(),np.zeros(image.shape[:2],bool)))
    data,hdr=engine.stack(paths,quality=False,normalize_exposure=True)
    np.testing.assert_array_equal(data,100);assert hdr['TOTALEXP']==50 and hdr['EXPTIME']==20 and hdr['EXPMIN']==20 and hdr['EXPMAX']==30 and hdr['EASNORM']
    legacy,_=engine.stack(paths,rejection='legacy');np.testing.assert_array_equal(legacy,125)
    raw,_=engine.read_fits(paths[1]);np.testing.assert_array_equal(raw,150)


@pytest.mark.parametrize('frames',[8,25,80])
def test_weighted_robust_gpu_matches_cpu(frames):
    cl=pytest.importorskip('pyopencl')
    try:devices=[d for p in cl.get_platforms() for d in p.get_devices() if 'cl_khr_fp64' in d.extensions.split()]
    except cl.Error:pytest.skip('No OpenCL')
    if not devices:pytest.skip('No fp64 OpenCL')
    from gpu import GpuProcessor
    gpu=GpuProcessor(context=cl.Context([devices[0]]));rng=np.random.default_rng(frames)
    data=rng.normal(1000,2,(frames,100)).astype('float32');data[0,:20]=20000;data[:,21]=np.nan;data[:,22]=42;data[1:,23]=np.nan
    weights=rng.uniform(.25,4,frames).astype('float32');before=data.copy()
    expected=np.nan_to_num(robust_weighted_mean(data,weights),nan=0)
    np.testing.assert_allclose(gpu.combine_weighted(data,weights),expected,rtol=2e-6,atol=.001)
    np.testing.assert_array_equal(before,data)
