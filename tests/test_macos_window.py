import sys
import numpy as np
import pytest
from astropy.io import fits
from PySide6 import QtCore, QtWidgets
from app import Window
from macos_window import restore_window, install_reopen_handler


def test_restore_existing_window_preserves_unsaved_edits():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = Window(ask_on_close=False)
    pixels = np.ones((30, 40, 3), dtype='float32') * 100
    window.loaded(pixels, fits.Header())
    window.sliders['Stretch'].setValue(60)
    window.commit_history()
    state = window.edit_state()
    window.showMinimized()
    app.processEvents()
    assert window.isMinimized()
    restore_window(window)
    app.processEvents()
    assert not window.isMinimized() and window.isVisible()
    np.testing.assert_array_equal(window.linear, pixels)
    assert window.edit_state() == state and window._dirty
    window.hide()
    restore_window(window)
    assert window.isVisible()
    window.close()


@pytest.mark.skipif(sys.platform != 'darwin', reason='Native macOS Apple event handler')
def test_native_reopen_handler_restores_minimized_window():
    from AppKit import NSApplication
    NSApplication.sharedApplication()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = Window(ask_on_close=False)
    handler = install_reopen_handler(app, window)
    window.showMinimized()
    app.processEvents()
    handler.handleReopen_withReplyEvent_(None, None)
    QtCore.QCoreApplication.sendPostedEvents()
    app.processEvents()
    assert window.isVisible() and not window.isMinimized()
    window.close()
