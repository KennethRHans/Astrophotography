"""Compile the small Metal bridge using Apple's SDK; no GPU needed to compile."""
from pathlib import Path
import subprocess
import sys


def build():
    if sys.platform != 'darwin':
        raise SystemExit('The Metal bridge requires macOS and Xcode command line tools.')
    root = Path(__file__).resolve().parents[1]
    target = root / 'build/metal/libEasyAstroMetal.dylib'
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['xcrun', 'clang', '-dynamiclib', '-fobjc-arc', '-O2',
                    '-mmacosx-version-min=12.0', '-framework', 'Foundation',
                    '-framework', 'Metal', str(root / 'macos/metal_bridge.m'),
                    '-o', str(target)], check=True)
    return target


if __name__ == '__main__':
    print(build())
