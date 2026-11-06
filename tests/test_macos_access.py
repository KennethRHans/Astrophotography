from concurrent.futures import ThreadPoolExecutor
import sys
from types import SimpleNamespace

from macos_access import FileAccess
import macos_access
import pytest


class ScopedURL:
    def __init__(self, path, scoped=True):
        self.value = path
        self.scoped = scoped
        self.starts = self.stops = 0

    def path(self):
        return self.value

    def startAccessingSecurityScopedResource(self):
        self.starts += 1
        return self.scoped

    def stopAccessingSecurityScopedResource(self):
        self.stops += 1

    def worker_read(self):
        assert self.starts == 1 and self.stops == 0
        return 'FITS pixels'


def test_panel_access_survives_selection_and_worker_reads(monkeypatch):
    access = FileAccess()
    url = ScopedURL('/selected/light.fit')
    class Panel:
        def setTitle_(self, value): pass
        def setCanChooseFiles_(self, value): pass
        def setCanChooseDirectories_(self, value): pass
        def setAllowsMultipleSelection_(self, value): pass
        def setAllowedFileTypes_(self, value): pass
        def runModal(self): return 1
        def URLs(self): return [url]
    monkeypatch.setitem(sys.modules, 'AppKit', SimpleNamespace(
        NSOpenPanel=SimpleNamespace(openPanel=lambda: Panel()), NSModalResponseOK=1))
    monkeypatch.setattr(macos_access, 'file_access', access)
    assert macos_access.select_files('Exposures', ['fit'], True) == ['/selected/light.fit']
    # Re-selecting the same file must not acquire an unmatched second scope.
    macos_access.select_files('Exposures', ['fit'], True)
    with ThreadPoolExecutor() as workers:
        assert workers.submit(url.worker_read).result() == 'FITS pixels'
    access.close()
    access.close()
    assert url.starts == 1 and url.stops == 1


def test_implicit_access_does_not_stop_an_unacquired_scope():
    access = FileAccess()
    url = ScopedURL('/container/image.fit', scoped=False)
    access.retain(url)
    access.close()
    assert url.stops == 0


@pytest.mark.skipif(sys.platform != 'darwin', reason='Native Cocoa export panel')
@pytest.mark.parametrize('index,extension,format_name', [
    (0, '.tif', 'TIFF'), (1, '.png', 'PNG'),
    (2, '.jpg', 'JPEG'), (3, '.fits', 'FITS'),
])
def test_native_export_selector_changes_extension_and_encoder(tmp_path, index, extension, format_name):
    from AppKit import NSApplication
    from PIL import Image
    from astropy.io import fits
    import numpy as np
    import engine
    native = NSApplication.sharedApplication()
    panel, controller, popup = macos_access.export_panel('C56.tif')
    assert popup.numberOfItems() == 4
    assert panel.accessoryView() is not None
    popup.selectItemAtIndex_(index)
    assert native.sendAction_to_from_('formatChanged:', controller, popup)
    assert str(panel.nameFieldStringValue()) == 'C56' + extension
    assert list(panel.allowedFileTypes()) == list(macos_access.EXPORT_FORMATS[index][1])
    target = tmp_path / str(panel.nameFieldStringValue())
    pixels = np.ones((30, 40, 3), dtype='float32') * .5
    engine.save(target, pixels, pixels, fits.Header())
    if format_name == 'FITS':
        with fits.open(target) as hdus:
            np.testing.assert_array_equal(hdus[0].data, np.moveaxis(pixels, -1, 0))
    else:
        with Image.open(target) as exported:
            assert exported.format == format_name
