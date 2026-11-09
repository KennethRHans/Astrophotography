"""Bundled privacy policy, available without network access."""
import sys
from pathlib import Path
from PySide6 import QtCore,QtGui,QtWidgets as W


class PrivacyDialog(W.QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('Easy Astro Studio — Privacy Policy');self.resize(760,700)
        layout=W.QVBoxLayout(self);self.browser=W.QTextBrowser();self.browser.setOpenExternalLinks(False);self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(lambda url:QtGui.QDesktopServices.openUrl(url) if url.scheme() in ('https','mailto') else None)
        path=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'/'privacy_policy.md'
        try:self.policy_text=path.read_text(encoding='utf-8')
        except OSError:self.policy_text='Privacy policy could not be loaded. Please contact starsandfits@gmail.com.'
        self.browser.setMarkdown(self.policy_text);layout.addWidget(self.browser)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.Close);buttons.rejected.connect(self.reject);layout.addWidget(buttons)


def show_privacy(parent=None):
    dialog=PrivacyDialog(parent)
    try:dialog.exec()
    finally:dialog.deleteLater()
