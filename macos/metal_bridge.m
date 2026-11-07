#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <string.h>

@interface EASMetalContext : NSObject
@property (nonatomic, strong) id<MTLDevice> device;
@property (nonatomic, strong) id<MTLCommandQueue> queue;
@property (nonatomic, strong) id<MTLComputePipelineState> stretch;
@property (nonatomic, strong) id<MTLComputePipelineState> blur;
@property (nonatomic, strong) id<MTLComputePipelineState> color;
@end
@implementation EASMetalContext
@end

typedef struct {
    uint32_t width, height, radius, vertical;
    float stretch, saturation, exposure, contrast;
} Params;
static void failure(char *out, size_t size, NSString *message) {
    if (out && size) snprintf(out, size, "%s", message.UTF8String ?: "Metal operation failed");
}
void *eas_metal_create(const char *shader, char *error, size_t size) {
    @autoreleasepool {
        EASMetalContext *ctx=[EASMetalContext new];
        ctx.device=MTLCreateSystemDefaultDevice();
        if (!ctx.device) { failure(error,size,@"No Metal GPU available. CPU processing is available."); return NULL; }
        ctx.queue=[ctx.device newCommandQueue];
        NSError *issue=nil;
        MTLCompileOptions *options=[MTLCompileOptions new];
        options.fastMathEnabled=NO;
        id<MTLLibrary> library=[ctx.device newLibraryWithSource:[NSString stringWithUTF8String:shader] options:options error:&issue];
        if (!library) { failure(error,size,issue.localizedDescription); return NULL; }
        ctx.stretch=[ctx.device newComputePipelineStateWithFunction:[library newFunctionWithName:@"stretch_image"] error:&issue];
        ctx.blur=[ctx.device newComputePipelineStateWithFunction:[library newFunctionWithName:@"blur_image"] error:&issue];
        ctx.color=[ctx.device newComputePipelineStateWithFunction:[library newFunctionWithName:@"color_image"] error:&issue];
        if (!ctx.queue || !ctx.stretch || !ctx.blur || !ctx.color) {
            failure(error,size,issue.localizedDescription ?: @"Could not create Metal pipelines"); return NULL;
        }
        return (__bridge_retained void *)ctx;
    }
}
void eas_metal_destroy(void *context) { if (context) { id released=CFBridgingRelease(context); (void)released; } }
const char *eas_metal_name(void *context) { return ((__bridge EASMetalContext *)context).device.name.UTF8String; }
static void dispatch(id<MTLCommandBuffer> command, id<MTLComputePipelineState> pipeline,
                     id<MTLBuffer> input, id<MTLBuffer> output, Params params,
                     id<MTLBuffer> weights, NSUInteger count) {
    id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
    [encoder setComputePipelineState:pipeline];
    [encoder setBuffer:input offset:0 atIndex:0];
    [encoder setBuffer:output offset:0 atIndex:1];
    [encoder setBytes:&params length:sizeof(params) atIndex:2];
    if (weights) [encoder setBuffer:weights offset:0 atIndex:3];
    NSUInteger group=MIN((NSUInteger)256,pipeline.maxTotalThreadsPerThreadgroup);
    [encoder dispatchThreads:MTLSizeMake(count,1,1) threadsPerThreadgroup:MTLSizeMake(group,1,1)];
    [encoder endEncoding];
}
int eas_metal_process(void *context, const float *input, float *output, uint32_t width, uint32_t height,
                      float stretch, float saturation, float exposure, float contrast,
                      const float *weights, uint32_t radius, uint32_t smooth, char *error, size_t size) {
    @autoreleasepool {
        EASMetalContext *ctx=(__bridge EASMetalContext *)context;
        size_t count=(size_t)width*height*3, bytes=count*sizeof(float);
        if (!width || !height || count>UINT32_MAX || bytes>ctx.device.maxBufferLength) {
            failure(error,size,@"Image exceeds Metal buffer limits"); return 0;
        }
        id<MTLBuffer> a=[ctx.device newBufferWithBytes:input length:bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer> b=[ctx.device newBufferWithLength:bytes options:MTLResourceStorageModeShared];
        if (!a || !b) { failure(error,size,@"Not enough GPU memory"); return 0; }
        id<MTLCommandBuffer> command=[ctx.queue commandBuffer];
        if (!command) { failure(error,size,@"Could not create Metal command buffer"); return 0; }
        Params p={width,height,radius,0,stretch,saturation,exposure,contrast};
        dispatch(command,ctx.stretch,a,b,p,nil,count);
        id<MTLBuffer> current=b, spare=a;
        if (smooth) {
            id<MTLBuffer> coefficients=[ctx.device newBufferWithBytes:weights length:(2*(size_t)radius+1)*sizeof(float) options:MTLResourceStorageModeShared];
            if (!coefficients) { failure(error,size,@"Not enough memory for smoothing"); return 0; }
            for (uint32_t vertical=0;vertical<2;++vertical) {
                p.vertical=vertical;
                dispatch(command,ctx.blur,current,spare,p,coefficients,count);
                id<MTLBuffer> temporary=current; current=spare; spare=temporary;
            }
        }
        dispatch(command,ctx.color,current,spare,p,nil,count/3);
        [command commit]; [command waitUntilCompleted];
        if (command.status!=MTLCommandBufferStatusCompleted) {
            failure(error,size,command.error.localizedDescription); return 0;
        }
        memcpy(output,spare.contents,bytes);
        return 1;
    }
}
