import numpy as np
import pytest
from astropy.stats import sigma_clip
from stack_store import AlignedFrames, combine, clipped_mean


def test_disk_chunks_match_full_sigma_clip_and_obey_budget():
    rng = np.random.default_rng(91)
    data = rng.normal(1000, 8, (43, 17, 23, 3)).astype('float32')
    data[0, 5:8] = 20000  # satellites/hot pixels
    data[:, :2, :2] = np.nan  # no coverage
    data[1:, 3, 3] = np.nan  # one covered sample
    expected = np.nan_to_num(clipped_mean(data), nan=0)
    with AlignedFrames(data.shape[1:]) as store:
        for frame in data:
            store.append(frame)
        sizes = []
        original_read = store.read
        def read(first, last):
            block = original_read(first, last); sizes.append(block.nbytes); return block
        store.read = read
        events = []
        # Deliberately less than one full row to verify horizontal chunking.
        budget = 43*4*19
        result = combine(store, input_bytes=budget, report_progress=lambda *e: events.append(e))
        assert max(sizes) <= budget and len(sizes) > 1
        np.testing.assert_array_equal(result, expected)
        assert events[0] == (0, 17, 'Combining image rows')
        assert events[-1] == (17, 17, 'Combining image rows')
        assert all(a[0] <= b[0] for a,b in zip(events, events[1:]))
        backing = store.file
    assert backing.closed


def test_gpu_failure_retries_intact_chunk_on_cpu_and_cancellation_cleans_up():
    data = np.arange(12*7*9*3, dtype=np.float32).reshape(12, 7, 9, 3)
    class BrokenGpu:
        calls = 0
        def combine_input_limit(self): return 4096
        def combine(self, block):
            self.calls += 1
            raise RuntimeError('GPU ran out of memory')
    gpu = BrokenGpu(); log = []
    with AlignedFrames(data.shape[1:]) as store:
        for frame in data: store.append(frame)
        result = combine(store, gpu=gpu, progress=log.append, input_bytes=1024)
        np.testing.assert_array_equal(result, clipped_mean(data))
        assert gpu.calls == 1 and any('continuing on CPU' in line for line in log)
        with pytest.raises(InterruptedError): combine(store, cancelled=lambda: True)
        backing = store.file
    assert backing.closed


@pytest.mark.parametrize('frames', [2, 3, 8, 10, 32, 299, 512])
def test_opencl_combining_matches_astropy(frames):
    cl = pytest.importorskip('pyopencl')
    try: devices = [d for p in cl.get_platforms() for d in p.get_devices()]
    except cl.Error: pytest.skip('No OpenCL runtime available')
    if not devices: pytest.skip('No OpenCL device available')
    from gpu import GpuProcessor
    device = next((d for d in devices if 'cl_khr_fp64' in d.extensions.split()), None)
    if device is None: pytest.skip('No double-precision OpenCL device available')
    gpu = GpuProcessor(context=cl.Context([device]))
    rng = np.random.default_rng(frames)
    data = rng.normal(2000, 40, (frames, 313)).astype('float32')
    data[:, 0] = np.nan
    data[:, 1] = 42
    data[1:, 2] = np.nan
    data[:, 3] = 0
    data[:, 4] = 12000 + rng.normal(0, .03, frames)
    if frames >= 32:
        data[:2, 10:30] = 30000
        data[2:4, 10:30] = 2600  # second rejection after the bright outliers
    data[rng.random(data.shape) < .03] = np.nan
    if frames == 10:
        # Construct values near the 3-sigma boundary. Rounding the average of
        # the two median samples to float32 can wrongly retain/reject a pixel.
        base = rng.normal(10000, 40, (9, 80)).astype('float32').astype('float64')
        lo = base.max(axis=0); hi = lo + 10000
        for _ in range(64):
            mid = (lo+hi)/2
            samples = np.vstack([base, mid])
            above = mid > np.median(samples,axis=0)+3*np.std(samples,axis=0)
            hi = np.where(above,mid,hi); lo = np.where(above,lo,mid)
        boundary = ((lo+hi)/2).astype('float32')
        near = [np.nextafter(boundary,-np.inf),boundary,np.nextafter(boundary,np.inf)]
        data = np.concatenate([data,*[np.vstack([base,value]).astype('float32') for value in near]],axis=1)
    original = data.copy()
    expected = np.nan_to_num(clipped_mean(data), nan=0)
    actual = gpu.combine(data)
    np.testing.assert_allclose(actual, expected, atol=.003, rtol=2e-6)
    np.testing.assert_array_equal(data, original)
