"""Prepare native icon resources and the installed dependency license inventory."""
from pathlib import Path
import subprocess
from prepare_msix import collect_licenses


def prepare(root):
    target=root/'work/macos-release-assets';target.mkdir(parents=True,exist_ok=True)
    notices=target/'ThirdPartyNotices'
    if notices.exists():
        import shutil
        shutil.rmtree(notices)
    collect_licenses(notices)
    iconset=target/'EasyAstroStudio.iconset';iconset.mkdir(exist_ok=True)
    logo=root/'assets/easy-astro-logo.png'
    for size in (16,32,128,256,512):
        for scale in (1,2):
            name=f'icon_{size}x{size}'+('@2x' if scale==2 else '')+'.png'
            subprocess.run(['sips','--resampleHeightWidth',str(size*scale),str(size*scale),str(logo),'--out',str(iconset/name)],check=True,capture_output=True)
    icon=target/'EasyAstroStudio.icns'
    subprocess.run(['iconutil','--convert','icns',str(iconset),'--output',str(icon)],check=True)
    return icon,notices
