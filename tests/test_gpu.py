import numpy as np
import pytest
import engine


def test_gpu_failure_uses_cpu_result():
    class FailedDevice:
        disabled = False
        last_error = None
        def process(self, *args):
            raise RuntimeError('Device disconnected')
    device = FailedDevice()
    image=np.random.default_rng(10).uniform(100,500,(40,50,3)).astype('float32')
    expected=engine.render(image,stretch=17,denoise=.8,saturation=1.2,sky=.3)
    actual=engine.render(image,stretch=17,denoise=.8,saturation=1.2,gpu=device,sky=.3)
    np.testing.assert_array_equal(actual,expected)
    assert device.disabled and device.last_error == 'Device disconnected'


def test_opencl_matches_cpu_adjustments():
    cl=pytest.importorskip('pyopencl')
    try:
        devices=[d for p in cl.get_platforms() for d in p.get_devices()]
    except cl.Error:
        pytest.skip('No OpenCL runtime available')
    if not devices:
        pytest.skip('No OpenCL device available')
    from gpu import GpuProcessor
    processor=GpuProcessor(context=cl.Context([devices[0]]))
    image=np.random.default_rng(12).uniform(100,1500,(80,100,3)).astype('float32')
    image[:2]=0
    for smoothing,brightness,contrast,sky in [(0,0,1,0),(.8,.5,1.4,.3),(1.5,-.5,.8,-.2)]:
        cpu=engine.render(image,stretch=30,saturation=1.3,denoise=smoothing,brightness=brightness,contrast=contrast,sky=sky)
        actual=engine.render(image,stretch=30,saturation=1.3,denoise=smoothing,gpu=processor,brightness=brightness,contrast=contrast,sky=sky)
        assert not processor.disabled,processor.last_error
        np.testing.assert_allclose(actual,cpu,atol=3e-5,rtol=3e-5)


def test_shared_opencl_processor_is_safe_for_background_preview_and_export():
    from concurrent.futures import ThreadPoolExecutor
    cl=pytest.importorskip('pyopencl')
    try:devices=[d for p in cl.get_platforms() for d in p.get_devices()]
    except cl.Error:pytest.skip('No OpenCL runtime available')
    if not devices:pytest.skip('No OpenCL device available')
    from gpu import GpuProcessor
    processor=GpuProcessor(context=cl.Context([devices[0]]))
    image=np.random.default_rng(33).uniform(100,2000,(64,80,3)).astype('float32')
    adjustments=[(-.5,1.2,.3),(.5,.8,-.2),(0,1,0),(.2,1.3,.1)]
    def run(values):
        brightness,contrast,sky=values
        return engine.render(image,stretch=22,denoise=.8,saturation=1.2,brightness=brightness,contrast=contrast,sky=sky,gpu=processor)
    with ThreadPoolExecutor(max_workers=2) as pool:actual=list(pool.map(run,adjustments))
    for result,(brightness,contrast,sky) in zip(actual,adjustments):
        expected=engine.render(image,stretch=22,denoise=.8,saturation=1.2,brightness=brightness,contrast=contrast,sky=sky)
        np.testing.assert_allclose(result,expected,atol=3e-5,rtol=3e-5)
    assert not processor.disabled,processor.last_error


def test_opencl_reuses_image_buffers_without_reusing_old_pixels():
    cl=pytest.importorskip('pyopencl')
    try:devices=[d for p in cl.get_platforms() for d in p.get_devices()]
    except cl.Error:pytest.skip('No OpenCL runtime available')
    if not devices:pytest.skip('No OpenCL device available')
    from gpu import GpuProcessor
    processor=GpuProcessor(context=cl.Context([devices[0]]));rng=np.random.default_rng(51)
    a=rng.uniform(.01,.8,(64,80,3)).astype('float32');b=rng.uniform(.2,1,(80,64,3)).astype('float32')
    processor.process(a,17,1.1,.8,.2,1.2);handles=tuple(buf.int_ptr for buf in processor._image_buffers[1:]);weight=processor._blur_weights[1].int_ptr
    actual=processor.process(b,17,1.1,.8,.2,1.2)
    expected=engine.render(b,stretch=17,saturation=1.1,denoise=.8,brightness=.2,contrast=1.2,normalization=(b,np.ones(b.shape[:2],dtype=bool)))
    np.testing.assert_allclose(actual,expected,atol=3e-5,rtol=3e-5)
    assert handles==tuple(buf.int_ptr for buf in processor._image_buffers[1:]) and weight==processor._blur_weights[1].int_ptr
