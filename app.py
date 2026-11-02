import sys
from pathlib import Path
import numpy as np
import cv2
from PySide6 import QtCore, QtGui, QtWidgets as W
import engine

from preview import ImagePreview

class WheelSlider(W.QSlider):
    """Keep the outer 5% on each side available for panel scrolling."""
    def wheelEvent(self,event):
        margin=self.width()*.05
        if event.position().x()<margin or event.position().x()>self.width()-margin:
            event.ignore();return
        super().wheelEvent(event)


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
        self.setWindowTitle('Astro Studio for Seestar • Preview 0.9')
        self.resize(1200, 800)
        app = W.QApplication.instance()
        palette = QtGui.QPalette()
        for role,color in [(QtGui.QPalette.Window,'#000000'),(QtGui.QPalette.WindowText,'#f1f6fd'),
                           (QtGui.QPalette.Base,'#071321'),(QtGui.QPalette.AlternateBase,'#102640'),
                           (QtGui.QPalette.Text,'#f1f6fd'),(QtGui.QPalette.Button,'#123252'),
                           (QtGui.QPalette.ButtonText,'#f1f6fd'),(QtGui.QPalette.Highlight,'#247eb6'),
                           (QtGui.QPalette.HighlightedText,'#ffffff'),(QtGui.QPalette.ToolTipBase,'#102640'),
                           (QtGui.QPalette.ToolTipText,'#ffffff'),(QtGui.QPalette.Link,'#7bceff'),(QtGui.QPalette.Mid,'#789ab7'),
                           (QtGui.QPalette.Light,'#a2c4e3'),(QtGui.QPalette.Dark,'#3c5878')]:
            palette.setColor(role,QtGui.QColor(color))
        for role in (QtGui.QPalette.WindowText,QtGui.QPalette.Text,QtGui.QPalette.ButtonText):
            palette.setColor(QtGui.QPalette.Disabled,role,QtGui.QColor('#91a5bf'))
        app.setPalette(palette)
        self.setStyleSheet("""
            QMainWindow, QWidget#appCanvas, QWidget#controlPanel, QScrollArea { background: #000000; color: #f1f6fd; }
            QScrollArea { border: none; }
            QGroupBox#stepLoad, QGroupBox#stepAdjust, QGroupBox#stepExport {
                border: 2px solid #3a6c9e; border-radius: 8px;
                margin-top: 4px; padding-top: 4px; background: #0b2545;
            }
            QLabel#sectionTitle {
                color: #ffffff; font-size: 20px; font-weight: bold;
                background: #12395e; border: 1px solid #74b9e9;
                border-radius: 5px; padding: 8px 10px; margin-bottom: 6px;
            }
            QLabel#sectionTitle:disabled { color: #c3d5e9; background: #102b49; border-color: #466888; }
            QFrame#gpuPanel { background: #0b2545; border: 2px solid #3a6c9e; border-radius: 8px; }
            QCheckBox#gpuSwitch { background: transparent; color: #f1f6fd; font-size: 12px; }
            QGroupBox { color: #f1f6fd; }
            QLabel { color: #f1f6fd; background: transparent; }
            QLabel:disabled { color: #91a5bf; }
            QCheckBox { color: #f1f6fd; spacing: 7px; }
            QCheckBox:disabled { color: #91a5bf; }
            QPushButton, QToolButton {
                background: #123252; color: #f1f6fd; border: 1px solid #476b95;
                border-radius: 4px; padding: 5px 8px;
            }
            QPushButton:hover, QToolButton:hover { background: #1b466d; border-color: #74c8ff; }
            QPushButton:pressed, QToolButton:pressed { background: #235a86; }
            QPushButton:disabled, QToolButton:disabled { background: #0a192b; color: #91a5bf; border-color: #28415f; }
            QComboBox, QSpinBox, QLineEdit, QListWidget, QPlainTextEdit {
                background: #071321; color: #f1f6fd; border: 1px solid #3a5e86;
                border-radius: 3px; padding: 3px; selection-background-color: #247eb6;
                selection-color: #ffffff;
            }
            QComboBox QAbstractItemView { background: #102640; color: #f1f6fd; selection-background-color: #247eb6; }
            QProgressBar { background: #071321; color: #ffffff; border: 1px solid #3a5e86; border-radius: 3px; text-align: center; }
            QProgressBar::chunk { background: #247eb6; }
            QSlider::groove:horizontal { height: 8px; background: #254668; border-radius: 4px; }
            QSlider::sub-page:horizontal { background: #379cc3; border-radius: 4px; }
            QSlider::handle:horizontal { width: 24px; margin: -8px 0; background: #def2ff;
                border: 2px solid #5ec9ff; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #91d6ff; }
            QSlider::handle:horizontal:pressed { background: #57bbef; }
        """)
        self.source_name = 'image' 
        self.linear = self.header = self.rendered = None
        self.worker = None
        self.gpu = None
        root = W.QWidget(); root.setObjectName('appCanvas'); self.setCentralWidget(root)
        layout = W.QHBoxLayout(root)
        left_column = W.QVBoxLayout(); layout.addLayout(left_column,1)
        header = W.QWidget(); header_row = W.QHBoxLayout(header); header_row.setContentsMargins(0,0,0,0)
        self.header_art = W.QLabel(); self.header_art.setFixedSize(104,104)
        self.header_art.setAlignment(QtCore.Qt.AlignCenter)
        self.artwork_path = Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'/'seestar-cartoon.png'
        artwork=QtGui.QPixmap(str(self.artwork_path))
        # Mirror only the displayed header image; preserve the supplied PNG bytes.
        artwork=artwork.transformed(QtGui.QTransform().scale(-1,1))
        if not artwork.isNull():
            self.header_art.setPixmap(artwork.scaled(104,104,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation))
        else:
            self.header_art.setText('Artwork pending')
        header_row.addWidget(self.header_art)
        brand = W.QVBoxLayout(); header_row.addLayout(brand,1)
        title = W.QLabel('Astro Studio for Seestar'); title.setWordWrap(True); title.setStyleSheet('font-size:24px; font-weight:bold'); brand.addWidget(title)
        disclaimer = W.QLabel('Not affiliated with Suzhou ZWO Co., Ltd.'); disclaimer.setWordWrap(True); disclaimer.setContentsMargins(0,0,0,0); brand.addWidget(disclaimer)
        left_column.addWidget(header)
        self.gpu_panel = W.QFrame(); self.gpu_panel.setObjectName('gpuPanel')
        gpu_row = W.QHBoxLayout(self.gpu_panel); gpu_row.setContentsMargins(12,10,12,10)
        self.use_gpu = W.QCheckBox('Click to use GPU for faster image adjustments')
        self.use_gpu.setObjectName('gpuSwitch')
        self.use_gpu.setToolTip('Accelerates stretch, saturation and smoothing. Alignment and stacking use CPU.')
        self.use_gpu.toggled.connect(self.toggle_gpu); gpu_row.addWidget(self.use_gpu); left_column.addWidget(self.gpu_panel)
        controls = W.QWidget(); controls.setObjectName('controlPanel')
        sidebar = W.QVBoxLayout(controls)
        scroll = W.QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(controls)
        scroll.setMinimumWidth(360); left_column.addWidget(scroll,1)
        self.sidebar_scroll = scroll
        instructions = W.QLabel('Instructions For Use:'); instructions.setStyleSheet('font-weight:bold; font-size:15px'); sidebar.addWidget(instructions)
        intro = W.QLabel('1. Load or stack\n2. Adjust and crop\n3. Export'); intro.setContentsMargins(12,0,0,6); sidebar.addWidget(intro)
        outer_sidebar = sidebar
        self.step_load = W.QGroupBox(); self.step_load.setAccessibleName('1. Load or stack'); self.step_load.setObjectName('stepLoad')
        outer_sidebar.addWidget(self.step_load)
        sidebar = W.QVBoxLayout(self.step_load)
        section_title = W.QLabel('1. Load or stack'); section_title.setObjectName('sectionTitle'); section_title.setWordWrap(True); sidebar.addWidget(section_title)
        load_hint = W.QLabel('Add individual exposures and stack them, or open a stack you already have.'); load_hint.setWordWrap(True); sidebar.addWidget(load_hint)
        self.add = W.QPushButton('Add exposures…'); self.add.clicked.connect(self.add_files); sidebar.addWidget(self.add)
        self.files = W.QListWidget(); self.files.setSelectionMode(W.QAbstractItemView.ExtendedSelection); sidebar.addWidget(self.files)
        self.remove = W.QPushButton('Remove selected'); self.remove.clicked.connect(self.remove_files); sidebar.addWidget(self.remove)
        sidebar.addWidget(W.QLabel('Bayer pattern (for 2D files only)'))
        self.bayer = W.QComboBox(); self.bayer.addItems(['Auto', 'RGGB', 'BGGR', 'GRBG', 'GBRG', 'None']); sidebar.addWidget(self.bayer)
        note = W.QLabel('Auto uses BAYERPAT. Missing header → grayscale.\nUse None for an already debayered 2D image.\nDo not mix targets, sizes, or exposure settings.'); note.setWordWrap(True); sidebar.addWidget(note)
        self.run = W.QPushButton('Align and stack exposures'); self.run.clicked.connect(lambda: self.start(False)); sidebar.addWidget(self.run)
        self.open = W.QPushButton('Open existing FITS stack…'); self.open.clicked.connect(lambda: self.start(True)); sidebar.addWidget(self.open)
        self.cancel = W.QPushButton('Cancel'); self.cancel.clicked.connect(lambda: self.worker.requestInterruption() if self.worker else None); self.cancel.setEnabled(False); sidebar.addWidget(self.cancel)
        self.next_adjust = W.QPushButton('Continue to step 2: Adjust and crop →')
        self.next_adjust.setEnabled(False)
        self.next_adjust.clicked.connect(lambda: self.show_step(self.step_adjust))
        sidebar.addWidget(self.next_adjust)
        outer_sidebar.addSpacing(20)
        self.step_adjust = W.QGroupBox(); self.step_adjust.setAccessibleName('2. Adjust and crop'); self.step_adjust.setObjectName('stepAdjust')
        self.step_adjust.setEnabled(False); outer_sidebar.addWidget(self.step_adjust)
        sidebar = W.QVBoxLayout(self.step_adjust)
        section_title = W.QLabel('2. Adjust and crop'); section_title.setObjectName('sectionTitle'); section_title.setWordWrap(True); sidebar.addWidget(section_title)
        adjust_hint = W.QLabel('Changes appear automatically in the preview. Adjust the sliders or crop, then continue to Export.'); adjust_hint.setWordWrap(True); sidebar.addWidget(adjust_hint)
        self.sliders = {}
        self.slider_defaults = {}
        for label, low, high, default in [('Stretch', 0, 100, 30), ('Black percentile ×100', 0, 100, 10), ('Saturation %', 0, 200, 100), ('Noise smoothing ×100', 0, 150, 0), ('Background correction %', 0, 100, 0), ('Red balance %', 50, 200, 100), ('Green balance %', 50, 200, 100), ('Blue balance %', 50, 200, 100), ('Brightness (stops ×100)', -200, 200, 0), ('Contrast %', 25, 250, 100)]:
            sidebar.addWidget(W.QLabel(label))
            slider = WheelSlider(QtCore.Qt.Horizontal); slider.setMinimumHeight(36); slider.setRange(low, high); slider.setValue(default); sidebar.addWidget(slider); self.sliders[label] = slider
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
        self.crop_group = W.QGroupBox('Crop — drag edges or corners in the image')
        crop_layout = W.QFormLayout(self.crop_group)
        self.crop_ratio = W.QComboBox()
        for title, ratio in [('Free',None),('Original', 'original'),('Square (1:1)',(1,1)),('4:3',(4,3)),('3:2',(3,2)),('16:9',(16,9)),('3:4 portrait',(3,4)),('2:3 portrait',(2,3)),('9:16 portrait',(9,16))]:
            self.crop_ratio.addItem(title,ratio)
        self.crop_ratio.currentIndexChanged.connect(self.ratio_changed)
        crop_layout.addRow('Aspect ratio',self.crop_ratio)
        self.guides = W.QComboBox(); self.guides.addItems(['Thirds + rulers','Center + rulers','Grid 10 × 10 + rulers','Off'])
        self.guides.currentTextChanged.connect(self.guides_changed)
        crop_layout.addRow('Alignment guides',self.guides)
        self.crop_dimensions = W.QLabel('No image loaded'); crop_layout.addRow(self.crop_dimensions)
        self.apply_crop = W.QPushButton('Apply crop'); self.apply_crop.clicked.connect(self.crop_selected)
        self.restore_crop = W.QPushButton('Restore full frame'); self.restore_crop.clicked.connect(self.restore_full_frame)
        crop_layout.addRow(self.apply_crop); crop_layout.addRow(self.restore_crop)
        self.crop_group.setEnabled(False); sidebar.addWidget(self.crop_group)
        next_export = W.QPushButton('Continue to step 3: Export →')
        next_export.clicked.connect(lambda: self.show_step(self.step_export)); sidebar.addWidget(next_export)
        outer_sidebar.addSpacing(20)
        self.step_export = W.QGroupBox(); self.step_export.setAccessibleName('3. Export'); self.step_export.setObjectName('stepExport')
        self.step_export.setEnabled(False); outer_sidebar.addWidget(self.step_export)
        sidebar = W.QVBoxLayout(self.step_export)
        section_title = W.QLabel('3. Export'); section_title.setObjectName('sectionTitle'); section_title.setWordWrap(True); sidebar.addWidget(section_title)
        export_hint = W.QLabel('Save the adjusted picture as TIFF, PNG or JPG, or keep linear data as FITS. Choose the format and filename in the save window.'); export_hint.setWordWrap(True); sidebar.addWidget(export_hint)
        self.export = W.QPushButton('3. Export image…'); self.export.setEnabled(False); self.export.clicked.connect(self.save); sidebar.addWidget(self.export)
        right = W.QVBoxLayout(); layout.addLayout(right, 3)
        zoom_row = W.QHBoxLayout(); right.addLayout(zoom_row)
        self.zoom_out = W.QPushButton('−'); self.zoom_out.setFixedWidth(36); zoom_row.addWidget(self.zoom_out)
        self.zoom_in = W.QPushButton('+'); self.zoom_in.setFixedWidth(36); zoom_row.addWidget(self.zoom_in)
        self.zoom_fit = W.QPushButton('Fit'); zoom_row.addWidget(self.zoom_fit)
        self.zoom_actual = W.QPushButton('100%'); zoom_row.addWidget(self.zoom_actual)
        self.zoom_label = W.QLabel('Fit'); zoom_row.addWidget(self.zoom_label); zoom_row.addStretch()
        self.preview = ImagePreview(); right.addWidget(self.preview,4)
        zoom_hint = W.QLabel('Drag crop edges/corners • Drag inside to move • Wheel to zoom • Right-drag to pan')
        zoom_hint.setWordWrap(True); right.addWidget(zoom_hint)
        self.zoom_out.clicked.connect(lambda: self.preview.zoom_by(.8))
        self.zoom_in.clicked.connect(lambda: self.preview.zoom_by(1.25))
        self.zoom_fit.clicked.connect(self.preview.fit_image)
        self.zoom_actual.clicked.connect(lambda: self.preview.set_zoom(1))
        self.preview.zoomChanged.connect(self.zoom_changed)
        self.preview.selection.connect(self.select_crop)
        self.progress_text = W.QLabel('Ready'); right.addWidget(self.progress_text)
        self.progress_bar = W.QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0); right.addWidget(self.progress_bar)
        self.log = W.QPlainTextEdit(); self.log.setReadOnly(True); right.addWidget(self.log, 1)
        self.timer = QtCore.QTimer(); self.timer.setSingleShot(True); self.timer.timeout.connect(self.update_preview)
        self.statusBar().showMessage('Ready • CPU processing • Originals are preserved')
    def zoom_changed(self,scale):
        self.zoom_label.setText(f'{scale*100:.0f}%')
        if hasattr(self,'timer'): self.schedule_preview()
    def show_step(self, widget):
        position = widget.mapTo(self.sidebar_scroll.widget(), QtCore.QPoint(0, 0)).y()
        self.sidebar_scroll.verticalScrollBar().setValue(position)
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
        self.pending_source_name = Path(paths[0]).stem
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
        self.source_name = getattr(self, 'pending_source_name', 'image')
        self.original_linear, self.original_header = linear, header.copy()
        self.linear, self.header = linear, header
        self.reset_crop_controls()
        self.background = engine.background_model(linear)
        self.export.setEnabled(True)
        self.step_adjust.setEnabled(True); self.step_export.setEnabled(True)
        self.next_adjust.setEnabled(True)
        QtCore.QTimer.singleShot(0, lambda: self.show_step(self.step_adjust))
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
    def active_crop_ratio(self):
        ratio=self.crop_ratio.currentData()
        if ratio == 'original':
            return (self.original_linear.shape[1],self.original_linear.shape[0])
        return ratio
    def guides_changed(self, text):
        self.preview.guide = text; self.preview.viewport().update()
    def ratio_changed(self):
        if self.linear is None:
            return
        self.preview.ratio=self.active_crop_ratio()
        self.crop_selection_changed()
    def reset_crop_controls(self):
        h,w,_=self.linear.shape
        self.crop_group.setEnabled(True)
        self.preview.source_size=(w,h)
        self.preview.ratio=self.active_crop_ratio()
        self.crop_bounds=(0,0,w,h)
        self.preview.fit_mode=True
        self.crop_selection_changed()
    def crop_selection_changed(self):
        if self.linear is None:return
        bounds=getattr(self,'crop_bounds',(0,0,self.linear.shape[1],self.linear.shape[0]))
        try:
            self.select_crop(*engine.fit_crop_ratio(bounds,self.active_crop_ratio()))
        except ValueError as exc:
            self.crop_dimensions.setText(str(exc));self.apply_crop.setEnabled(False)
    def select_crop(self,x0,y0,x1,y1):
        self.crop_bounds=(x0,y0,x1,y1)
        self.apply_crop.setEnabled(True)
        self.preview.selection_pixels=self.crop_bounds
        self.crop_dimensions.setText(f'Crop: {x1-x0:,} × {y1-y0:,} px • X {x0:,}, Y {y0:,}')
        self.preview.update_band()
    def crop_selected(self):
        if self.linear is None:
            return
        h,w,_=self.linear.shape
        x0,y0,x1,y1=self.crop_bounds
        margins=dict(left=x0,right=w-x1,top=y0,bottom=h-y1)
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
        v={name:slider.value() for name,slider in self.sliders.items()}
        if self.baseline.isChecked():return (30,.1,1,0,0,(1,1,1),0,1)
        return (v['Stretch'],v['Black percentile ×100']/100,v['Saturation %']/100,v['Noise smoothing ×100']/100,
                v['Background correction %']/100,tuple(v[name]/100 for name in ('Red balance %','Green balance %','Blue balance %')),
                v['Brightness (stops ×100)']/100,v['Contrast %']/100)
    def update_preview(self):
        if self.linear is None: return
        # Interactive display is reduced; export always renders at native resolution.
        step = max(1, int(np.floor(1/max(self.preview.transform().m11(), .01))))
        small = cv2.resize(self.linear, (max(1, self.linear.shape[1]//step), max(1, self.linear.shape[0]//step)), interpolation=cv2.INTER_AREA)
        preview = engine.render(small, *self.settings(), model=self.background, gpu=self.gpu)
        self.report_gpu_failure()
        pixels = np.ascontiguousarray(np.round(preview*255).astype(np.uint8))
        image = QtGui.QImage(pixels.data, pixels.shape[1], pixels.shape[0], pixels.strides[0], QtGui.QImage.Format_RGB888).copy()
        self.preview.set_image(image,(self.linear.shape[1],self.linear.shape[0]))
    def save(self):
        folder = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.PicturesLocation)
        dialog = W.QFileDialog(self, 'Export (FITS saves linear data)', folder)
        dialog.setAcceptMode(W.QFileDialog.AcceptSave)
        dialog.setFileMode(W.QFileDialog.AnyFile)
        dialog.setNameFilters(['16-bit TIFF (*.tif)', 'PNG (*.png)', 'JPG / JPEG (*.jpg *.jpeg)', 'Linear FITS (*.fits)'])
        dialog.setDefaultSuffix('tif')
        dialog.selectFile(engine.export_basename(self.header, self.source_name))
        dialog.filterSelected.connect(lambda selected: dialog.setDefaultSuffix('fits' if 'FITS' in selected else 'png' if 'PNG' in selected else 'jpg' if 'JPG' in selected else 'tif'))
        if dialog.exec() != W.QDialog.Accepted:
            return
        path = dialog.selectedFiles()[0]
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
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('AstroStudioForSeestar.Desktop')
    app = W.QApplication(sys.argv)
    app.setApplicationName('Astro Studio for Seestar')
    app.setApplicationDisplayName('Astro Studio for Seestar')
    app.setStyle('Fusion')
    window = Window(); window.show()
    if '--smoke-test' in sys.argv:
        from astropy.io import fits
        assert window.artwork_path.is_file(), 'Bundled header artwork missing'
        assert window.header_art.pixmap() is not None and not window.header_art.pixmap().isNull(), 'Header artwork failed to load'
        sample = np.ones((60, 80, 3), dtype=np.float32)*100
        sample[20:30, 20:30] = 500
        window.loaded(sample, fits.Header())
        window.sliders['Background correction %'].setValue(50)
        window.reset.click()
        window.select_crop(5,0,80,60)
        window.apply_crop.click()
        assert window.linear.shape == (60, 75, 3)
        window.restore_crop.click()
        assert window.linear.shape == sample.shape
        window.crop_ratio.setCurrentText('16:9')
        window.apply_crop.click()
        assert window.linear.shape[1]*9 == window.linear.shape[0]*16
        window.restore_crop.click()
        window.preview.set_zoom(1)
        window.zoom_fit.click()
        window.update_preview()
        app.processEvents()
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'smoke.jpg'
            engine.save(output,window.linear,engine.render(window.linear,*window.settings()),window.header)
            from PIL import Image
            with Image.open(output) as exported:
                assert exported.format=='JPEG'
        window.close()
        sys.exit(0)
    sys.exit(app.exec())
