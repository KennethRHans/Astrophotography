"""macOS container storage and coordinated atomic project replacement.

Native Cocoa panels retain security-scoped URLs for the current session. Projects embed
their image; source paths in their manifest never serve as persistent grants.
"""
from contextlib import contextmanager
from pathlib import Path
import shutil
import sys
import tempfile


class FileAccess:
    """Keep selected URLs alive until workers and repeated saves are finished."""
    def __init__(self):
        self.urls = {}

    def retain(self, url):
        path = str(url.path())
        if path not in self.urls:
            active = bool(url.startAccessingSecurityScopedResource())
            # A false result can mean the URL is already implicitly accessible
            # (for example, a file inside the container). Retain either way.
            self.urls[path] = (url, active)
        return path

    def close(self):
        for url, active in self.urls.values():
            if active:
                url.stopAccessingSecurityScopedResource()
        self.urls.clear()


file_access = FileAccess()


def select_files(title, extensions, multiple=False):
    """Use original NSURLs from NSOpenPanel, not URLs recreated from paths.

    Qt's file engine can manage its own sandbox access, but Python/Astropy
    reads bypass that engine. Explicit scopes must outlive the panel and the
    asynchronous stacking/project workers.
    """
    from AppKit import NSOpenPanel, NSModalResponseOK
    panel = NSOpenPanel.openPanel()
    panel.setTitle_(title)
    panel.setCanChooseFiles_(True)
    panel.setCanChooseDirectories_(False)
    panel.setAllowsMultipleSelection_(multiple)
    panel.setAllowedFileTypes_(extensions)
    if panel.runModal() != NSModalResponseOK:
        return []
    return [file_access.retain(url) for url in panel.URLs()]


def select_save_file(title, default_name, extensions):
    from AppKit import NSSavePanel, NSModalResponseOK
    panel = NSSavePanel.savePanel()
    panel.setTitle_(title)
    panel.setNameFieldStringValue_(default_name)
    panel.setAllowedFileTypes_(extensions)
    panel.setAllowsOtherFileTypes_(False)
    panel.setCanCreateDirectories_(True)
    panel.setExtensionHidden_(False)
    if panel.runModal() != NSModalResponseOK:
        return ''
    return file_access.retain(panel.URL())


def sandboxed():
    if sys.platform != 'darwin':
        return False
    from Foundation import NSHomeDirectory
    return '/Library/Containers/' in str(NSHomeDirectory())


def configure_storage():
    if sys.platform == 'darwin':
        from Foundation import NSTemporaryDirectory
        # Foundation resolves the app's permitted temporary directory even when
        # a shell launching the executable inherited a different TMPDIR.
        tempfile.tempdir = str(NSTemporaryDirectory())


@contextmanager
def coordinated_destination(path):
    """Stage on the destination volume, then atomically replace via Foundation.

    NSItemReplacementDirectory avoids requesting permission for arbitrary
    siblings of the file selected in the save panel. Never truncate the target
    as a fallback: a failed write must preserve the previous project.
    """
    from Foundation import (NSURL, NSFileManager, NSFileCoordinator,
                            NSItemReplacementDirectory, NSUserDomainMask,
                            NSFileCoordinatorWritingForReplacing)
    manager = NSFileManager.defaultManager()
    url = NSURL.fileURLWithPath_(str(Path(path).absolute()))
    directory, error = manager.URLForDirectory_inDomain_appropriateForURL_create_error_(
        NSItemReplacementDirectory, NSUserDomainMask, url, True, None)
    if directory is None:
        raise OSError(f'Cannot stage project save: {error}')
    folder = Path(str(directory.path()))
    staged = folder / 'project.astro'
    try:
        yield staged
        failures = []
        completed = []

        def replace(coordinated_url):
            # Exceptions must not escape a Python callback into Objective-C.
            try:
                source = NSURL.fileURLWithPath_(str(staged))
                if manager.fileExistsAtPath_(coordinated_url.path()):
                    ok, resulting_url, failure = manager.replaceItemAtURL_withItemAtURL_backupItemName_options_resultingItemURL_error_(
                        coordinated_url, source, None, 0, None, None)
                else:
                    ok, failure = manager.moveItemAtURL_toURL_error_(source, coordinated_url, None)
                if not ok:
                    raise OSError(f'Cannot commit project save: {failure}')
                completed.append(True)
            except Exception as exc:
                failures.append(exc)

        coordinator = NSFileCoordinator.alloc().initWithFilePresenter_(None)
        error = coordinator.coordinateWritingItemAtURL_options_error_byAccessor_(
            url, NSFileCoordinatorWritingForReplacing, None, replace)
        if failures:
            raise failures[0]
        if error is not None or not completed:
            raise OSError(f'Cannot coordinate project save: {error}')
    finally:
        shutil.rmtree(folder)
