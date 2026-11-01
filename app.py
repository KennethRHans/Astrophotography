import sys
from pathlib import Path
import numpy as np
import cv2
from PySide6 import QtCore, QtGui, QtWidgets as W
import engine

class Worker(QtCore.QThread):
    message = QtCore.Signal(str)
    result = QtCore.Signal(object, object)
    failed = QtCore.Signal(str)
    def __init__(self, paths, bayer, single=False):
        super().__init__()
        self.paths, self.bayer, self.single = paths, bayer, single
    def run(self):
        try:
            result = engine.read_fits(self.paths[0], self.bayer) if self.single else engine.stack(self.paths, self.bayer, self.message.emit, self.isInterruptionRequested)
            self.result.emit(*result)
        except Exception as exc:
            self.failed.emit(str(exc))

class Window(W.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Seestar Studio • Preview 0.2')
        self.resize(1200, 800)
        self.linear = self.header = self.rendered = None
        self.worker = None
        root = W.QWidget(); self.setCentralWidget(root)
        layout = W.QHBoxLayout(root)
        controls = W.QWidget()
        sidebar = W.QVBoxLayout(controls)
        scroll = W.QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(controls)
        scroll.setMinimumWidth(340); layout.addWidget(scroll, 1)
        title = W.QLabel('Seestar Studio'); title.setStyleSheet('font-size:26px; font-weight:bold'); sidebar.addWidget(title)
        intro = W.QLabel('1. Add individual exposures to stack,\nor open an existing FITS stack.\n2. Adjust the preview.\n3. Export your image.'); sidebar.addWidget(intro)
        self.add = W.QPushButton('Add exposures…'); self.add.clicked.connect(self.add_files); sidebar.addWidget(self.add)
        self.files = W.QListWidget(); self.files.setSelectionMode(W.QAbstractItemView.ExtendedSelection); sidebar.addWidget(self.files)
        self.remove = W.QPushButton('Remove selected'); self.remove.clicked.connect(self.remove_files); sidebar.addWidget(self.remove)
        sidebar.addWidget(W.QLabel('Bayer pattern (for 2D files only)'))
        self.bayer = W.QComboBox(); self.bayer.addItems(['Auto', 'RGGB', 'BGGR', 'GRBG', 'GBRG', 'None']); sidebar.addWidget(self.bayer)
        note = W.QLabel('Auto uses BAYERPAT. Missing header → grayscale.\nUse None for an already debayered 2D image.\nDo not mix targets, sizes, or exposure settings.'); note.setWordWrap(True); sidebar.addWidget(note)
        self.run = W.QPushButton('Align and stack exposures'); self.run.clicked.connect(lambda: self.start(False)); sidebar.addWidget(self.run)
        self.open = W.QPushButton('Open existing FITS stack…'); self.open.clicked.connect(lambda: self.start(True)); sidebar.addWidget(self.open)
        self.cancel = W.QPushButton('Cancel'); self.cancel.clicked.connect(lambda: self.worker.requestInterruption() if self.worker else None); self.cancel.setEnabled(False); sidebar.addWidget(self.cancel)
        self.sliders = {}
        for label, low, high, default in [('Stretch', 0, 100, 30), ('Black percentile ×100', 0, 100, 10), ('Saturation %', 0, 200, 100), ('Noise smoothing ×100', 0, 150, 0), ('Background correction %', 0, 100, 0), ('Red balance %', 50, 200, 100), ('Green balance %', 50, 200, 100), ('Blue balance %', 50, 200, 100)]:
            sidebar.addWidget(W.QLabel(label))
            slider = W.QSlider(QtCore.Qt.Horizontal); slider.setRange(low, high); slider.setValue(default); sidebar.addWidget(slider); self.sliders[label] = slider
            slider.valueChanged.connect(self.schedule_preview)
            value = W.QLabel(str(default)); sidebar.addWidget(value)
            slider.valueChanged.connect(lambda n, widget=value: widget.setText(str(n)))
        hint = W.QLabel('Background correction can remove faint extended nebulosity.\nStart low and compare. Color balance is manual.'); hint.setWordWrap(True); sidebar.addWidget(hint)
        self.baseline = W.QCheckBox('Compare: default stretch'); self.baseline.toggled.connect(self.schedule_preview); sidebar.addWidget(self.baseline)
        self.export = W.QPushButton('Export FITS / 16-bit TIFF / PNG…'); self.export.setEnabled(False); self.export.clicked.connect(self.save); sidebar.addWidget(self.export)
        right = W.QVBoxLayout(); layout.addLayout(right, 3)
        self.preview = W.QLabel('Your image will appear here'); self.preview.setAlignment(QtCore.Qt.AlignCenter); self.preview.setMinimumSize(400, 300); self.preview.setStyleSheet('background:#080e18;color:#a6b7cc'); right.addWidget(self.preview, 4)
        self.log = W.QPlainTextEdit(); self.log.setReadOnly(True); right.addWidget(self.log, 1)
        self.timer = QtCore.QTimer(); self.timer.setSingleShot(True); self.timer.timeout.connect(self.update_preview)
        self.statusBar().showMessage('Ready • CPU processing • Originals are preserved')
    def add_files(self):
        paths, _ = W.QFileDialog.getOpenFileNames(self, 'Select individual exposures', '', 'FITS (*.fit *.fits *.FIT *.FITS)')
        existing = {self.files.item(i).text() for i in range(self.files.count())}
        self.files.addItems([p for p in paths if p not in existing])
    def remove_files(self):
        for item in self.files.selectedItems(): self.files.takeItem(self.files.row(item))
    def start(self, single):
        if single:
            path, _ = W.QFileDialog.getOpenFileName(self, 'Open a finished stack', '', 'FITS (*.fit *.fits *.FIT *.FITS)')
            if not path: return
            paths = [path]
        else:
            paths = [self.files.item(i).text() for i in range(self.files.count())]
            if len(paths) < 2:
                W.QMessageBox.information(self, 'Add exposures', 'Add at least two individual exposures.'); return
        self.log.appendPlainText('Starting. Alignment uses the first listed exposure as reference.\nTemporary disk space needed: approximately 12 bytes × pixels × frames.')
        for control in (self.run, self.open, self.add, self.remove, self.bayer): control.setEnabled(False)
        self.cancel.setEnabled(True)
        self.worker = Worker(paths, self.bayer.currentText(), single)
        self.worker.message.connect(self.log.appendPlainText)
        self.worker.result.connect(self.loaded)
        self.worker.failed.connect(lambda text: self.log.appendPlainText('Stopped: '+text))
        self.worker.finished.connect(self.finished)
        self.worker.start()
    def finished(self):
        for control in (self.run, self.open, self.add, self.remove, self.bayer): control.setEnabled(True)
        self.cancel.setEnabled(False)
        self.worker.deleteLater(); self.worker = None
    def loaded(self, linear, header):
        self.linear, self.header = linear, header
        self.background = engine.background_model(linear)
        self.export.setEnabled(True)
        self.log.appendPlainText(engine.image_summary(linear, header))
        self.update_preview()
    def schedule_preview(self): self.timer.start(150)
    def settings(self):
        values = [s.value() for s in self.sliders.values()]
        return (30, .1, 1, 0, 0, (1, 1, 1)) if self.baseline.isChecked() else (values[0], values[1]/100, values[2]/100, values[3]/100, values[4]/100, tuple(v/100 for v in values[5:8]))
    def update_preview(self):
        if self.linear is None: return
        # Interactive display is reduced; export always renders at native resolution.
        step = max(1, int(np.ceil(max(self.linear.shape[:2])/1400)))
        small = cv2.resize(self.linear, (max(1, self.linear.shape[1]//step), max(1, self.linear.shape[0]//step)), interpolation=cv2.INTER_AREA)
        preview = engine.render(small, *self.settings(), model=self.background)
        pixels = np.ascontiguousarray(np.round(preview*255).astype(np.uint8))
        image = QtGui.QImage(pixels.data, pixels.shape[1], pixels.shape[0], pixels.strides[0], QtGui.QImage.Format_RGB888).copy()
        self.pixmap = QtGui.QPixmap.fromImage(image)
        self.preview.setPixmap(self.pixmap.scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'pixmap'): self.preview.setPixmap(self.pixmap.scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
    def save(self):
        path, _ = W.QFileDialog.getSaveFileName(self, 'Export (FITS saves linear data)', 'image.tif', '16-bit TIFF (*.tif);;PNG (*.png);;Linear FITS (*.fits)')
        if not path: return
        try:
            engine.save(path, self.linear, engine.render(self.linear, *self.settings(), model=self.background), self.header)
            self.log.appendPlainText('Saved '+path)
        except Exception as exc: W.QMessageBox.critical(self, 'Export failed', str(exc))
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.log.appendPlainText('Cancelling. Close again after processing stops.')
            event.ignore()
        else: event.accept()

if __name__ == '__main__':
    app = W.QApplication(sys.argv)
    app.setStyle('Fusion')
    window = Window(); window.show()
    if '--smoke-test' in sys.argv:
        from astropy.io import fits
        sample = np.ones((60, 80, 3), dtype=np.float32)*100
        sample[20:30, 20:30] = 500
        window.loaded(sample, fits.Header())
        window.sliders['Background correction %'].setValue(50)
        window.update_preview()
        app.processEvents()
        window.close()
        sys.exit(0)
    sys.exit(app.exec())
