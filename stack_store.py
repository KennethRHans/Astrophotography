"""Bounded-memory storage and combination of aligned linear RGB exposures."""
import tempfile
import warnings
import numpy as np
from astropy.stats import sigma_clip

# This is input chunk size, not total process RAM. CPU clipping needs extra
# masks/statistics; the final RGB image and alignment also require memory.
COMBINE_INPUT_BYTES = 32 * 1024 * 1024


class AlignedFrames:
    """Explicit disk I/O avoids retaining a whole stack as mapped process pages."""
    def __init__(self, shape):
        self.shape = tuple(shape)
        self.elements = int(np.prod(shape))
        self.count = 0
        self.file = tempfile.TemporaryFile(prefix='EasyAstroStudio-', buffering=0)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.file.close()

    def append(self, image):
        if image.shape != self.shape:
            raise ValueError('Aligned image dimensions differ.')
        data = np.ascontiguousarray(image, dtype=np.float32)
        self.file.seek(self.count * self.elements * 4)
        view = memoryview(data).cast('B')
        while view:
            written = self.file.write(view)
            if not written:
                raise OSError('Could not write aligned exposure to temporary disk.')
            view = view[written:]
        self.count += 1

    def read(self, first, last):
        if not 0 <= first < last <= self.elements:
            raise ValueError('Invalid stack chunk.')
        block = np.empty((self.count, last-first), dtype=np.float32)
        for frame in range(self.count):
            self.file.seek((frame*self.elements+first)*4)
            view = memoryview(block[frame]).cast('B')
            while view:
                got = self.file.readinto(view)
                if not got:
                    raise OSError('Incomplete temporary aligned exposure.')
                view = view[got:]
        return block


def clipped_mean(block):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        # Invalid border coverage is expected, and excluded from each sample.
        warnings.simplefilter('ignore', category=UserWarning)
        clipped = sigma_clip(block, sigma=3, maxiters=3, axis=0)
        return np.ma.mean(clipped, axis=0).filled(np.nan).astype(np.float32)


def combine(store, gpu=None, progress=lambda s: None, cancelled=lambda: False,
            report_progress=lambda done,total,stage: None,
            input_bytes=COMBINE_INPUT_BYTES):
    h, w, _ = store.shape
    # Device allocation limits and a small host staging buffer both apply.
    budget = input_bytes
    if gpu is not None:
        budget = min(budget, gpu.combine_input_limit())
    if budget < store.count*4:
        raise ValueError('Stack chunk budget is too small for one sample.')
    samples = max(1, budget//(store.count*4))
    # Prefer whole rows when possible; exceptionally large batches can use
    # smaller horizontal chunks without exceeding the input budget.
    if samples >= w*3:
        samples = min(32, samples//(w*3)) * w*3
    output = np.empty(store.shape, dtype=np.float32)
    flat = output.reshape(-1)
    backend = 'GPU' if gpu is not None else 'CPU'
    progress(f'Combining on {backend}; input chunks up to {budget/(1024**2):.1f} MiB. '
             'Alignment remains on CPU; temporary frames stay on disk.')
    report_progress(0, h, 'Combining image rows')
    previous_row = 0
    for first in range(0, store.elements, samples):
        if cancelled():
            raise InterruptedError('Cancelled')
        last = min(first+samples, store.elements)
        block = store.read(first, last)
        if gpu is not None:
            try:
                result = gpu.combine(block)
                if result.shape != (last-first,) or not np.isfinite(result).all():
                    raise RuntimeError('GPU returned invalid combined pixels.')
            except Exception as exc:
                progress(f'GPU combining failed; continuing on CPU with bounded chunks: {exc}')
                gpu = None
                result = clipped_mean(block)
        else:
            result = clipped_mean(block)
        # Uncovered pixels are black, never extrapolated detail.
        np.nan_to_num(result, copy=False, nan=0, posinf=0, neginf=0)
        flat[first:last] = result
        del block, result
        row = last//(w*3)
        if row > previous_row:
            progress(f'Combining rows {previous_row+1}–{row}; {store.count} aligned frames • {"GPU" if gpu is not None else "CPU"}')
            report_progress(row, h, 'Combining image rows')
            previous_row = row
    return output
