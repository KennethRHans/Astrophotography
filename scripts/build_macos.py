"""Build an unsigned, CPU-only macOS preview on a Mac."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    if sys.platform != 'darwin':
        raise SystemExit('Build on macOS; cross-compiling from Windows/Linux is unsupported.')
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    from app_version import VERSION
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--windowed', '--name', 'EasyAstroStudio',
        '--osx-bundle-identifier', 'com.astrivanta.easyastrostudio',
        '--add-data', 'assets:assets', '--hidden-import', 'sep',
        '--collect-submodules', 'skimage.transform',
        '--exclude-module', 'pyopencl', '--exclude-module', 'pytest',
        'app.py',
    ], check=True)
    # PyInstaller's default version is 0.0.0; keep the bundle in sync.
    import plistlib
    plist = root / 'dist/EasyAstroStudio.app/Contents/Info.plist'
    with plist.open('rb') as stream:
        info = plistlib.load(stream)
    info.update(CFBundleShortVersionString=VERSION, CFBundleVersion=VERSION,
                NSHighResolutionCapable=True)
    with plist.open('wb') as stream:
        plistlib.dump(info, stream)
    # Refresh the development signature after editing the bundle metadata.
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-',
                    str(plist.parents[1])], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict',
                    str(plist.parents[1])], check=True)


if __name__ == '__main__':
    main()
