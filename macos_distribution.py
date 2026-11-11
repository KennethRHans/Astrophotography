"""Read the distribution marker from a frozen Mac bundle, never a user preference."""
from pathlib import Path
import plistlib
import sys


def app_store_build():
    if sys.platform != 'darwin' or not getattr(sys,'frozen',False):return False
    try:
        with (Path(sys.executable).parent.parent/'Info.plist').open('rb') as stream:
            return plistlib.load(stream).get('EASMacAppStoreBuild') is True
    except (OSError,ValueError,plistlib.InvalidFileException):return False
