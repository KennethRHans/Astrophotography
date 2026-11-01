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
    expected=engine.render(image,stretch=17,denoise=.8,saturation=1.2)
    actual=engine.render(image,stretch=17,denoise=.8,saturation=1.2,gpu=device)
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
    for smoothing in (0,.8,1.5):
        cpu=engine.render(image,stretch=30,saturation=1.3,denoise=smoothing)
        actual=engine.render(image,stretch=30,saturation=1.3,denoise=smoothing,gpu=processor)
        assert not processor.disabled,processor.last_error
        np.testing.assert_allclose(actual,cpu,atol=3e-5,rtol=3e-5)
