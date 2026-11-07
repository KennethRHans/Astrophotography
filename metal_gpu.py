"""Apple Metal image adjustments; stacking deliberately remains on CPU."""
import ctypes
from pathlib import Path
import sys
import numpy as np


class MetalProcessor:
    def __init__(self):
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        library = root / 'libEasyAstroMetal.dylib'
        if not library.exists():
            library = root / 'build/metal/libEasyAstroMetal.dylib'
        if not library.exists():
            raise RuntimeError('Metal bridge is not built. Run python scripts/build_metal.py on a Mac.')
        self.lib = ctypes.CDLL(str(library))
        pointer = ctypes.c_void_p
        self.lib.eas_metal_create.argtypes = [ctypes.c_char_p, pointer, ctypes.c_size_t]
        self.lib.eas_metal_create.restype = pointer
        self.lib.eas_metal_destroy.argtypes = [pointer]
        self.lib.eas_metal_destroy.restype = None
        self.lib.eas_metal_name.argtypes = [pointer]
        self.lib.eas_metal_name.restype = ctypes.c_char_p
        self.lib.eas_metal_process.argtypes = [pointer, pointer, pointer,
            ctypes.c_uint32, ctypes.c_uint32, *([ctypes.c_float]*4), pointer,
            ctypes.c_uint32, ctypes.c_uint32, pointer, ctypes.c_size_t]
        self.lib.eas_metal_process.restype = ctypes.c_int
        error = ctypes.create_string_buffer(4096)
        source = (root / 'macos/adjustments.metal').read_bytes()
        self.context = self.lib.eas_metal_create(source, error, len(error))
        if not self.context:
            raise RuntimeError(error.value.decode('utf-8', errors='replace'))
        self.name = 'Metal: ' + self.lib.eas_metal_name(self.context).decode()
        self.disabled = False
        self.last_error = None
        self.validate()

    def validate(self):
        from engine import render
        sample = np.random.default_rng(71).uniform(100, 1500, (24, 32, 3)).astype('float32')
        sample[:2] = 0
        for smoothing in (0, .8):
            reference = render(sample, stretch=17, saturation=1.3, denoise=smoothing,
                               brightness=.5, contrast=1.2)
            result = render(sample, stretch=17, saturation=1.3, denoise=smoothing,
                            brightness=.5, contrast=1.2, gpu=self)
            if self.disabled or not np.allclose(reference, result, atol=3e-5, rtol=3e-5):
                self.close()
                raise RuntimeError('Metal numerical validation failed; CPU processing remains available. '
                                   + str(self.last_error or 'CPU/GPU results differ'))

    def close(self):
        context = getattr(self, 'context', None)
        if context:
            self.lib.eas_metal_destroy(context)
            self.context = None

    def __del__(self):
        self.close()

    def process(self, image, stretch, saturation, denoise, brightness=0, contrast=1):
        if not self.context:
            raise RuntimeError('Metal processor is closed')
        source = np.ascontiguousarray(image, dtype=np.float32)
        if source.ndim != 3 or source.shape[2] != 3 or not source.size:
            raise ValueError('Metal requires a nonempty RGB image')
        if not np.isfinite(source).all():
            raise ValueError('Metal input must be finite')
        values = (stretch, saturation, denoise, brightness, contrast)
        if not np.isfinite(values).all() or denoise < 0:
            raise ValueError('Invalid image adjustment parameters')
        radius = int(4*denoise+.5) if denoise else 0
        positions = np.arange(-radius, radius+1, dtype=np.float64)
        weights = np.exp(-.5*(positions/denoise)**2) if denoise else np.ones(1)
        weights = np.asarray(weights/weights.sum(), dtype=np.float32)
        output = np.empty_like(source)
        error = ctypes.create_string_buffer(4096)
        ok = self.lib.eas_metal_process(self.context, source.ctypes.data, output.ctypes.data,
            source.shape[1], source.shape[0], stretch, saturation, 2.**brightness, contrast,
            weights.ctypes.data, radius, bool(denoise), error, len(error))
        if not ok:
            raise RuntimeError(error.value.decode('utf-8', errors='replace'))
        return output
