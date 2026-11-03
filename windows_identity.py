"""Preserve the Store-assigned taskbar identity when running inside MSIX."""
import sys


def has_package_identity():
    if sys.platform != 'win32':return False
    import ctypes
    from ctypes import wintypes
    try:
        get_name=ctypes.windll.kernel32.GetCurrentPackageFullName
        get_name.argtypes=[ctypes.POINTER(wintypes.UINT),wintypes.LPWSTR]
        get_name.restype=wintypes.LONG
        size=wintypes.UINT(0)
        return get_name(ctypes.byref(size),None) in (0,122)
    except (AttributeError,OSError):return False


def configure_taskbar_identity():
    if sys.platform=='win32' and not has_package_identity():
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('EasyAstroStudio.Desktop')
