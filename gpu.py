"""Optional OpenCL image adjustments. No driver or GPU is required for CPU use."""
import numpy as np

SOURCE = r'''
__kernel void stretch_image(__global const float *src, __global float *dst,
                            const int n, const float amount) {
    int i = get_global_id(0);
    if (i < n) dst[i] = amount > 0 ? asinh(src[i]*amount)/asinh(amount) : src[i];
}
int reflected(int i, int size) {
    while (i < 0 || i >= size) i = i < 0 ? -i-1 : 2*size-i-1;
    return i;
}
__kernel void blur_image(__global const float *src, __global float *dst,
                         __constant const float *weights, const int radius,
                         const int width, const int height, const int vertical) {
    int i = get_global_id(0);
    if (i >= width*height*3) return;
    int channel = i%3, x = (i/3)%width, y = i/(width*3);
    float total = 0;
    for (int k = -radius; k <= radius; ++k) {
        int xx = vertical ? x : reflected(x+k,width);
        int yy = vertical ? reflected(y+k,height) : y;
        total += src[(yy*width+xx)*3+channel]*weights[k+radius];
    }
    dst[i] = total;
}
__kernel void color_image(__global const float *src, __global float *dst,
                          const int pixels, const float saturation, const float exposure, const float contrast) {
    int i = get_global_id(0);
    if (i >= pixels) return;
    int p = i*3;
    float light = src[p]*0.2126f+src[p+1]*0.7152f+src[p+2]*0.0722f;
    for (int c=0; c<3; ++c) {
        float value = clamp(light+saturation*(src[p+c]-light),0.0f,1.0f);
        if (exposure != 1.0f || contrast != 1.0f) value=(value*exposure-0.18f)*contrast+0.18f;
        dst[p+c] = clamp(value,0.0f,1.0f);
    }
}
'''


class GpuProcessor:
    def __init__(self, context=None):
        import pyopencl as cl
        import pyopencl.invoker  # OpenCL extension imports this dynamically; include it in the frozen app.
        self.cl = cl
        if context is None:
            devices = []
            try:
                for platform in cl.get_platforms():
                    devices.extend(platform.get_devices(device_type=cl.device_type.GPU))
            except cl.Error as exc:
                raise RuntimeError('OpenCL GPU driver unavailable. CPU processing is available.') from exc
            if not devices:
                raise RuntimeError('No OpenCL GPU found. Update the graphics driver, or use CPU processing.')
            devices.sort(key=lambda d: ('nvidia' not in d.vendor.lower(), -d.global_mem_size))
            context = cl.Context([devices[0]])
        self.context = context
        self.queue = cl.CommandQueue(context)
        self.name = context.devices[0].name.strip()
        self.disabled = False
        self.last_error = None
        program = cl.Program(context, SOURCE).build()
        self.stretch_kernel = cl.Kernel(program, 'stretch_image')
        self.blur_kernel = cl.Kernel(program, 'blur_image')
        self.color_kernel = cl.Kernel(program, 'color_image')

    def process(self, image, stretch, saturation, denoise, brightness=0, contrast=1):
        cl = self.cl
        source = np.ascontiguousarray(image, dtype=np.float32)
        h, w, _ = source.shape
        a = cl.Buffer(self.context, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=source)
        b = cl.Buffer(self.context, cl.mem_flags.READ_WRITE, source.nbytes)
        self.stretch_kernel(self.queue, (source.size,), None, a, b, np.int32(source.size), np.float32(stretch))
        current, spare = b, a
        if denoise > 0:
            radius = int(4*denoise+.5)
            x = np.arange(-radius,radius+1,dtype=np.float64)
            weights = np.exp(-.5*(x/denoise)**2)
            weights = (weights/weights.sum()).astype(np.float32)
            weights_buffer = cl.Buffer(self.context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=weights)
            for vertical in (0,1):
                self.blur_kernel(self.queue,(source.size,),None,current,spare,weights_buffer,np.int32(radius),np.int32(w),np.int32(h),np.int32(vertical))
                current, spare = spare, current
        self.color_kernel(self.queue,(h*w,),None,current,spare,np.int32(h*w),np.float32(saturation),np.float32(2.**brightness),np.float32(contrast))
        result = np.empty_like(source)
        cl.enqueue_copy(self.queue,result,spare).wait()
        return result

    def combine_input_limit(self):
        device = self.context.devices[0]
        return int(min(device.max_mem_alloc_size//2, device.global_mem_size//8))

    def combine(self, block):
        """Three iterations of median-centered 3-sigma clipping across frames.

        One work item per scalar RGB sample. GPU scratch is a single chunk;
        the host input is preserved so CPU fallback can safely retry it.
        """
        cl = self.cl
        if not hasattr(self, 'combine_kernel'):
            use_double = 'cl_khr_fp64' in self.context.devices[0].extensions.split()
            if not use_double:
                raise RuntimeError('GPU combining requires double-precision OpenCL for reliable clipping; image adjustments can still use this GPU.')
            prefix = '#pragma OPENCL EXTENSION cl_khr_fp64 : enable\ntypedef double acc_t;\n'
            program = cl.Program(self.context, prefix+COMBINE_SOURCE).build()
            self.combine_kernel = cl.Kernel(program, 'combine_frames')
        source = np.ascontiguousarray(block, dtype=np.float32)
        count, pixels = source.shape
        if source.nbytes > self.combine_input_limit():
            raise MemoryError('GPU stack chunk exceeds the device allocation budget.')
        a = cl.Buffer(self.context, cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR, hostbuf=source)
        result = np.empty(pixels, dtype=np.float32)
        b = cl.Buffer(self.context, cl.mem_flags.WRITE_ONLY, result.nbytes)
        try:
            self.combine_kernel(self.queue, (pixels,), None, a, b, np.int32(count), np.int32(pixels))
            cl.enqueue_copy(self.queue, result, b).wait()
        finally:
            self.queue.finish()
            a.release(); b.release()
        return result


COMBINE_SOURCE = r'''
// In-place quickselect in the frame dimension. Each pixel owns independent
// addresses; adjacent work items access adjacent scalar samples.
float select_k(__global float *v, int stride, int pixel, int n, int k) {
    int lo=0, hi=n-1;
    while (lo < hi) {
        float pivot=v[((lo+hi)/2)*stride+pixel];
        int i=lo, j=hi;
        while (i<=j) {
            while (i<=hi && v[i*stride+pixel]<pivot) ++i;
            while (j>=lo && v[j*stride+pixel]>pivot) --j;
            if (i<=j) {
                float t=v[i*stride+pixel];
                v[i*stride+pixel]=v[j*stride+pixel];
                v[j*stride+pixel]=t;
                ++i; --j;
            }
        }
        if (k<=j) hi=j;
        else if (k>=i) lo=i;
        else break;
    }
    return v[k*stride+pixel];
}
__kernel void combine_frames(__global float *v, __global float *out,
                              const int frames, const int pixels) {
    int p=get_global_id(0);
    if (p>=pixels) return;
    int n=0;
    for (int f=0; f<frames; ++f) {
        float value=v[f*pixels+p];
        if (isfinite(value)) v[(n++)*pixels+p]=value;
    }
    for (int iteration=0; iteration<3 && n>0; ++iteration) {
        acc_t median=(acc_t)select_k(v,pixels,p,n,n/2);
        if (n%2==0) {
            // Avoid summation overflow for large finite input values.
            median=median*(acc_t)0.5+(acc_t)select_k(v,pixels,p,n,n/2-1)*(acc_t)0.5;
        }
        acc_t mean=0, m2=0;
        for (int f=0; f<n; ++f) {
            acc_t value=v[f*pixels+p], delta=value-mean;
            mean+=delta/(f+1);
            m2+=delta*(value-mean);
        }
        acc_t deviation=sqrt(fmax(m2/n,(acc_t)0));
        acc_t low=(acc_t)median-3*deviation, high=(acc_t)median+3*deviation;
        int kept=0;
        for (int f=0; f<n; ++f) {
            float value=v[f*pixels+p];
            if (value>=low && value<=high) v[(kept++)*pixels+p]=value;
        }
        if (kept==n) break;
        n=kept;
    }
    acc_t total=0;
    for (int f=0; f<n; ++f) total+=(acc_t)v[f*pixels+p];
    out[p]=n ? (float)(total/n) : 0.0f;
}
'''
