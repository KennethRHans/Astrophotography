"""Build an ad hoc signed macOS preview with optional Metal adjustments."""
import os
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sandbox', action='store_true', help='Enable App Sandbox for development testing')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        raise SystemExit('Build on macOS; cross-compiling from Windows/Linux is unsupported.')
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    from app_version import APPLE_VERSION as VERSION
    from build_metal import build
    metal_library = build()
    from macos_release_assets import prepare
    icon, notices = prepare(root)
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--windowed', '--name', 'EasyAstroStudio',
        '--icon', str(icon), '--add-data', str(notices)+':ThirdPartyNotices',
        '--osx-bundle-identifier', 'com.astrivanta.easyastrostudio',
        '--add-data', 'assets:assets', '--hidden-import', 'sep',
        '--add-data', 'macos/adjustments.metal:macos',
        '--add-binary', str(metal_library)+':.',
        '--collect-submodules', 'skimage.transform', '--collect-data', 'certifi',
        '--exclude-module', 'pyopencl', '--exclude-module', 'pytest',
        'app.py',
    ], check=True)
    # PyInstaller's default version is 0.0.0; keep the bundle in sync.
    import plistlib
    plist = root / 'dist/EasyAstroStudio.app/Contents/Info.plist'
    with plist.open('rb') as stream:
        info = plistlib.load(stream)
    info.update(CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION,
                NSHighResolutionCapable=True, LSApplicationCategoryType='public.app-category.photography')
    with plist.open('wb') as stream:
        plistlib.dump(info, stream)
    # Refresh the development signature after editing the bundle metadata.
    signing = ['codesign', '--force', '--sign', '-']
    if args.sandbox:
        signing += ['--entitlements', str(root / 'macos/sandbox.entitlements')]
    subprocess.run(signing + [str(plist.parents[1])], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict',
                    str(plist.parents[1])], check=True)


if __name__ == '__main__':
    main()
