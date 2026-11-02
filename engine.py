"""Linear FITS processing. Never modifies input files."""
from pathlib import Path
import numpy as np
import cv2
import astroalign
from astropy.io import fits
from scipy.ndimage import gaussian_filter
import tifffile
from PIL import Image
from stack_store import AlignedFrames, combine


def read_fits(path, bayer='Auto'):
    with fits.open(path, memmap=False) as hdus:
        hdu = next((h for h in hdus if h.data is not None and h.data.ndim in (2, 3)), None)
        if hdu is None:
            raise ValueError('No 2D or RGB image found in FITS file.')
        data = np.array(hdu.data, dtype=np.float32)
        header = hdu.header.copy()
    if not np.isfinite(data).all():
        raise ValueError('FITS contains nonfinite pixels; repair the source before processing.')
    if data.ndim == 3:
        if data.shape[0] == 3:
            data = np.moveaxis(data, 0, -1)
        if data.shape[-1] != 3:
            raise ValueError('Only RGB cubes with three channels are supported.')
    else:
        pattern = str(header.get('BAYERPAT', '')).strip().upper() if bayer == 'Auto' else bayer
        if pattern in ('RGGB', 'BGGR', 'GRBG', 'GBRG'):
            if int(header.get('XBAYROFF', 0)) % 2 or int(header.get('YBAYROFF', 0)) % 2:
                raise ValueError('Odd Bayer offsets require a corrected Bayer pattern/header.')
            low, high = float(data.min()), float(data.max())
            scale = max(high - low, 1e-12)
            raw = np.round(np.clip((data-low)/scale, 0, 1)*65535).astype(np.uint16)
            # Explicit four-letter OpenCV codes avoid its ambiguous two-letter aliases.
            code = getattr(cv2, 'COLOR_Bayer'+pattern+'2RGB')
            data = cv2.cvtColor(raw, code).astype(np.float32)/65535*scale+low
        elif pattern not in ('', 'None'):
            raise ValueError(f'Unsupported Bayer pattern: {pattern}')
        else:
            data = np.repeat(data[..., None], 3, axis=-1)
    return data, header



def frame_count(header):
    """Seestar uses STACKCNT; our stacks use NCOMBINE."""
    return max(int(header.get('STACKCNT', 1)), int(header.get('NCOMBINE', 1)))


def image_summary(data, header):
    count = frame_count(header)
    exposure = header.get('TOTALEXP')
    if exposure is None:
        exposure = float(header.get('EXPTIME', header.get('EXPOSURE', 0))) * count
    return (f"{header.get('OBJECT', 'Unknown target')} • {data.shape[1]} × {data.shape[0]} RGB"
            f" • {count} exposure(s) • {float(exposure):g} seconds total")


def stack(paths, bayer='Auto', progress=lambda s: None, cancelled=lambda: False,
          report_progress=lambda completed, total, stage: None, gpu=None):
    if len(paths) < 2:
        raise ValueError('Select at least two individual exposures, or open one finished stack.')
    for path in paths:
        if frame_count(fits.getheader(path)) > 1:
            raise ValueError(f'{Path(path).name} is already stacked. Use Open existing FITS stack.')
    reference, header = read_fits(paths[0], bayer)
    h, w, _ = reference.shape
    # Explicit disk I/O and bounded staging buffers keep the entire stack out
    # of process RAM even after every aligned frame has been accessed.
    with AlignedFrames(reference.shape) as frames:
        frames.append(reference)
        report_progress(1, len(paths), 'Aligning exposures')
        total_exposure = float(header.get('EXPTIME', header.get('EXPOSURE', 0)))
        for i, path in enumerate(paths[1:], 1):
            if cancelled():
                raise InterruptedError('Cancelled')
            progress(f'Aligning {i+1}/{len(paths)}: {Path(path).name}')
            moving, moving_header = read_fits(path, bayer)
            if moving.shape != reference.shape:
                raise ValueError(f'Image dimensions differ: {Path(path).name}')
            try:
                transform, _ = astroalign.find_transform(moving.mean(axis=-1), reference.mean(axis=-1))
                aligned, footprint = astroalign.apply_transform(transform, moving, reference)
                aligned[footprint] = np.nan
                frames.append(aligned)
                total_exposure += float(moving_header.get('EXPTIME', moving_header.get('EXPOSURE', 0)))
                del aligned, footprint
            except (astroalign.MaxIterError, ValueError, RuntimeError) as exc:
                progress(f'Skipped {Path(path).name}: {exc}')
            del moving
            report_progress(i+1, len(paths), 'Aligning exposures')
        accepted = frames.count
        if accepted < 2:
            raise ValueError('Could not align a second exposure. Try a sharper reference frame first.')
        del reference
        output = combine(frames, gpu, progress, cancelled, report_progress)
    header['NCOMBINE'] = accepted
    header['TOTALEXP'] = (total_exposure, 'Total accepted exposure time in seconds')
    header.add_history('Easy Astro Studio: star similarity alignment; 3-sigma clipped mean.')
    return output, header


def background_model(linear):
    """Robust quadratic sky fit to grid medians; may also fit extended nebulosity.

    Coordinates are normalized to [-1, 1]. Coefficients can be reused at any
    preview size without refitting or touching the original image.
    """
    h, w, _ = linear.shape
    if min(h, w) < 24:
        return np.zeros((6, 3), dtype=np.float64)
    ys = np.linspace(0, h, 13, dtype=int)
    xs = np.linspace(0, w, 13, dtype=int)
    design, samples = [], []
    for y0, y1 in zip(ys[:-1], ys[1:]):
        for x0, x1 in zip(xs[:-1], xs[1:]):
            # Sampling every few pixels limits computation on very large frames.
            tile = linear[y0:y1:max(1, (y1-y0)//64), x0:x1:max(1, (x1-x0)//64)]
            valid = np.isfinite(tile).all(axis=-1) & (tile > 0).all(axis=-1)
            if valid.sum() < tile.shape[0]*tile.shape[1]*.8:
                continue
            x = (x0+x1-1)/max(w-1, 1)-1
            y = (y0+y1-1)/max(h-1, 1)-1
            design.append([1, x, y, x*x, x*y, y*y])
            samples.append(np.median(tile[valid], axis=0))
    if len(samples) < 24:
        return np.zeros((6, 3), dtype=np.float64)
    design, samples = np.array(design), np.array(samples)
    coefficients = np.zeros((6, 3), dtype=np.float64)
    for channel in range(3):
        keep = np.ones(len(samples), dtype=bool)
        for _ in range(5):
            fit = np.linalg.lstsq(design[keep], samples[keep, channel], rcond=None)[0]
            residual = samples[:, channel]-design@fit
            center = np.median(residual[keep])
            scatter = max(float(1.4826*np.median(np.abs(residual[keep]-center))), 1e-6)
            new_keep = np.abs(residual-center) < 2.5*scatter
            if new_keep.sum() < 24 or np.array_equal(new_keep, keep):
                break
            keep = new_keep
        coefficients[:, channel] = fit
    return coefficients


def correct_background(linear, strength=0, model=None):
    image = linear.astype(np.float32).copy()
    if strength == 0:
        return image
    if model is None:
        model = background_model(linear)
    h, w, _ = image.shape
    x = np.linspace(-1, 1, w, dtype=np.float32)[None, :, None]
    # Row blocks avoid allocating another full image for the fitted background.
    for first in range(0, h, 64):
        last = min(first+64, h)
        y = np.linspace(-1, 1, h, dtype=np.float32)[first:last, None, None]
        # Leave the constant term intact; remove only spatial variation.
        sky = x*model[1]+y*model[2]+x*x*model[3]+x*y*model[4]+y*y*model[5]
        image[first:last] -= strength*sky.astype(np.float32)
    return image


def render(linear, stretch=30, black=0.1, saturation=1, denoise=0,
           gradient=0, gains=(1, 1, 1), brightness=0, contrast=1, model=None, gpu=None):
    image = correct_background(linear, gradient, model)
    valid = (linear > 0).all(axis=-1)
    sample = image[valid]
    if not sample.size:
        return np.zeros_like(image)
    floor = np.percentile(sample, black, axis=0)
    image = np.maximum(image-floor, 0)
    image *= np.asarray(gains, dtype=np.float32)
    white = max(float(np.percentile(image[valid], 99.9)), 1e-12)
    image = np.clip(image/white, 0, 1)
    if gpu is not None and not gpu.disabled:
        try:
            result = gpu.process(image, stretch, saturation, denoise, brightness, contrast)
            if not np.isfinite(result).all():
                raise RuntimeError('GPU returned nonfinite pixels')
            result[~valid] = 0
            return result
        except Exception as exc:
            gpu.disabled = True
            gpu.last_error = str(exc)
            # Re-run from the same normalized image on CPU after a GPU failure.
    image = np.arcsinh(image*stretch)/np.arcsinh(stretch) if stretch > 0 else image
    if denoise:
        image = gaussian_filter(image, sigma=(denoise, denoise, 0))
    luminance = image @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    image = np.clip(luminance[..., None]+saturation*(image-luminance[..., None]), 0, 1)
    if brightness != 0 or contrast != 1:
        image = np.clip((image*(2.**brightness)-.18)*contrast+.18,0,1)
    image[~valid] = 0
    return image


def fit_crop_ratio(bounds, ratio):
    """Center the largest exact integer-ratio rectangle inside pixel bounds."""
    from math import gcd
    x0, y0, x1, y1 = map(int, bounds)
    if x1 <= x0 or y1 <= y0:
        raise ValueError('Crop must have positive width and height.')
    if ratio is None:
        return x0, y0, x1, y1
    rw, rh = map(int, ratio)
    if rw <= 0 or rh <= 0:
        raise ValueError('Crop ratio must be positive.')
    factor = gcd(rw, rh); rw //= factor; rh //= factor
    multiple = min((x1-x0)//rw, (y1-y0)//rh)
    if multiple < 1:
        raise ValueError('Selection is too small for this pixel ratio.')
    width, height = rw*multiple, rh*multiple
    left, top = x0+((x1-x0)-width)//2, y0+((y1-y0)-height)//2
    return left, top, left+width, top+height


def resize_crop(bounds, edges, point, image_size, ratio=None):
    """Resize a crop, keeping opposite edges fixed and optional ratio exact."""
    from math import gcd
    x0,y0,x1,y1=map(int,bounds);px,py=map(int,point);w,h=map(int,image_size)
    if ratio is None:
        if 'l' in edges:x0=max(0,min(px,x1-1))
        if 'r' in edges:x1=min(w,max(px,x0+1))
        if 't' in edges:y0=max(0,min(py,y1-1))
        if 'b' in edges:y1=min(h,max(py,y0+1))
        return x0,y0,x1,y1
    rw,rh=map(int,ratio);divisor=gcd(rw,rh);rw//=divisor;rh//=divisor
    horizontal='l' in edges or 'r' in edges;vertical='t' in edges or 'b' in edges
    ax=x1 if 'l' in edges else x0
    ay=y1 if 't' in edges else y0
    if horizontal and vertical:
        available_x=ax if 'l' in edges else w-ax
        available_y=ay if 't' in edges else h-ay
        maximum=min(available_x//rw,available_y//rh)
        wanted=min(round(abs(px-ax)/rw),round(abs(py-ay)/rh))
    elif horizontal:
        cy=(y0+y1)/2
        maximum=min((ax if 'l' in edges else w-ax)//rw,int(2*min(cy,h-cy)//rh))
        wanted=round(abs(px-ax)/rw)
    else:
        cx=(x0+x1)/2
        maximum=min((ay if 't' in edges else h-ay)//rh,int(2*min(cx,w-cx)//rw))
        wanted=round(abs(py-ay)/rh)
    if maximum<1:return bounds
    k=max(1,min(maximum,wanted));width,height=k*rw,k*rh
    if horizontal:
        left=ax-width if 'l' in edges else ax
    else:left=round((x0+x1-width)/2)
    if vertical:
        top=ay-height if 't' in edges else ay
    else:top=round((y0+y1-height)/2)
    left=max(0,min(w-width,left));top=max(0,min(h-height,top))
    return left,top,left+width,top+height


def crop_image(linear, header, left=0, right=0, top=0, bottom=0):
    """Crop RGB pixels and shift FITS WCS reference pixels without resampling."""
    h, w, _ = linear.shape
    margins = (left, right, top, bottom)
    if any(not isinstance(v, (int, np.integer)) or v < 0 for v in margins):
        raise ValueError('Crop margins must be nonnegative whole pixels.')
    if left+right >= w or top+bottom >= h:
        raise ValueError('Crop must leave at least one pixel in each dimension.')
    cropped = linear[top:h-bottom, left:w-right]
    hdr = header.copy()
    # Alternate WCS versions use letter suffixes. SIP offsets share CRPIX.
    for suffix in ['', *'ABCDEFGHIJKLMNOPQRSTUVWXYZ']:
        for axis, shift in ((1, left), (2, top)):
            key = f'CRPIX{axis}{suffix}'
            if key in hdr:
                hdr[key] = float(hdr[key])-shift
    hdr['IMAGEW'] = cropped.shape[1]
    hdr['IMAGEH'] = cropped.shape[0]
    hdr.add_history(f'Crop: left={left}, right={right}, top={top}, bottom={bottom} pixels.')
    return cropped, hdr


def export_basename(header, fallback='image'):
    """Use the target name as a safe Windows filename, without an extension."""
    import re
    name = str(header.get('OBJECT', '')).strip() or str(fallback).strip() or 'image'
    # Normalize common catalogue names: C 56 -> C56, NGC 7000 -> NGC7000.
    name = re.sub(r'^([A-Za-z]+)\s+(\d+[A-Za-z]?)$', r'\1\2', name)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'\s+', '_', name).strip(' .')[:100].rstrip(' .') or 'image'
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        name = 'Object_'+name
    return name


def save(path, linear, rendered, header):
    suffix = Path(path).suffix.lower()
    if suffix in ('.fit', '.fits'):
        hdr = header.copy()
        for key in ('BAYERPAT', 'XBAYROFF', 'YBAYROFF'):
            hdr.remove(key, ignore_missing=True, remove_all=True)
        hdr.add_history('Saved linear RGB; axis 3 is R,G,B. Display adjustments not applied.')
        fits.writeto(path, np.moveaxis(linear, -1, 0), hdr, overwrite=True)
    elif suffix in ('.tif', '.tiff'):
        tifffile.imwrite(path, np.round(rendered*65535).astype(np.uint16), photometric='rgb')
    elif suffix in ('.jpg', '.jpeg'):
        Image.fromarray(np.round(rendered*255).astype(np.uint8)).save(path,quality=95,subsampling=0,progressive=True)
    elif suffix == '.png':
        Image.fromarray(np.round(rendered*255).astype(np.uint8)).save(path)
    else:
        raise ValueError('Choose .fits, .tif, .tiff, .png, .jpg or .jpeg.')
