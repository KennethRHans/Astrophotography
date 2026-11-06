"""Restore the existing Qt window when macOS sends a Dock reopen event."""
import sys
from PySide6 import QtCore

_handler_class = None
CORE_EVENTS = int.from_bytes(b'aevt', 'big')
REOPEN_APPLICATION = int.from_bytes(b'rapp', 'big')


def restore_window(window):
    # Preserve maximized/full-screen state, the loaded project and all workers.
    window.setWindowState(window.windowState() & ~QtCore.Qt.WindowMinimized)
    window.show()
    window.raise_()
    window.activateWindow()


def install_reopen_handler(app, window):
    if sys.platform != 'darwin':
        return None
    import objc
    from Foundation import NSAppleEventManager, NSObject
    global _handler_class
    if _handler_class is None:
        class EasyAstroDockReopenHandler(NSObject):
            @objc.typedSelector(b'v@:@@')
            def handleReopen_withReplyEvent_(self, event, reply):
                # Apple events arrive on the main thread. Queue restoration
                # through Qt so its window state stays synchronized with Cocoa.
                QtCore.QTimer.singleShot(0, self.restore)
        _handler_class = EasyAstroDockReopenHandler
    handler = _handler_class.alloc().init()
    handler.restore = lambda: restore_window(window)
    manager = NSAppleEventManager.sharedAppleEventManager()
    # Handle only the standard reopen event; leave Qt's app delegate and other
    # Apple-event handlers (quit, file opening, etc.) intact.
    manager.setEventHandler_andSelector_forEventClass_andEventID_(
        handler, 'handleReopen:withReplyEvent:', CORE_EVENTS, REOPEN_APPLICATION)
    app.aboutToQuit.connect(lambda: manager.removeEventHandlerForEventClass_andEventID_(
        CORE_EVENTS, REOPEN_APPLICATION))
    # Keep the Python-backed Objective-C handler alive for the app's lifetime.
    app._mac_reopen_handler = handler
    return handler
