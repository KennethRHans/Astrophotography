import sys
import numpy as np
import pytest
import engine


def test_mac_stacking_factory_does_not_request_metal(monkeypatch):
    import gpu
    monkeypatch.setattr(sys, 'platform', 'darwin')
    assert gpu.create_gpu_processor(for_stacking=True) is None


@pytest.mark.skipif(sys.platform != 'darwin', reason='Metal requires macOS')
def test_metal_matches_cpu_and_preserves_input():
    import ctypes
    from metal_gpu import MetalProcessor
    probe = ctypes.CDLL('/System/Library/Frameworks/Metal.framework/Metal')
    probe.MTLCreateSystemDefaultDevice.restype = ctypes.c_void_p
    if not probe.MTLCreateSystemDefaultDevice():
        pytest.skip('Runner has no Metal device; numerical GPU validation needs a real Mac')
    processor = MetalProcessor()  # Shader/bridge/validation failures must fail, not skip.
    try:
        image = np.random.default_rng(44).uniform(100, 1500, (80, 100, 3)).astype('float32')
        image[:2] = 0
        original = image.copy()
        for stretch, smoothing, saturation, brightness, contrast in [
            (0, 0, 0, 0, 1), (30, .8, 1.3, .5, 1.4),
            (17, 1.5, 2, -.5, .8), (60, 3, 1, 0, 1),
        ]:
            settings = dict(stretch=stretch, denoise=smoothing, saturation=saturation,
                            brightness=brightness, contrast=contrast)
            expected = engine.render(image, **settings)
            actual = engine.render(image, gpu=processor, **settings)
            assert not processor.disabled, processor.last_error
            np.testing.assert_allclose(actual, expected, atol=3e-5, rtol=3e-5)
            np.testing.assert_array_equal(image, original)
    finally:
        processor.close()
