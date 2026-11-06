from concurrent.futures import ThreadPoolExecutor
import sys
from types import SimpleNamespace

from macos_access import FileAccess
import macos_access


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
