#include <metal_stdlib>
using namespace metal;
struct Params {
    uint width, height, radius, vertical;
    float stretch, saturation, exposure, contrast;
};
kernel void stretch_image(device const float *src [[buffer(0)]], device float *dst [[buffer(1)]],
                          constant Params &p [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    if (i >= p.width*p.height*3) return;
    dst[i] = p.stretch > 0 ? asinh(src[i]*p.stretch)/asinh(p.stretch) : src[i];
}
int reflected(int i, int size) {
    while (i < 0 || i >= size) i = i < 0 ? -i-1 : 2*size-i-1;
    return i;
}
kernel void blur_image(device const float *src [[buffer(0)]], device float *dst [[buffer(1)]],
                       constant Params &p [[buffer(2)]], device const float *weights [[buffer(3)]],
                       uint i [[thread_position_in_grid]]) {
    if (i >= p.width*p.height*3) return;
    int channel=i%3, x=(i/3)%p.width, y=i/(p.width*3);
    float total=0;
    for (int k=-int(p.radius); k<=int(p.radius); ++k) {
        int xx=p.vertical ? x : reflected(x+k, p.width);
        int yy=p.vertical ? reflected(y+k, p.height) : y;
        total += src[(yy*p.width+xx)*3+channel]*weights[k+int(p.radius)];
    }
    dst[i]=total;
}
kernel void color_image(device const float *src [[buffer(0)]], device float *dst [[buffer(1)]],
                        constant Params &p [[buffer(2)]], uint i [[thread_position_in_grid]]) {
    if (i >= p.width*p.height) return;
    uint offset=i*3;
    float light=src[offset]*0.2126f+src[offset+1]*0.7152f+src[offset+2]*0.0722f;
    for (uint c=0;c<3;++c) {
        float value=clamp(light+p.saturation*(src[offset+c]-light),0.0f,1.0f);
        if (p.exposure!=1.0f || p.contrast!=1.0f) value=(value*p.exposure-0.18f)*p.contrast+0.18f;
        dst[offset+c]=clamp(value,0.0f,1.0f);
    }
}
