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
                          const int pixels, const float saturation) {
    int i = get_global_id(0);
    if (i >= pixels) return;
    int p = i*3;
    float light = src[p]*0.2126f+src[p+1]*0.7152f+src[p+2]*0.0722f;
    for (int c=0; c<3; ++c)
        dst[p+c] = clamp(light+saturation*(src[p+c]-light),0.0f,1.0f);
}
'''


class GpuProcessor:
    def __init__(self, context=None):
        import pyopencl as cl
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

    def process(self, image, stretch, saturation, denoise):
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
        self.color_kernel(self.queue,(h*w,),None,current,spare,np.int32(h*w),np.float32(saturation))
        result = np.empty_like(source)
        cl.enqueue_copy(self.queue,result,spare).wait()
        return result
