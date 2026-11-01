import sys
from pathlib import Path
import numpy as np
import cv2
from PySide6 import QtCore, QtGui, QtWidgets as W
import engine

class CropPreview(W.QLabel):
    selection = QtCore.Signal(int, int, int, int)
    def __init__(self, text):
        super().__init__(text)
        self.source_size = None
        self.drag_start = None
        self.band = W.QRubberBand(W.QRubberBand.Rectangle, self)
        self.setCursor(QtCore.Qt.CrossCursor)
    def image_rect(self):
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return QtCore.QRect()
        return QtCore.QRect((self.width()-pixmap.width())//2,
                            (self.height()-pixmap.height())//2,
                            pixmap.width(), pixmap.height())
    def mousePressEvent(self, event):
        point = event.position().toPoint()
        if event.button() == QtCore.Qt.LeftButton and self.source_size and self.image_rect().contains(point):
            self.drag_start = point
            self.band.setGeometry(QtCore.QRect(point, QtCore.QSize()))
            self.band.show()
    def mouseMoveEvent(self, event):
        if self.drag_start is not None:
            self.band.setGeometry(QtCore.QRect(self.drag_start, event.position().toPoint()).normalized().intersected(self.image_rect()))
    def mouseReleaseEvent(self, event):
        if self.drag_start is None or event.button() != QtCore.Qt.LeftButton:
            return
        rect = QtCore.QRect(self.drag_start, event.position().toPoint()).normalized().intersected(self.image_rect())
        self.drag_start = None
        if rect.width() < 3 or rect.height() < 3:
            self.band.hide()
            return
        bounds = self.image_rect()
        w, h = self.source_size
        x0 = max(0, int(np.floor((rect.x()-bounds.x())*w/bounds.width())))
        y0 = max(0, int(np.floor((rect.y()-bounds.y())*h/bounds.height())))
        x1 = min(w, int(np.ceil((rect.x()+rect.width()-bounds.x())*w/bounds.width())))
        y1 = min(h, int(np.ceil((rect.y()+rect.height()-bounds.y())*h/bounds.height())))
        self.selection.emit(x0, y0, x1, y1)


class Worker(QtCore.QThread):
    message = QtCore.Signal(str)
    result = QtCore.Signal(object, object)
    progress = QtCore.Signal(int, int, str)
    failed = QtCore.Signal(str)
    def __init__(self, paths, bayer, single=False):
        super().__init__()
        self.paths, self.bayer, self.single = paths, bayer, single
    def run(self):
        try:
            result = engine.read_fits(self.paths[0], self.bayer) if self.single else engine.stack(self.paths, self.bayer, self.message.emit, self.isInterruptionRequested, self.progress.emit)
            self.result.emit(*result)
        except Exception as exc:
            self.failed.emit(str(exc))

class Window(W.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Seestar Studio • Preview 0.4')
        self.resize(1200, 800)
        self.linear = self.header = self.rendered = None
        self.worker = None
        self.gpu = None
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
        self.slider_defaults = {}
        for label, low, high, default in [('Stretch', 0, 100, 30), ('Black percentile ×100', 0, 100, 10), ('Saturation %', 0, 200, 100), ('Noise smoothing ×100', 0, 150, 0), ('Background correction %', 0, 100, 0), ('Red balance %', 50, 200, 100), ('Green balance %', 50, 200, 100), ('Blue balance %', 50, 200, 100)]:
            sidebar.addWidget(W.QLabel(label))
            slider = W.QSlider(QtCore.Qt.Horizontal); slider.setRange(low, high); slider.setValue(default); sidebar.addWidget(slider); self.sliders[label] = slider
            self.slider_defaults[label] = default
            slider.valueChanged.connect(self.schedule_preview)
            value = W.QLabel(str(default)); sidebar.addWidget(value)
            slider.valueChanged.connect(lambda n, widget=value: widget.setText(str(n)))
        hint = W.QLabel('Background correction can remove faint extended nebulosity.\nStart low and compare. Color balance is manual.'); hint.setWordWrap(True); sidebar.addWidget(hint)
        self.baseline = W.QCheckBox('Compare: default stretch'); self.baseline.toggled.connect(self.schedule_preview); sidebar.addWidget(self.baseline)
        self.reset = W.QPushButton('Reset adjustments')
        self.reset.setToolTip('Restore all sliders to their starting values')
        self.reset.clicked.connect(self.reset_adjustments)
        sidebar.addWidget(self.reset)
        self.use_gpu = W.QCheckBox('Use GPU for adjustments (experimental)')
        self.use_gpu.setToolTip('Accelerates stretch, saturation and smoothing. Alignment and stacking use CPU.')
        self.use_gpu.toggled.connect(self.toggle_gpu); sidebar.addWidget(self.use_gpu)
        self.crop_group = W.QGroupBox('Crop — drag on the image or trim edges')
        crop_layout = W.QFormLayout(self.crop_group)
        self.crop_margins = {}
        for edge in ('Left', 'Right', 'Top', 'Bottom'):
            spin = W.QSpinBox(); spin.setRange(0, 0); spin.setSuffix(' px')
            crop_layout.addRow(edge, spin); self.crop_margins[edge] = spin
        self.apply_crop = W.QPushButton('Apply crop'); self.apply_crop.clicked.connect(self.crop_selected)
        self.restore_crop = W.QPushButton('Restore full frame'); self.restore_crop.clicked.connect(self.restore_full_frame)
        crop_layout.addRow(self.apply_crop); crop_layout.addRow(self.restore_crop)
        self.crop_group.setEnabled(False); sidebar.addWidget(self.crop_group)
        self.export = W.QPushButton('Export FITS / 16-bit TIFF / PNG…'); self.export.setEnabled(False); self.export.clicked.connect(self.save); sidebar.addWidget(self.export)
        right = W.QVBoxLayout(); layout.addLayout(right, 3)
        self.preview = CropPreview('Your image will appear here'); self.preview.setAlignment(QtCore.Qt.AlignCenter); self.preview.setMinimumSize(400, 300); self.preview.setStyleSheet('background:#080e18;color:#a6b7cc'); right.addWidget(self.preview, 4)
        self.preview.selection.connect(self.select_crop)
        self.progress_text = W.QLabel('Ready'); right.addWidget(self.progress_text)
        self.progress_bar = W.QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0); right.addWidget(self.progress_bar)
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
        self.progress_bar.setRange(0, 0)
        self.progress_text.setText('Loading FITS image…' if single else 'Preparing exposures…')
        self.worker = Worker(paths, self.bayer.currentText(), single)
        self.worker.message.connect(self.log.appendPlainText)
        self.worker.progress.connect(self.update_progress)
        self.worker.result.connect(self.loaded)
        self.worker.failed.connect(self.processing_failed)
        self.worker.finished.connect(self.finished)
        self.worker.start()
    def update_progress(self, completed, total, stage):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(completed)
        percent = 100*completed//max(total, 1)
        unit = 'frames' if stage == 'Aligning exposures' else 'rows'
        self.progress_text.setText(f'{stage}: {completed:,}/{total:,} {unit} • {percent}% complete • {total-completed:,} remaining')
    def processing_failed(self, text):
        if self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        self.progress_text.setText('Stopped: '+text)
        self.log.appendPlainText('Stopped: '+text)
    def finished(self):
        for control in (self.run, self.open, self.add, self.remove, self.bayer): control.setEnabled(True)
        self.cancel.setEnabled(False)
        self.worker.deleteLater(); self.worker = None
    def loaded(self, linear, header):
        self.original_linear, self.original_header = linear, header.copy()
        self.linear, self.header = linear, header
        self.reset_crop_controls()
        self.background = engine.background_model(linear)
        self.export.setEnabled(True)
        self.progress_bar.setRange(0, 100); self.progress_bar.setValue(100)
        self.progress_text.setText("Complete • 100% • 0 remaining")
        self.log.appendPlainText(engine.image_summary(linear, header))
        self.update_preview()
    def toggle_gpu(self, enabled):
        self.gpu = None
        if enabled:
            try:
                from gpu import GpuProcessor
                self.gpu = GpuProcessor()
                self.log.appendPlainText('GPU adjustments enabled: '+self.gpu.name)
                self.statusBar().showMessage('GPU adjustments: '+self.gpu.name+' • Alignment/stacking: CPU')
            except Exception as exc:
                self.use_gpu.blockSignals(True); self.use_gpu.setChecked(False); self.use_gpu.blockSignals(False)
                self.log.appendPlainText('Using CPU: '+str(exc))
                self.statusBar().showMessage('CPU processing • GPU unavailable')
        else:
            self.log.appendPlainText('CPU adjustments selected.')
            self.statusBar().showMessage('CPU processing')
        self.update_preview()
    def report_gpu_failure(self):
        if self.gpu is not None and self.gpu.disabled:
            self.log.appendPlainText('GPU adjustments failed; CPU result used: '+self.gpu.last_error)
            self.use_gpu.blockSignals(True); self.use_gpu.setChecked(False); self.use_gpu.blockSignals(False)
            self.gpu = None
            self.statusBar().showMessage('CPU processing • GPU fallback')
    def reset_crop_controls(self):
        h, w, _ = self.linear.shape
        self.crop_group.setEnabled(True)
        for name, spin in self.crop_margins.items():
            spin.setMaximum((w if name in ('Left', 'Right') else h)-1)
            spin.setValue(0)
        self.preview.band.hide()
    def select_crop(self, x0, y0, x1, y1):
        h, w, _ = self.linear.shape
        for name, value in zip(('Left', 'Right', 'Top', 'Bottom'), (x0, w-x1, y0, h-y1)):
            self.crop_margins[name].setValue(value)
    def crop_selected(self):
        if self.linear is None:
            return
        margins = {name.lower(): spin.value() for name, spin in self.crop_margins.items()}
        if not any(margins.values()):
            return
        try:
            self.linear, self.header = engine.crop_image(self.linear, self.header, **margins)
        except ValueError as exc:
            W.QMessageBox.information(self, 'Adjust crop', str(exc)); return
        self.background = engine.background_model(self.linear)
        self.reset_crop_controls()
        self.log.appendPlainText(f'Crop applied: {self.linear.shape[1]} × {self.linear.shape[0]} pixels. Restore full frame is available.')
        self.update_preview()
    def restore_full_frame(self):
        if self.linear is None:
            return
        self.linear, self.header = self.original_linear, self.original_header.copy()
        self.background = engine.background_model(self.linear)
        self.reset_crop_controls()
        self.log.appendPlainText('Full frame restored. Adjustments preserved.')
        self.update_preview()
    def reset_adjustments(self):
        for name, slider in self.sliders.items():
            slider.setValue(self.slider_defaults[name])
        self.baseline.setChecked(False)
        self.timer.stop()
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
        preview = engine.render(small, *self.settings(), model=self.background, gpu=self.gpu)
        self.report_gpu_failure()
        pixels = np.ascontiguousarray(np.round(preview*255).astype(np.uint8))
        image = QtGui.QImage(pixels.data, pixels.shape[1], pixels.shape[0], pixels.strides[0], QtGui.QImage.Format_RGB888).copy()
        self.preview.source_size = (self.linear.shape[1], self.linear.shape[0])
        self.preview.band.hide()
        self.pixmap = QtGui.QPixmap.fromImage(image)
        self.preview.setPixmap(self.pixmap.scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'pixmap'): self.preview.setPixmap(self.pixmap.scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
    def save(self):
        path, _ = W.QFileDialog.getSaveFileName(self, 'Export (FITS saves linear data)', str(Path(QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.PicturesLocation))/'image.tif'), '16-bit TIFF (*.tif);;PNG (*.png);;Linear FITS (*.fits)')
        if not path: return
        try:
            rendered = None if Path(path).suffix.lower() in ('.fit', '.fits') else engine.render(self.linear, *self.settings(), model=self.background, gpu=self.gpu)
            engine.save(path, self.linear, rendered, self.header)
            self.report_gpu_failure()
            self.log.appendPlainText('Saved '+path)
        except Exception as exc: W.QMessageBox.critical(self, 'Export failed', str(exc))
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.log.appendPlainText('Cancelling. Close again after processing stops.')
            event.ignore()
        else: event.accept()

if __name__ == '__main__':
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('SeestarStudio.Desktop')
    app = W.QApplication(sys.argv)
    app.setStyle('Fusion')
    window = Window(); window.show()
    if '--smoke-test' in sys.argv:
        from astropy.io import fits
        sample = np.ones((60, 80, 3), dtype=np.float32)*100
        sample[20:30, 20:30] = 500
        window.loaded(sample, fits.Header())
        window.sliders['Background correction %'].setValue(50)
        window.reset.click()
        window.crop_margins['Left'].setValue(5)
        window.apply_crop.click()
        assert window.linear.shape == (60, 75, 3)
        window.restore_crop.click()
        assert window.linear.shape == sample.shape
        window.update_preview()
        app.processEvents()
        window.close()
        sys.exit(0)
    sys.exit(app.exec())
