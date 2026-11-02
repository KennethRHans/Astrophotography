import sys
import copy
import json
from pathlib import Path
import numpy as np
import cv2
from PySide6 import QtCore, QtGui, QtWidgets as W
import engine

from preview import ImagePreview
from project_store import EditHistory,validate_state,save_project,load_project
from histogram import HistogramView,histogram_data

from controls import WheelSlider,SliderValueRow,VisibleGpuCheckBox


class Worker(QtCore.QThread):
    message = QtCore.Signal(str)
    result = QtCore.Signal(object, object)
    progress = QtCore.Signal(int, int, str)
    failed = QtCore.Signal(str)
    def __init__(self, paths, bayer, single=False, use_gpu=False):
        super().__init__()
        self.paths, self.bayer, self.single = paths, bayer, single
        self.use_gpu = use_gpu
    def run(self):
        try:
            gpu = None
            if self.use_gpu and not self.single:
                try:
                    from gpu import GpuProcessor
                    gpu = GpuProcessor()
                    self.message.emit('GPU row combining enabled: '+gpu.name)
                except Exception as exc:
                    self.message.emit('GPU combining unavailable; using bounded CPU chunks: '+str(exc))
            result = engine.read_fits(self.paths[0], self.bayer) if self.single else engine.stack(self.paths, self.bayer, self.message.emit, self.isInterruptionRequested, self.progress.emit, gpu=gpu)
            self.result.emit(*result)
        except Exception as exc:
            self.failed.emit(str(exc))

class ProjectWorker(QtCore.QThread):
    done=QtCore.Signal(object)
    failed=QtCore.Signal(str)
    def __init__(self,path,payload=None):
        super().__init__();self.path=path;self.payload=payload
    def run(self):
        try:
            if self.payload is None:self.done.emit(load_project(self.path))
            else:
                save_project(self.path,*self.payload);self.done.emit(self.path)
        except Exception as exc:self.failed.emit(str(exc))


class Window(W.QMainWindow):
    def __init__(self,ask_on_close=True):
        super().__init__()
        self.ask_on_close=ask_on_close
        self.history=EditHistory()
        self._history_ready=False;self._restoring=False
        self.project_worker=None;self.project_path=None;self._saved_signature=None;self._dirty=False;self._after_io=None
        self.source_paths=[]
        self.setWindowTitle('Easy Astro Studio • Preview 0.12')
        self.base_title=self.windowTitle()
        self.resize(1200, 880)
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
            QToolBar { background: #000000; border-bottom: 1px solid #3a6c9e; spacing: 6px; }
            QFrame#histogramPanel { background: #0b2545; border: 1px solid #3a6c9e; border-radius: 5px; }
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
            QCheckBox#gpuSwitch::indicator { width: 20px; height: 20px; }
            QFrame#previewPanel { background: #000000; border: 2px solid #3a6c9e; border-radius: 8px; }
            QLabel#sliderValue { color: #def2ff; font-weight: bold; }
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
        self.artwork_path = Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'/'easy-astro-logo.png'
        artwork=QtGui.QPixmap(str(self.artwork_path))
        # Display the theme-colored supplied telescope logo upright.
        if not artwork.isNull():
            self.header_art.setPixmap(artwork.scaled(104,104,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation))
        else:
            self.header_art.setText('Artwork pending')
        header_row.addWidget(self.header_art)
        brand = W.QVBoxLayout(); header_row.addLayout(brand,1)
        title = W.QLabel('Easy Astro Studio'); title.setWordWrap(True); title.setStyleSheet('font-size:24px; font-weight:bold'); brand.addWidget(title)
        left_column.addWidget(header)
        self.gpu_panel = W.QFrame(); self.gpu_panel.setObjectName('gpuPanel')
        gpu_row = W.QHBoxLayout(self.gpu_panel); gpu_row.setContentsMargins(12,10,12,10)
        self.use_gpu = VisibleGpuCheckBox('Click to use GPU for faster combining and image adjustments')
        self.use_gpu.setObjectName('gpuSwitch')
        self.use_gpu.setToolTip('Accelerates row combining, stretch, saturation and smoothing. Star alignment stays on CPU. Uses bounded chunks with CPU fallback.')
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
        self.bayer_help = W.QLabel(); self.bayer_help.setWordWrap(True)
        self.bayer_help.setStyleSheet('color:#d5e8ff; padding:6px; border:1px solid #365f94;')
        sidebar.addWidget(self.bayer_help)
        self.bayer.currentTextChanged.connect(self.update_bayer_help)
        self.update_bayer_help()
        note = W.QLabel('The camera sensor and capture software determine the pattern, not the telescope optics. Auto reads BAYERPAT; a missing header produces grayscale. RGB stacks ignore this setting. Do not mix targets, sizes, or exposure settings.'); note.setWordWrap(True); sidebar.addWidget(note)
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
        self.slider_rows = {}
        self.slider_defaults = {}
        for label, low, high, default in [('Stretch', 0, 100, 30), ('Black percentile ×100', 0, 100, 10), ('Saturation %', 0, 200, 100), ('Noise smoothing ×100', 0, 150, 0), ('Background correction %', 0, 100, 0), ('Red balance %', 50, 200, 100), ('Green balance %', 50, 200, 100), ('Blue balance %', 50, 200, 100), ('Brightness (stops ×100)', -200, 200, 0), ('Contrast %', 25, 250, 100)]:
            sidebar.addWidget(W.QLabel(label))
            row = SliderValueRow(low,high,default); sidebar.addWidget(row)
            slider = row.slider; self.sliders[label] = slider; self.slider_rows[label] = row
            self.slider_defaults[label] = default
            slider.valueChanged.connect(self.schedule_preview)
            slider.sliderPressed.connect(self.commit_history)
            slider.sliderReleased.connect(self.commit_history)
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
        self.preview_panel = W.QFrame(); self.preview_panel.setObjectName('previewPanel')
        picture_layout = W.QVBoxLayout(self.preview_panel); picture_layout.setContentsMargins(4,4,4,4)
        self.preview = ImagePreview('Processed picture will appear here.'); picture_layout.addWidget(self.preview)
        right.addWidget(self.preview_panel,4)
        zoom_hint = W.QLabel('Drag crop edges/corners • Drag inside to move • Wheel to zoom • Right-drag to pan')
        zoom_hint.setWordWrap(True); right.addWidget(zoom_hint)
        self.zoom_out.clicked.connect(lambda: self.preview.zoom_by(.8))
        self.zoom_in.clicked.connect(lambda: self.preview.zoom_by(1.25))
        self.zoom_fit.clicked.connect(self.preview.fit_image)
        self.zoom_actual.clicked.connect(lambda: self.preview.set_zoom(1))
        self.preview.zoomChanged.connect(self.zoom_changed)
        self.preview.selection.connect(self.select_crop)
        self.preview.editStarted.connect(self.commit_history)
        self.preview.editFinished.connect(self.commit_history)
        self.progress_text = W.QLabel('Ready'); right.addWidget(self.progress_text)
        self.progress_bar = W.QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0); right.addWidget(self.progress_bar)
        self.histogram_panel=W.QFrame();self.histogram_panel.setObjectName('histogramPanel')
        hist_layout=W.QVBoxLayout(self.histogram_panel);hist_layout.setContentsMargins(8,5,8,5);hist_layout.setSpacing(3)
        hist_layout.addWidget(W.QLabel('RGB histogram • Black → White • Log scale • Preview sample'))
        self.histogram=HistogramView();hist_layout.addWidget(self.histogram)
        self.clip_summary=W.QLabel('Black clipping: 0% • White clipping: 0%');hist_layout.addWidget(self.clip_summary)
        self.mark_clipping=W.QCheckBox('Mark clipped pixels in preview (blue: black, red: white)')
        self.mark_clipping.toggled.connect(self.schedule_preview);hist_layout.addWidget(self.mark_clipping)
        self.histogram_panel.hide();right.addWidget(self.histogram_panel)
        self.log = W.QPlainTextEdit(); self.log.setReadOnly(True); right.addWidget(self.log, 1)
        self.timer = QtCore.QTimer(); self.timer.setSingleShot(True); self.timer.timeout.connect(self.update_preview)
        self.history_timer=QtCore.QTimer();self.history_timer.setSingleShot(True);self.history_timer.timeout.connect(self.commit_history)
        toolbar=self.addToolBar('Projects and history');toolbar.setMovable(False)
        self.open_project_action=QtGui.QAction('Open project…',self);self.open_project_action.setShortcut('Ctrl+O');self.open_project_action.triggered.connect(self.open_project_dialog)
        self.save_project_action=QtGui.QAction('Save project',self);self.save_project_action.setShortcut('Ctrl+S');self.save_project_action.triggered.connect(self.save_project_dialog)
        self.save_as_action=QtGui.QAction('Save project as…',self);self.save_as_action.setShortcut('Ctrl+Shift+S');self.save_as_action.triggered.connect(lambda: self.save_project_dialog(save_as=True))
        self.undo_action=QtGui.QAction('Undo',self);self.undo_action.setShortcut('Ctrl+Z');self.undo_action.triggered.connect(self.undo_edit)
        self.redo_action=QtGui.QAction('Redo',self);self.redo_action.setShortcuts(['Ctrl+Y','Ctrl+Shift+Z']);self.redo_action.triggered.connect(self.redo_edit)
        for action in (self.open_project_action,self.save_project_action,self.undo_action,self.redo_action):toolbar.addAction(action)
        file_menu=self.menuBar().addMenu('File');file_menu.addActions([self.open_project_action,self.save_project_action,self.save_as_action])
        edit_menu=self.menuBar().addMenu('Edit');edit_menu.addActions([self.undo_action,self.redo_action])
        self.update_actions()
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
        self.update_actions()
    def update_bayer_help(self):
        from bayer_guide import BAYER_GUIDE
        self.bayer_help.setText(BAYER_GUIDE[self.bayer.currentText()])

    def remove_files(self):
        for item in self.files.selectedItems(): self.files.takeItem(self.files.row(item))
        self.update_actions()
    def start(self, single):
        if self.project_worker is not None:return
        if single:
            path, _ = W.QFileDialog.getOpenFileName(self, 'Open a finished stack', '', 'FITS (*.fit *.fits *.FIT *.FITS)')
            if not path: return
            paths = [path]
        else:
            paths = [self.files.item(i).text() for i in range(self.files.count())]
            if len(paths) < 2:
                W.QMessageBox.information(self, 'Add exposures', 'Add at least two individual exposures.'); return
        if not self.allow_replace():return
        self.pending_source_paths=list(paths)
        self.pending_source_name = Path(paths[0]).stem
        self.log.appendPlainText('Starting. Alignment uses the first listed exposure as reference.\nTemporary disk space needed: approximately 12 bytes × pixels × frames.')
        for control in (self.run, self.open, self.add, self.remove, self.bayer, self.use_gpu): control.setEnabled(False)
        self.cancel.setEnabled(True)
        self.progress_bar.setRange(0, 0)
        self.progress_text.setText('Loading FITS image…' if single else 'Preparing exposures…')
        self.worker = Worker(paths, self.bayer.currentText(), single, self.use_gpu.isChecked())
        self.worker.message.connect(self.log.appendPlainText)
        self.worker.progress.connect(self.update_progress)
        self.worker.result.connect(self.loaded)
        self.worker.failed.connect(self.processing_failed)
        self.worker.finished.connect(self.finished)
        self.worker.start()
        self.update_actions()
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
        for control in (self.run, self.open, self.add, self.remove, self.bayer, self.use_gpu): control.setEnabled(True)
        self.cancel.setEnabled(False)
        self.worker.deleteLater(); self.worker = None
        self.update_actions()
    def loaded(self, linear, header):
        self._history_ready=False
        self.project_path=None
        self.source_paths=list(getattr(self,'pending_source_paths',[]))
        self.applied_crop=(0,0,linear.shape[1],linear.shape[0])
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
        self.histogram_panel.show()
        self.update_preview()
        self.history.reset(self.edit_state());self._history_ready=True
        self._saved_signature=None if self.worker is not None and not self.worker.single else self.project_signature()
        self.update_actions()
    def toggle_gpu(self, enabled):
        self.gpu = None
        if enabled:
            try:
                from gpu import GpuProcessor
                self.gpu = GpuProcessor()
                self.log.appendPlainText('GPU enabled for row combining and adjustments: '+self.gpu.name)
                self.statusBar().showMessage('GPU combining/adjustments: '+self.gpu.name+' • Alignment: CPU')
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
        self.schedule_history()
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
        if self.preview.mode is None:self.schedule_history()
    def crop_selected(self):
        if self.linear is None:
            return
        self.commit_history()
        h,w,_=self.linear.shape
        x0,y0,x1,y1=self.crop_bounds
        margins=dict(left=x0,right=w-x1,top=y0,bottom=h-y1)
        if not any(margins.values()):
            return
        try:
            self.linear, self.header = engine.crop_image(self.linear, self.header, **margins)
        except ValueError as exc:
            W.QMessageBox.information(self, 'Adjust crop', str(exc)); return
        ox,oy,_,_=self.applied_crop
        self.applied_crop=(ox+x0,oy+y0,ox+x1,oy+y1)
        self.background = engine.background_model(self.linear)
        self.reset_crop_controls()
        self.log.appendPlainText(f'Crop applied: {self.linear.shape[1]} × {self.linear.shape[0]} pixels. Restore full frame is available.')
        self.update_preview()
        self.commit_history()
    def restore_full_frame(self):
        if self.linear is None:
            return
        self.commit_history()
        self.applied_crop=(0,0,self.original_linear.shape[1],self.original_linear.shape[0])
        self.linear, self.header = self.original_linear, self.original_header.copy()
        self.background = engine.background_model(self.linear)
        self.reset_crop_controls()
        self.log.appendPlainText('Full frame restored. Adjustments preserved.')
        self.update_preview()
        self.commit_history()
    def reset_adjustments(self):
        self.commit_history()
        for name, slider in self.sliders.items():
            slider.setValue(self.slider_defaults[name])
        self.baseline.setChecked(False)
        self.timer.stop()
        self.update_preview()
        self.commit_history()
    def schedule_preview(self):
        self.timer.start(150)
        self.schedule_history()
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
        valid=(small>0).all(axis=-1)
        bins,black,white=histogram_data(preview,valid)
        self.histogram.set_data(bins)
        self.clip_summary.setText(f'Black clipping: {black:.3f}% • White clipping: {white:.3f}% (preview)')
        self.clip_summary.setStyleSheet('color: #ffce7a;' if max(black,white)>.1 else 'color: #c3d9ef;')
        pixels = np.ascontiguousarray(np.round(preview*255).astype(np.uint8))
        if self.mark_clipping.isChecked():
            pixels[np.any(preview<=0,axis=-1)&valid]=(45,105,255)
            pixels[np.any(preview>=1,axis=-1)&valid]=(255,65,65)
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
    def edit_state(self):
        return dict(sliders={name:slider.value() for name,slider in self.sliders.items()},compare=self.baseline.isChecked(),
                    applied_crop=list(self.applied_crop),selection=list(self.crop_bounds),ratio=self.crop_ratio.currentText(),guides=self.guides.currentText())
    def project_signature(self):
        return json.dumps(dict(state=self.edit_state(),input_files=[self.files.item(i).text() for i in range(self.files.count())],bayer=self.bayer.currentText()),sort_keys=True)
    def schedule_history(self):
        if self._history_ready and not self._restoring:
            if self.preview.mode is not None or any(slider.isSliderDown() for slider in self.sliders.values()):self.history_timer.stop()
            else:self.history_timer.start(400)
            self.update_actions()
    def commit_history(self):
        if not self._history_ready or self._restoring:return
        self.history_timer.stop();self.history.push(self.edit_state());self.update_actions()
    def update_actions(self):
        if not hasattr(self,'undo_action'):return
        busy=self.worker is not None or self.project_worker is not None
        ready=self.linear is not None and self._history_ready
        pending=ready and self.edit_state()!=self.history.states[self.history.index]
        self.undo_action.setEnabled(ready and not busy and (self.history.can_undo or pending))
        self.redo_action.setEnabled(ready and not busy and self.history.can_redo and not pending)
        self.save_project_action.setEnabled(ready and not busy);self.save_as_action.setEnabled(ready and not busy)
        self.open_project_action.setEnabled(not busy)
        if ready:
            self._dirty=self.project_signature()!=self._saved_signature
            name=Path(self.project_path).name if self.project_path else engine.export_basename(self.header,self.source_name)
            self.setWindowTitle(self.base_title+' • '+name+(' *' if self._dirty else ''))
    def validate_edit_state(self,state,shape):
        validate_state(state,shape,{name:(slider.minimum(),slider.maximum()) for name,slider in self.sliders.items()})
        if self.crop_ratio.findText(state['ratio'])<0 or self.guides.findText(state['guides'])<0:raise ValueError('Project contains unsupported crop guides or ratio')
    def apply_edit_state(self,state):
        self.validate_edit_state(state,self.original_linear.shape)
        self._restoring=True;self.history_timer.stop();self.timer.stop()
        try:
            rect=tuple(state['applied_crop'])
            if rect!=self.applied_crop:
                x0,y0,x1,y1=rect;h,w,_=self.original_linear.shape
                self.linear,self.header=engine.crop_image(self.original_linear,self.original_header,x0,w-x1,y0,h-y1)
                self.applied_crop=rect;self.background=engine.background_model(self.linear)
            for name,value in state['sliders'].items():
                widget=self.sliders[name];previous=widget.blockSignals(True);widget.setValue(value);widget.blockSignals(previous)
                self.slider_rows[name].position_value()
            for widget,value in ((self.baseline,state['compare']),(self.crop_ratio,state['ratio']),(self.guides,state['guides'])):
                previous=widget.blockSignals(True)
                if widget is self.baseline:widget.setChecked(value)
                else:widget.setCurrentText(value)
                widget.blockSignals(previous)
            self.preview.ratio=self.active_crop_ratio();self.preview.guide=self.guides.currentText()
            self.select_crop(*state['selection']);self.update_preview()
        finally:self._restoring=False
        self.update_actions()
    def undo_edit(self):
        self.commit_history()
        if self.history.can_undo:self.apply_edit_state(self.history.undo())
    def redo_edit(self):
        self.commit_history()
        if self.history.can_redo:self.apply_edit_state(self.history.redo())
    def allow_replace(self):
        self.commit_history()
        if not self._dirty or not self.ask_on_close:return True
        return W.QMessageBox.question(self,'Replace current image?','Unsaved project changes will be lost. Cancel and save the project first to keep them.',W.QMessageBox.Discard|W.QMessageBox.Cancel,W.QMessageBox.Cancel)==W.QMessageBox.Discard
    def project_manifest(self):
        self.commit_history()
        center=self.preview.mapToScene(self.preview.viewport().rect().center())
        return dict(state=self.edit_state(),source_name=self.source_name,source_files=self.source_paths,
                    input_files=[self.files.item(i).text() for i in range(self.files.count())],bayer=self.bayer.currentText(),
                    history=dict(states=copy.deepcopy(self.history.states),index=self.history.index),
                    view=dict(fit=self.preview.fit_mode,zoom=self.preview.transform().m11(),center=[center.x(),center.y()],
                              mark_clipping=self.mark_clipping.isChecked(),gpu=self.use_gpu.isChecked()))
    def save_project_dialog(self,checked=False,save_as=False,after_save=None):
        if self.linear is None or self.worker is not None or self.project_worker is not None:return
        path=None if save_as else self.project_path
        if not path:
            initial=str(Path(QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation))/(engine.export_basename(self.header,self.source_name)+'.astro'))
            path,_=W.QFileDialog.getSaveFileName(self,'Save project',initial,'Easy Astro Studio project (*.astro)')
            if not path:return
            if Path(path).suffix.lower()!='.astro':path+='.astro'
        self.save_project_path(path,after_save)
    def save_project_path(self,path,after_save=None):
        self._after_io=after_save
        payload=(self.original_linear,self.original_header.copy(),self.project_manifest())
        self._start_project_io(path,payload)
    def open_project_dialog(self):
        path,_=W.QFileDialog.getOpenFileName(self,'Open saved project','','Easy Astro Studio project (*.astro)')
        if path and self.allow_replace():self.open_project_path(path)
    def open_project_path(self,path):self._after_io=None;self._start_project_io(path,None)
    def _start_project_io(self,path,payload):
        if self.worker is not None or self.project_worker is not None:return
        self.timer.stop();self.history_timer.stop();self.preview.mode=None
        self.project_worker=ProjectWorker(str(path),payload)
        self._project_io_path=str(path)
        self._project_io_ok=False
        for widget in (self.step_load,self.step_adjust,self.step_export,self.use_gpu,self.preview,self.zoom_in,self.zoom_out,self.zoom_fit,self.zoom_actual,self.mark_clipping):widget.setEnabled(False)
        self.progress_bar.setRange(0,0);self.progress_text.setText('Saving project…' if payload is not None else 'Opening project…')
        self.project_worker.done.connect(self._project_saved if payload is not None else self._project_opened)
        self.project_worker.failed.connect(self._project_error);self.project_worker.finished.connect(self._project_finished)
        self.project_worker.start();self.update_actions()
    def _project_saved(self,path):
        self._project_io_ok=True
        self.project_path=str(path);self._saved_signature=self.project_signature();self._dirty=False
        self.log.appendPlainText('Project saved: '+str(path));self.progress_text.setText('Project saved • 100%')
    def _project_opened(self,payload):
        try:
            linear,header,meta=payload
            self.validate_edit_state(meta['state'],linear.shape)
            for state in meta.get('history',{}).get('states',[]):self.validate_edit_state(state,linear.shape)
            self.loaded(linear,header)
            self.source_name=str(meta.get('source_name','image'))
            self.source_paths=list(meta.get('source_files',[]))
            self.files.clear();self.files.addItems(meta.get('input_files',[]))
            if self.bayer.findText(meta.get('bayer','Auto'))>=0:self.bayer.setCurrentText(meta.get('bayer','Auto'))
            self.apply_edit_state(meta['state'])
            history=meta.get('history')
            if history:self.history.states=copy.deepcopy(history['states']);self.history.index=history['index']
            else:self.history.reset(self.edit_state())
            view=meta.get('view',{})
            self.mark_clipping.setChecked(bool(view.get('mark_clipping',False)))
            self.use_gpu.setChecked(bool(view.get('gpu',False)))
            self.update_preview()
            if view.get('fit',True):self.preview.fit_image()
            else:
                zoom=float(view.get('zoom',1))
                if np.isfinite(zoom):self.preview.set_zoom(zoom)
                center=view.get('center',[])
                if len(center)==2 and all(isinstance(v,(float,int)) and np.isfinite(v) for v in center):self.preview.centerOn(*center)
            self.project_path=self._project_io_path;self._saved_signature=self.project_signature();self._dirty=False
            self._project_io_ok=True
            self.progress_text.setText('Project opened • 100%');self.log.appendPlainText('Project image, editing state and history restored.')
        except Exception as exc:self._project_error(str(exc))
    def _project_error(self,text):
        self._after_io=None;self.processing_failed('Project: '+text)
        W.QMessageBox.critical(self,'Project failed',text)
    def _project_finished(self):
        self.project_worker.deleteLater();self.project_worker=None
        self.step_load.setEnabled(True)
        for widget in (self.use_gpu,self.preview,self.zoom_in,self.zoom_out,self.zoom_fit,self.zoom_actual,self.mark_clipping):widget.setEnabled(True)
        self.step_adjust.setEnabled(self.linear is not None);self.step_export.setEnabled(self.linear is not None)
        self.progress_bar.setRange(0,100);self.progress_bar.setValue(100 if self._project_io_ok else 0)
        self.update_actions()
        callback=self._after_io;self._after_io=None
        if callback:QtCore.QTimer.singleShot(0,callback)
    def closeEvent(self, event):
        if self.project_worker is not None:
            self.log.appendPlainText('Project save/load is in progress. Close again after it finishes.');event.ignore();return
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption();self.log.appendPlainText('Cancelling. Close again after processing stops.');event.ignore();return
        self.commit_history()
        if self._dirty and self.ask_on_close:
            result=W.QMessageBox.question(self,'Save project before closing?','Save your image and editing state as a project before closing?',W.QMessageBox.Save|W.QMessageBox.Discard|W.QMessageBox.Cancel,W.QMessageBox.Save)
            if result==W.QMessageBox.Cancel:event.ignore();return
            if result==W.QMessageBox.Save:
                event.ignore();self.save_project_dialog(after_save=self.close);return
        event.accept()

if __name__ == '__main__':
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('EasyAstroStudio.Desktop')
    app = W.QApplication(sys.argv)
    app.setApplicationName('Easy Astro Studio')
    app.setApplicationDisplayName('Easy Astro Studio')
    app.setStyle('Fusion')
    window = Window(ask_on_close='--smoke-test' not in sys.argv); window.show()
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
            window.commit_history()
            project=Path(folder)/'smoke.astro'
            save_project(project,window.original_linear,window.original_header,window.project_manifest())
            restored,restored_header,meta=load_project(project)
            assert np.array_equal(restored,window.original_linear)
            assert meta['state']==window.edit_state()
        window.close()
        sys.exit(0)
    sys.exit(app.exec())
