"""macOS container storage and coordinated atomic project replacement.

Native Qt open/save panels grant access for the current session. Projects embed
their image; source paths in their manifest never serve as persistent grants.
"""
from contextlib import contextmanager
from pathlib import Path
import shutil
import sys
import tempfile


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
