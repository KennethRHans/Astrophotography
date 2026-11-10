import sys
import copy
import json
import time
from pathlib import Path
import numpy as np
import cv2
from PySide6 import QtCore, QtGui, QtWidgets as W
import engine
from macos_access import configure_storage, sandboxed, select_files, select_save_file, select_export_file, file_access
from macos_window import install_reopen_handler
from annotations import LabelsPanel,paint_annotations
from identify_dialog import IdentifyDialog
from privacy_viewer import show_privacy

from preview import ImagePreview
from project_store import EditHistory,validate_state,save_project,load_project
from histogram import HistogramView,histogram_data
import community_links
from feedback import FeedbackDialog
from app_version import VERSION
from themes import THEMES,apply_theme
from frame_review import FrameReviewDialog
from preview_render import PreviewRenderer,PreviewWorker

from controls import WheelSlider,SliderValueRow,VisibleGpuCheckBox
from tone_curve import ToneCurve
from astro_adjustments import NEUTRAL_CURVE


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
            times={'message':0.,'progress':0.,'stage':None}
            def message(text):
                now=time.monotonic()
                if text.startswith('Combining rows') and now-times['message']<.12:return
                times['message']=now;self.message.emit(text)
            def progress(done,total,stage):
                now=time.monotonic()
                if stage==times['stage'] and done<total and now-times['progress']<.05:return
                times['stage']=stage;times['progress']=now;self.progress.emit(done,total,stage)
            gpu = None
            if self.use_gpu and not self.single:
                try:
                    from gpu import create_gpu_processor
                    gpu = create_gpu_processor(for_stacking=True)
                    self.message.emit('GPU row combining enabled: '+gpu.name if gpu is not None else 'Stack combining and alignment use CPU; Metal accelerates image adjustments.')
                except Exception as exc:
                    self.message.emit('GPU combining unavailable; using bounded CPU chunks: '+str(exc))
            result = engine.read_image(self.paths[0], self.bayer) if self.single else engine.stack(self.paths, self.bayer, message, self.isInterruptionRequested, progress, gpu=gpu)
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
    def __init__(self,ask_on_close=True,settings=None):
        super().__init__()
        self.ask_on_close=ask_on_close
        self.history=EditHistory()
        self._history_ready=False;self._restoring=False
        self.project_worker=None;self.project_path=None;self._saved_signature=None;self._dirty=False;self._after_io=None
        self.solution_header=None
        self.annotations=[];self.labels_visible=True
        self.source_paths=[]
        self.preview_renderer=PreviewRenderer();self.preview_worker=None;self._preview_generation=0;self._preview_pending=False;self._close_after_preview=False;self._files_json=None
        self.setWindowTitle('Easy Astro Studio • Version '+VERSION)
        self.base_title=self.windowTitle()
        self.resize(1200, 880)
        self.settings_store=settings if settings is not None else QtCore.QSettings('Astrivanta','EasyAstroStudio')
        self.theme_name=apply_theme(W.QApplication.instance(),self.settings_store.value('appearance/theme','Dark'))
        self.source_name = 'image' 
        self.linear = self.header = self.rendered = None
        self.worker = None
        self.gpu = None
        root = W.QWidget(); root.setObjectName('appCanvas'); self.setCentralWidget(root)
        root_layout = W.QVBoxLayout(root); root_layout.setContentsMargins(10,6,10,6)
        layout = W.QHBoxLayout(); root_layout.addLayout(layout,1)
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
        byline=W.QLabel('by Astrivanta ©');byline.setAlignment(QtCore.Qt.AlignCenter);byline.setObjectName('byline');brand.addWidget(byline)
        brand.setSpacing(3);brand.insertStretch(0);brand.addStretch()
        title.setSizePolicy(W.QSizePolicy.Preferred,W.QSizePolicy.Maximum);byline.setSizePolicy(W.QSizePolicy.Preferred,W.QSizePolicy.Maximum)
        left_column.addWidget(header)
        self.gpu_panel = W.QFrame(); self.gpu_panel.setObjectName('gpuPanel')
        gpu_row = W.QHBoxLayout(self.gpu_panel); gpu_row.setContentsMargins(12,10,12,10)
        self.use_gpu = VisibleGpuCheckBox('Click to use GPU for faster combining and image adjustments')
        self.use_gpu.setObjectName('gpuSwitch')
        if sys.platform == 'darwin':
            self.use_gpu.setText('Use Metal GPU for image adjustments')
        self.use_gpu.setToolTip('Metal accelerates stretch, color and smoothing. Stacking and alignment remain on CPU.' if sys.platform == 'darwin' else 'Accelerates row combining, stretch, saturation and smoothing. Star alignment stays on CPU. Uses bounded chunks with CPU fallback.')
        self.use_gpu.toggled.connect(self.toggle_gpu); gpu_row.addWidget(self.use_gpu); left_column.addWidget(self.gpu_panel)
        controls = W.QWidget(); controls.setObjectName('controlPanel')
        sidebar = W.QVBoxLayout(controls)
        scroll = W.QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(controls)
        scroll.setMinimumWidth(360); left_column.addWidget(scroll,1)
        self.sidebar_scroll = scroll
        instructions = W.QLabel('Instructions For Use:'); instructions.setStyleSheet('font-weight:bold; font-size:15px'); sidebar.addWidget(instructions)
        intro = W.QLabel('1. Set Bayer Pattern (Equipment-based)\n2. Load Image, FITS Stack or Multiple Files to Stack\n3. Align and Stack Exposures\n4. Adjust and Crop\n5. Export'); intro.setWordWrap(True); intro.setContentsMargins(12,0,0,6); sidebar.addWidget(intro)
        outer_sidebar = sidebar
        self.step_equipment=W.QGroupBox();self.step_equipment.setObjectName('stepEquipment');self.step_equipment.setAccessibleName('1. Set Bayer Pattern (Equipment-based)')
        outer_sidebar.addWidget(self.step_equipment);sidebar=W.QVBoxLayout(self.step_equipment)
        section_title=W.QLabel('1. Set Bayer Pattern (Equipment-based)');section_title.setObjectName('sectionTitle');section_title.setWordWrap(True);sidebar.addWidget(section_title)
        sidebar.addWidget(W.QLabel('Select Bayer pattern (for 2d files only)'))
        self.bayer = W.QComboBox(); self.bayer.addItems(['Auto', 'RGGB', 'BGGR', 'GRBG', 'GBRG', 'None']); sidebar.addWidget(self.bayer)
        self.bayer_help = W.QLabel(); self.bayer_help.setWordWrap(True)
        self.bayer_help.setObjectName('bayerHelp')
        sidebar.addWidget(self.bayer_help)
        self.bayer.currentTextChanged.connect(self.update_bayer_help)
        self.update_bayer_help()
        note = W.QLabel('The camera sensor and capture software determine the pattern, not the telescope optics. Auto reads BAYERPAT; a missing header produces grayscale. RGB stacks ignore this setting. Do not mix targets, sizes, or exposure settings.'); note.setWordWrap(True); sidebar.addWidget(note)
        next_load=W.QPushButton('Continue to step 2: Load files →');next_load.clicked.connect(lambda:self.show_step(self.step_load));sidebar.addWidget(next_load)
        outer_sidebar.addSpacing(20)
        self.step_load=W.QGroupBox();self.step_load.setObjectName('stepLoad');self.step_load.setAccessibleName('2. Load Image, FITS Stack or Multiple Files to Stack')
        outer_sidebar.addWidget(self.step_load);sidebar=W.QVBoxLayout(self.step_load)
        section_title=W.QLabel('2. Load Image, FITS Stack or Multiple Files to Stack');section_title.setObjectName('sectionTitle');section_title.setWordWrap(True);sidebar.addWidget(section_title)
        load_hint=W.QLabel('Open a JPG, PNG or existing FITS stack and continue to step 4, or add individual exposures for step 3.');load_hint.setWordWrap(True);sidebar.addWidget(load_hint)
        self.open = W.QPushButton('Open image or FITS stack…'); self.open.clicked.connect(lambda: self.start(True)); sidebar.addWidget(self.open)
        or_label=W.QLabel('OR');or_label.setAlignment(QtCore.Qt.AlignCenter);or_label.setStyleSheet('font-weight:bold');sidebar.addWidget(or_label)
        self.add = W.QPushButton('Add exposures…'); self.add.clicked.connect(self.add_files); sidebar.addWidget(self.add)
        self.files = W.QListWidget(); self.files.setSelectionMode(W.QAbstractItemView.ExtendedSelection); sidebar.addWidget(self.files)
        self.remove = W.QPushButton('Remove selected'); self.remove.clicked.connect(self.remove_files); sidebar.addWidget(self.remove)
        self.review=W.QPushButton('Preview / rate exposures…');self.review.clicked.connect(self.review_exposures);sidebar.addWidget(self.review)
        self.next_stack=W.QPushButton('Continue to step 3: Align and stack →');self.next_stack.clicked.connect(lambda:self.show_step(self.step_stack));sidebar.addWidget(self.next_stack)
        outer_sidebar.addSpacing(20)
        self.step_stack=W.QGroupBox();self.step_stack.setObjectName('stepStack');self.step_stack.setAccessibleName('3. Align and Stack Exposures')
        outer_sidebar.addWidget(self.step_stack);sidebar=W.QVBoxLayout(self.step_stack)
        section_title=W.QLabel('3. Align and Stack Exposures');section_title.setObjectName('sectionTitle');section_title.setWordWrap(True);sidebar.addWidget(section_title)
        stack_hint=W.QLabel('For individual exposures only. Existing stacks skip this step and open in step 4.');stack_hint.setWordWrap(True);sidebar.addWidget(stack_hint)
        self.reference_label=W.QLabel('Reference: first exposure in the list');self.reference_label.setWordWrap(True);sidebar.addWidget(self.reference_label)
        self.run = W.QPushButton('Align and stack exposures'); self.run.clicked.connect(lambda: self.start(False)); sidebar.addWidget(self.run)
        self.cancel = W.QPushButton('Cancel'); self.cancel.clicked.connect(lambda: self.worker.requestInterruption() if self.worker else None); self.cancel.setEnabled(False); sidebar.addWidget(self.cancel)
        self.next_adjust = W.QPushButton('Continue to step 4: Adjust and Crop →')
        self.next_adjust.setEnabled(False)
        self.next_adjust.clicked.connect(lambda: self.show_step(self.step_adjust))
        sidebar.addWidget(self.next_adjust)
        outer_sidebar.addSpacing(20)
        self.step_adjust = W.QGroupBox(); self.step_adjust.setAccessibleName('4. Adjust and Crop'); self.step_adjust.setObjectName('stepAdjust')
        self.step_adjust.setEnabled(False); outer_sidebar.addWidget(self.step_adjust)
        sidebar = W.QVBoxLayout(self.step_adjust)
        section_title = W.QLabel('4. Adjust and Crop'); section_title.setObjectName('sectionTitle'); section_title.setWordWrap(True); sidebar.addWidget(section_title)
        adjust_hint = W.QLabel('Changes appear automatically in the preview. Adjust the sliders or crop, then continue to Export.'); adjust_hint.setWordWrap(True); sidebar.addWidget(adjust_hint)
        self.sliders = {}
        self.slider_rows = {}
        self.slider_defaults = {};self.slider_labels={}
        percent=lambda v:f'{v}%'
        specs={
            'Stretch':('Stretch — faint detail',0,100,30,'Asinh stretch reveals faint signal. It can brighten noise and sky as well as the target.',str),
            'Black percentile ×100':('Black point — dark clipping',0,100,10,'Percent of the darkest samples used for the black point. Raising this can hide faint signal; watch black clipping.',lambda v:f'{v/100:.2f}%'),
            'Brightness (stops ×100)':('Exposure — display brightness',-200,200,0,'Display exposure in stops; does not change capture exposure or linear FITS data.',lambda v:f'{v/100:+.2f} stops'),
            'Contrast %':('Contrast',25,250,100,'Contrast around a fixed display pivot. High values can clip shadows and highlights.',percent),
            'Saturation %':('Color saturation',0,200,100,'Changes color strength; not color calibration.',percent),
            'Midtones %':('Midtones — faint detail',-100,100,0,'Positive values brighten intermediate tones; negative values darken them. Black/white endpoints are fixed. Uses a luminance midtones transfer.',lambda v:f'{v:+d}%'),
            'Star-preserving noise reduction %':('Noise reduction — star/edge protected',0,100,0,'Edge-aware noise reduction with a protective mask. Start low. Strong settings can still suppress faint detail; this is not a substitute for calibration or more exposure.',percent),
            'Background correction %':('Gradient removal',0,100,0,'Quadratic background correction. Extended nebulosity may be mistaken for sky; use cautiously.',percent),
            'Background neutralization %':('Background color neutralization',0,100,0,'Reduces an estimated sky color cast before stretching. Can alter faint colored nebulosity; this is not photometric color calibration. 0% is off.',percent),
            'Red balance %':('Red balance — manual',50,200,100,'Relative red-channel gain; not photometric color calibration.',percent),
            'Green balance %':('Green balance — manual',50,200,100,'Relative green-channel gain; not photometric color calibration.',percent),
            'Blue balance %':('Blue balance — manual',50,200,100,'Relative blue-channel gain; not photometric color calibration.',percent),
            'Star protection %':('Noise reduction — star protection',0,100,100,'Protection of detected bright structures and nearby wings. 100% is recommended. Very faint stars may not enter the mask.',percent),
            'Noise smoothing ×100':('Legacy smoothing — ordinary blur',0,150,0,'Gaussian smoothing can soften stars and fine structure. Leave off unless needed; this is not a star-preserving denoiser.',lambda v:f'{v/100:.2f} px'),
            'Sky brightness (stops ×100)':('Sky exposure — darker tones',-200,200,0,'Darkens or lightens darker tones in stops. Zero is neutral; faint nebulosity also changes.',lambda v:f'{v/100:+.2f} stops'),
            'Sky background %':('Shadows / sky brightness',-100,100,0,'Offsets darker tones, including faint nebulosity. This is not a measured sky-only mask.',lambda v:f'{v:+d}%')}
        self.advanced_names=list(specs)[7:]
        for index,(name,(label,low,high,default,tooltip,formatter)) in enumerate(specs.items()):
            if index==7:
                self.advanced_toggle=W.QToolButton();self.advanced_toggle.setText('Advanced: sky, color and noise');self.advanced_toggle.setCheckable(True);self.advanced_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon);self.advanced_toggle.setArrowType(QtCore.Qt.RightArrow);sidebar.addWidget(self.advanced_toggle)
                self.advanced_panel=W.QWidget();advanced_layout=W.QVBoxLayout(self.advanced_panel);advanced_layout.setContentsMargins(6,2,0,2);sidebar.addWidget(self.advanced_panel);self.advanced_panel.hide()
                self.advanced_toggle.toggled.connect(self.advanced_panel.setVisible)
                self.advanced_toggle.toggled.connect(lambda checked:self.advanced_toggle.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow))
            target=sidebar if index<7 else advanced_layout
            caption=W.QLabel(label);caption.setToolTip(tooltip);self.slider_labels[name]=caption;target.addWidget(caption)
            row=SliderValueRow(low,high,default,formatter=formatter);row.setToolTip(tooltip);target.addWidget(row)
            slider=row.slider;self.sliders[name]=slider;self.slider_rows[name]=row;self.slider_defaults[name]=default
            slider.valueChanged.connect(self.schedule_preview);slider.sliderPressed.connect(self.commit_history);slider.sliderReleased.connect(self.commit_history);slider.sliderReleased.connect(self.schedule_preview)
        self.curve_group=W.QGroupBox('Luminance curve — shadows, midtones, highlights');curve_layout=W.QVBoxLayout(self.curve_group);sidebar.addWidget(self.curve_group)
        self.curve=ToneCurve();curve_layout.addWidget(self.curve)
        curve_hint=W.QLabel('Drag the three interior points up/down. Black and white stay fixed.');curve_hint.setWordWrap(True);curve_layout.addWidget(curve_hint)
        self.reset_curve=W.QPushButton('Reset curve');self.reset_curve.clicked.connect(self.reset_tone_curve);curve_layout.addWidget(self.reset_curve)
        self.curve.editStarted.connect(self.commit_history);self.curve.editFinished.connect(self.commit_history);self.curve.editFinished.connect(self.schedule_preview);self.curve.changed.connect(self.schedule_preview)
        hint = W.QLabel('Use Stretch, Black point and Exposure first. Advanced shadow and gradient controls can suppress faint nebulosity. Color balance is manual.'); hint.setWordWrap(True); sidebar.addWidget(hint)
        self.baseline = W.QCheckBox('Compare: default stretch'); self.baseline.toggled.connect(self.schedule_preview); sidebar.addWidget(self.baseline)
        self.auto_sky=W.QPushButton('Auto sky background');self.auto_sky.setToolTip('Suggest a darker display using Stretch and Brightness; clears the Sky offset. Other adjustments and source data are preserved. Faint nebulosity can look darker. Undo restores the previous view.');self.auto_sky.clicked.connect(self.auto_sky_background);sidebar.addWidget(self.auto_sky)
        self.reset = W.QPushButton('Reset adjustments')
        self.reset.setToolTip('Restore all sliders and the tone curve to their starting values')
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
        self.restore_crop = W.QPushButton('Reset crop — show full image'); self.restore_crop.clicked.connect(self.restore_full_frame)
        crop_layout.addRow(self.apply_crop); crop_layout.addRow(self.restore_crop)
        self.crop_group.setEnabled(False); sidebar.addWidget(self.crop_group)
        next_export = W.QPushButton('Continue to step 5: Export →')
        next_export.clicked.connect(lambda: self.show_step(self.step_export)); sidebar.addWidget(next_export)
        outer_sidebar.addSpacing(20)
        self.step_export = W.QGroupBox(); self.step_export.setAccessibleName('5. Export'); self.step_export.setObjectName('stepExport')
        self.step_export.setEnabled(False); outer_sidebar.addWidget(self.step_export)
        sidebar = W.QVBoxLayout(self.step_export)
        section_title = W.QLabel('5. Export'); section_title.setObjectName('sectionTitle'); section_title.setWordWrap(True); sidebar.addWidget(section_title)
        export_hint = W.QLabel('Save the adjusted picture as TIFF, PNG or JPG, or keep linear data as FITS. Choose the format and filename in the save window.'); export_hint.setWordWrap(True); sidebar.addWidget(export_hint)
        self.export = W.QPushButton('5. Export image…'); self.export.setEnabled(False); self.export.clicked.connect(self.save); sidebar.addWidget(self.export)
        self.save_stack_button=W.QPushButton('Save stacked FITS…');self.save_stack_button.setToolTip('Save the full original combined frame without crop, display adjustments or labels.');self.save_stack_button.clicked.connect(self.save_stacked_fits);sidebar.addWidget(self.save_stack_button)
        self.export_labels_button=W.QPushButton('Export labeled image…');self.export_labels_button.clicked.connect(self.export_labeled_image);sidebar.addWidget(self.export_labels_button)
        right = W.QVBoxLayout(); layout.addLayout(right, 3)
        zoom_row = W.QHBoxLayout(); right.addLayout(zoom_row)
        self.zoom_out = W.QPushButton('−'); self.zoom_out.setFixedWidth(36); zoom_row.addWidget(self.zoom_out)
        self.zoom_in = W.QPushButton('+'); self.zoom_in.setFixedWidth(36); zoom_row.addWidget(self.zoom_in)
        self.zoom_fit = W.QPushButton('Fit'); zoom_row.addWidget(self.zoom_fit)
        self.zoom_actual = W.QPushButton('100%'); zoom_row.addWidget(self.zoom_actual)
        self.reset_crop_preview=W.QPushButton('Reset crop');self.reset_crop_preview.setToolTip('Remove all cropping and aspect-ratio restrictions; keep image adjustments.');self.reset_crop_preview.clicked.connect(self.restore_full_frame);self.reset_crop_preview.setEnabled(False);zoom_row.addWidget(self.reset_crop_preview)
        self.auto_sky_preview=W.QPushButton('Auto sky');self.auto_sky_preview.setToolTip('Suggest a darker sky background; Undo restores the previous view.');self.auto_sky_preview.clicked.connect(self.auto_sky_background);self.auto_sky_preview.setEnabled(False);zoom_row.addWidget(self.auto_sky_preview)
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
        self.log = W.QPlainTextEdit(); self.log.setMaximumBlockCount(2000); self.log.setReadOnly(True); right.addWidget(self.log, 1)
        self.timer = QtCore.QTimer(); self.timer.setSingleShot(True); self.timer.timeout.connect(self.request_preview)
        self.history_timer=QtCore.QTimer();self.history_timer.setSingleShot(True);self.history_timer.timeout.connect(self.commit_history)
        toolbar=self.addToolBar('Projects and history');toolbar.setMovable(False)
        self.new_project_action=QtGui.QAction('New Project',self);self.new_project_action.setShortcut(QtGui.QKeySequence.StandardKey.New);self.new_project_action.triggered.connect(self.new_project)
        self.open_project_action=QtGui.QAction('Open project…',self);self.open_project_action.setShortcut(QtGui.QKeySequence.StandardKey.Open);self.open_project_action.triggered.connect(self.open_project_dialog)
        self.save_project_action=QtGui.QAction('Save project',self);self.save_project_action.setShortcut(QtGui.QKeySequence.StandardKey.Save);self.save_project_action.triggered.connect(self.save_project_dialog)
        self.save_as_action=QtGui.QAction('Save project as…',self);self.save_as_action.setShortcut(QtGui.QKeySequence.StandardKey.SaveAs);self.save_as_action.triggered.connect(lambda: self.save_project_dialog(save_as=True))
        self.undo_action=QtGui.QAction('Undo',self);self.undo_action.setShortcut(QtGui.QKeySequence.StandardKey.Undo);self.undo_action.triggered.connect(self.undo_edit)
        self.redo_action=QtGui.QAction('Redo',self);self.redo_action.setShortcuts(QtGui.QKeySequence.keyBindings(QtGui.QKeySequence.StandardKey.Redo));self.redo_action.triggered.connect(self.redo_edit)
        for action in (self.new_project_action,self.open_project_action,self.save_project_action,self.undo_action,self.redo_action):toolbar.addAction(action)
        spacer=W.QWidget();spacer.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Preferred);toolbar.addWidget(spacer)
        self.labels_action=QtGui.QAction('Labels && Objects…',self);self.labels_action.setToolTip('Open an image to add labels');toolbar.addAction(self.labels_action)
        self.labels_panel=LabelsPanel();self.labels_dock=W.QDockWidget('Labels && Objects',self);self.labels_dock.setWidget(self.labels_panel);self.addDockWidget(QtCore.Qt.RightDockWidgetArea,self.labels_dock);self.labels_dock.hide()
        self.labels_action.triggered.connect(lambda:self.labels_dock.setVisible(not self.labels_dock.isVisible()))
        self.labels_panel.identify.connect(self.identify_objects)
        self.labels_panel.place.connect(self.begin_label);self.preview.annotationPlaced.connect(self.place_label)
        self.labels_panel.changed.connect(self.edit_label);self.labels_panel.remove.connect(self.remove_label);self.labels_panel.clear.connect(self.clear_labels)
        self.labels_panel.visible.toggled.connect(self.set_labels_visible);self.labels_panel.list.currentRowChanged.connect(self.select_label)
        file_menu=self.menuBar().addMenu('File');file_menu.addActions([self.new_project_action,self.open_project_action,self.save_project_action,self.save_as_action])
        edit_menu=self.menuBar().addMenu('Edit');edit_menu.addActions([self.undo_action,self.redo_action])
        self.community_panel = W.QFrame(); self.community_panel.setObjectName('communityPanel')
        community_layout = W.QVBoxLayout(self.community_panel); community_layout.setContentsMargins(10,8,10,8); community_layout.setSpacing(8)
        buttons = W.QHBoxLayout(); buttons.addStretch()
        self.coffee_button = W.QPushButton('Buy the Developer a Coffee')
        self.feedback_button = W.QPushButton('Report a Bug / Suggest a Fix')
        for button in (self.coffee_button,self.feedback_button):
            button.setMinimumHeight(32);buttons.addWidget(button)
        self.coffee_button.setToolTip('Open the developer’s Cash App page in your browser')
        self.coffee_button.clicked.connect(lambda: self.open_community_link(community_links.COFFEE_URL))
        self.feedback_button.setToolTip('Send a bug report or suggestion to the developer')
        self.feedback_button.clicked.connect(self.show_feedback)
        buttons.addStretch(); community_layout.addLayout(buttons)
        self.planner_banner = W.QLabel();self.update_planner_banner()
        self.planner_banner.setAlignment(QtCore.Qt.AlignCenter); self.planner_banner.setWordWrap(True)
        self.planner_banner.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        self.planner_banner.setOpenExternalLinks(False)
        self.planner_banner.linkActivated.connect(self.open_community_link)
        community_layout.addWidget(self.planner_banner)
        root_layout.addWidget(self.community_panel)
        settings_menu=self.menuBar().addMenu('Settings');theme_menu=settings_menu.addMenu('Theme')
        self.chime_action=QtGui.QAction('Play sound when stacking finishes',self);self.chime_action.setCheckable(True);self.chime_action.setChecked(self.settings_store.value('notifications/stack_sound',True,type=bool));settings_menu.addAction(self.chime_action)
        self.chime_action.toggled.connect(self.save_chime_preference)
        self.privacy_action=QtGui.QAction('Privacy Policy',self);self.privacy_action.triggered.connect(lambda:show_privacy(self));settings_menu.addAction(self.privacy_action)
        self.theme_actions={};self.theme_group=QtGui.QActionGroup(self);self.theme_group.setExclusive(True)
        for name in THEMES:
            action=QtGui.QAction(name,self);action.setCheckable(True);action.setChecked(name==self.theme_name)
            action.triggered.connect(lambda checked=False,choice=name:self.set_theme(choice))
            self.theme_group.addAction(action);theme_menu.addAction(action);self.theme_actions[name]=action
        self.about_action=QtGui.QAction('About',self);self.about_action.triggered.connect(self.show_about)
        self.menuBar().addAction(self.about_action)
        self.update_actions()
        self.statusBar().showMessage('Ready • CPU processing • Originals are preserved')
        for signal in (self.files.model().rowsInserted,self.files.model().rowsRemoved,self.files.model().modelReset,self.files.model().dataChanged,self.files.model().rowsMoved):signal.connect(self.invalidate_file_cache)
        if self.settings_store.value('processing/use_gpu',False,type=bool):self.use_gpu.setChecked(True)
    def update_planner_banner(self):
        color=THEMES[self.theme_name]['link'];url=community_links.PLANNER_URL
        self.planner_banner.setText(f'Plan tonight\'s observing at <a style="color:{color}; text-decoration:underline" href="{url}">{url}</a>')

    def set_theme(self,name):
        self.theme_name=apply_theme(W.QApplication.instance(),name)
        self.settings_store.setValue('appearance/theme',self.theme_name);self.settings_store.sync()
        self.theme_actions[self.theme_name].setChecked(True);self.update_planner_banner()
        if hasattr(self,'_clipping_warning'):self.clip_summary.setStyleSheet('color: '+THEMES[self.theme_name]['warning' if self._clipping_warning else 'fg']+';')

    def show_about(self):
        box=W.QMessageBox(self);box.setWindowTitle('About Easy Astro Studio');box.setTextFormat(QtCore.Qt.RichText)
        box.setText(
            '<h2>Easy Astro Studio</h2><p>Version '+VERSION+'</p><p>by Astrivanta ©</p>'
            '<p>Align and stack FITS exposures, adjust and crop images, identify and label catalog objects, and export FITS, TIFF, PNG or JPEG.</p>'
            '<p>Catalog data: OpenNGC (Mattia Verga and contributors) and HYG v4.1 (David Nash / Astronomy Nexus and contributors), CC BY-SA 4.0. Full attribution and license are bundled in assets/catalogs.</p>'
            '<p>Gaia matching uses ESA Gaia DR3 and DPAC data. Candidate matches require an existing sky solution.</p>'
            '<p>Privacy contact: starsandfits@gmail.com</p>')
        box.setStandardButtons(W.QMessageBox.Ok);privacy=box.addButton('Privacy Policy',W.QMessageBox.ActionRole);privacy.clicked.connect(lambda:show_privacy(box))
        try:box.exec()
        finally:box.deleteLater()

    def review_exposures(self):
        if self.worker is not None or self.project_worker is not None or not self.files.count():return
        paths=[self.files.item(i).text() for i in range(self.files.count())]
        selected=self.files.currentItem().text() if self.files.currentItem() else paths[0]
        dialog=FrameReviewDialog(paths,self.bayer.currentText(),self,selected)
        if dialog.exec()==W.QDialog.Accepted and dialog.chosen_path in paths:
            index=paths.index(dialog.chosen_path)
            item=self.files.takeItem(index);self.files.insertItem(0,item);self.files.setCurrentRow(0)
            self.log.appendPlainText('Alignment reference selected: '+Path(dialog.chosen_path).name)
            self.update_actions()

    def show_feedback(self):
        dialog=FeedbackDialog(self)
        if dialog.exec()==W.QDialog.Accepted:
            self.statusBar().showMessage('Thank you! Your feedback was sent.',10000)

    def open_community_link(self, destination):
        if destination and not QtGui.QDesktopServices.openUrl(QtCore.QUrl(destination)):
            W.QMessageBox.information(self, 'Could not open link',
                'Windows could not open this link. You can copy it into your browser or email app:\n\n'+destination)

    def zoom_changed(self,scale):
        self.zoom_label.setText(f'{scale*100:.0f}%')
        if hasattr(self,'timer'): self.schedule_preview()
    def show_step(self, widget):
        position = widget.mapTo(self.sidebar_scroll.widget(), QtCore.QPoint(0, 0)).y()
        self.sidebar_scroll.verticalScrollBar().setValue(position)
    def fits_folder(self):
        saved=str(self.settings_store.value('files/last_fits_directory','') or '')
        if sys.platform=='darwin':return saved or QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
        folder=Path(saved)
        if str(folder) not in ('','.'):
            while not folder.is_dir() and folder.parent!=folder:folder=folder.parent
            if folder.is_dir():return str(folder)
        return QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)

    def remember_fits_folder(self,path):
        self.settings_store.setValue('files/last_fits_directory',str(Path(path).parent));self.settings_store.sync()

    def choose_fits(self, multiple=False):
        title = 'Select individual exposures' if multiple else 'Open image or FITS stack'
        folder = self.fits_folder()
        if sys.platform == 'darwin':
            paths = select_files(title, ['fit','fits'] if multiple else ['fit','fits','png','jpg','jpeg'], multiple=multiple,
                                 initial_directory=folder or None)
        elif multiple:
            paths, _ = W.QFileDialog.getOpenFileNames(self, title, folder, 'FITS (*.fit *.fits *.FIT *.FITS)')
        else:
            path, _ = W.QFileDialog.getOpenFileName(self, title, folder, 'Images (*.fit *.fits *.FIT *.FITS *.png *.jpg *.jpeg *.PNG *.JPG *.JPEG)')
            paths = [path] if path else []
        if paths:
            self.settings_store.setValue('files/last_fits_directory', str(Path(paths[0]).parent))
            self.settings_store.sync()
        return paths

    def add_files(self):
        paths = self.choose_fits(multiple=True)
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
            selected = self.choose_fits()
            path = selected[0] if selected else ''
            if not path: return
            self.remember_fits_folder(path)
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
        self.progress_text.setText('Loading image…' if single else 'Preparing exposures…')
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
        self.use_gpu.setEnabled(True)
        self.update_actions()
    def loaded(self, linear, header):
        self._history_ready=False
        self.solution_header=None
        self.annotations=[];self.labels_visible=True;self.refresh_labels()
        self.project_path=None
        self.source_paths=list(getattr(self,'pending_source_paths',[]))
        self.applied_crop=(0,0,linear.shape[1],linear.shape[0])
        self.source_name = getattr(self, 'pending_source_name', 'image')
        self.original_linear, self.original_header = linear, header.copy()
        self.linear, self.header = linear, header
        self.reset_crop_controls()
        self.background = self.make_background(linear)
        self.curve.set_values(NEUTRAL_CURVE)
        for name,slider in self.sliders.items():
            value=0 if header.get('EASRASTR') and name in ('Stretch','Black percentile ×100') else self.slider_defaults[name]
            old=slider.blockSignals(True);slider.setValue(value);slider.blockSignals(old);self.slider_rows[name].position_value()
        self.export.setEnabled(True)
        self.step_adjust.setEnabled(True); self.step_export.setEnabled(True)
        self.next_adjust.setEnabled(True)
        QtCore.QTimer.singleShot(0, lambda: self.show_step(self.step_adjust) if self.linear is not None else None)
        self.progress_bar.setRange(0, 100); self.progress_bar.setValue(100)
        self.progress_text.setText("Complete • 100% • 0 remaining")
        if isinstance(self.worker,Worker) and not self.worker.single:
            accepted=engine.frame_count(header);skipped=max(0,len(self.pending_source_paths)-accepted)
            summary=f'Stacking complete: {accepted} exposures combined; {skipped} skipped.'
            self.progress_text.setText(summary);self.log.appendPlainText(summary);self.statusBar().showMessage(summary)
            W.QApplication.alert(self,0)
            if self.chime_action.isChecked():
                try:self.play_stack_chime()
                except Exception as exc:self.log.appendPlainText('Completion sound unavailable: '+str(exc))
        self.log.appendPlainText(engine.image_summary(linear, header))
        self.histogram_panel.show()
        self.update_preview()
        self.history.reset(self.edit_state());self._history_ready=True
        self._saved_signature=None if self.worker is not None and not self.worker.single else self.project_signature()
        self.update_actions()
    def toggle_gpu(self, enabled):
        self.settings_store.setValue('processing/use_gpu',bool(enabled));self.settings_store.sync()
        self._preview_generation+=1
        self.gpu = None
        if enabled:
            try:
                from gpu import create_gpu_processor
                self.gpu = create_gpu_processor()
                scope = 'image adjustments' if sys.platform == 'darwin' else 'row combining and adjustments'
                self.log.appendPlainText('GPU enabled for '+scope+': '+self.gpu.name)
                self.statusBar().showMessage(self.gpu.name+' • '+('Stacking/alignment: CPU' if sys.platform == 'darwin' else 'Alignment: CPU'))
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
        self.background = self.make_background(self.linear)
        self.reset_crop_controls()
        self.log.appendPlainText(f'Crop applied: {self.linear.shape[1]} × {self.linear.shape[0]} pixels. Restore full frame is available.')
        self.update_preview()
        self.commit_history()
    def restore_full_frame(self):
        if self.linear is None or self.worker is not None or self.project_worker is not None:return
        self.commit_history()
        self._restoring=True
        try:
            self.timer.stop();self.history_timer.stop();self.preview.mode=None
            old=self.crop_ratio.blockSignals(True);self.crop_ratio.setCurrentText('Free');self.crop_ratio.blockSignals(old)
            self.applied_crop=(0,0,self.original_linear.shape[1],self.original_linear.shape[0])
            self.linear,self.header=self.original_linear,self.original_header.copy()
            self.background=self.make_background(self.linear)
            self.reset_crop_controls();self.update_preview();self.preview.fit_image()
        finally:self._restoring=False
        self.log.appendPlainText('Crop reset: full image restored and aspect ratio set to Free. Adjustments and labels preserved.')
        self.commit_history();self.update_actions()
    def auto_sky_background(self):
        if self.linear is None or self.worker is not None or self.project_worker is not None:return
        self.commit_history()
        self._restoring=True
        try:
            old=self.baseline.blockSignals(True);self.baseline.setChecked(False);self.baseline.blockSignals(old)
            proposed=engine.auto_sky_adjustments(self.linear,self.settings(),self.background,self.preview_request()[1])
            for name,value in [('Stretch',int(proposed[0])),('Brightness (stops ×100)',round(proposed[6]*100)),('Sky background %',round(proposed[8]*100))]:
                slider=self.sliders[name];old=slider.blockSignals(True);slider.setValue(value);slider.blockSignals(old);self.slider_rows[name].position_value()
            self.timer.stop();self.history_timer.stop();self.update_preview()
        finally:self._restoring=False
        self.commit_history();self.log.appendPlainText('Auto sky background: suggested darker display applied. Source FITS data and black point are unchanged; Undo restores the prior view. Faint nebulosity can look darker.')

    def reset_tone_curve(self):
        if self.linear is None:return
        self.commit_history();self.curve.set_values(NEUTRAL_CURVE);self.update_preview();self.commit_history()
    def is_preview_interactive(self):
        return any(slider.isSliderDown() for slider in self.sliders.values()) or self.curve.dragging
    def reset_adjustments(self):
        self.commit_history()
        for name, slider in self.sliders.items():
            slider.setValue(0 if self.header.get('EASRASTR') and name in ('Stretch','Black percentile ×100') else self.slider_defaults[name])
        self.baseline.setChecked(False)
        self.curve.set_values(NEUTRAL_CURVE)
        self.timer.stop()
        self.update_preview()
        self.commit_history()
    def schedule_preview(self):
        self._preview_generation+=1;self._preview_pending=True
        if not self.timer.isActive():self.timer.start(16)
        self.schedule_history()
    def settings(self):
        v={name:slider.value() for name,slider in self.sliders.items()}
        if self.baseline.isChecked():return ((0,0,1,0,0,(1,1,1),0,1,0) if self.header.get('EASRASTR') else (30,.1,1,0,0,(1,1,1),0,1,0))+(0,0,1,NEUTRAL_CURVE,0,0)
        return (v['Stretch'],v['Black percentile ×100']/100,v['Saturation %']/100,v['Noise smoothing ×100']/100,
                v['Background correction %']/100,tuple(v[name]/100 for name in ('Red balance %','Green balance %','Blue balance %')),
                v['Brightness (stops ×100)']/100,v['Contrast %']/100,v['Sky background %']/100,v['Midtones %']/100,v['Star-preserving noise reduction %']/100,v['Star protection %']/100,tuple(self.curve.values),v['Sky brightness (stops ×100)']/100,v['Background neutralization %']/100)
    def preview_request(self):
        h,w,_=self.linear.shape
        scale=max(self.preview.transform().m11(),.01)
        if self.preview.item.pixmap().isNull():scale=min(self.preview.viewport().width()/w,self.preview.viewport().height()/h)
        step=max(1,int(np.floor(1/max(scale,.01))))
        size=(max(1,w//step),max(1,h//step))
        if self.is_preview_interactive():
            factor=max(1,max(size)/768);size=(max(1,round(size[0]/factor)),max(1,round(size[1]/factor)))
        return self.linear,size,self.settings(),self.background,self.gpu,self.mark_clipping.isChecked()

    def update_preview(self):
        # Initial load and explicit crop/reset operations keep their immediate
        # behavior. Slider/timer work uses the asynchronous path below.
        if self.linear is None:return
        self._preview_generation+=1;self._preview_pending=False
        self.apply_preview(self.preview_renderer.render(*self.preview_request()))
        self.report_gpu_failure()

    def request_preview(self):
        self.timer.stop()
        if self.linear is None or self._close_after_preview or self.project_worker is not None:return
        self._preview_pending=True
        if self.preview_worker is not None:return
        self._preview_pending=False
        self.preview_worker=PreviewWorker(self.preview_renderer,self._preview_generation,self.preview_request())
        self.preview_worker.interactive=self.is_preview_interactive()
        self.preview_worker.result.connect(self.preview_ready)
        self.preview_worker.failed.connect(self.preview_failed)
        self.preview_worker.finished.connect(self.preview_finished)
        self.preview_worker.start()

    def preview_ready(self,generation,result):
        same_source=self.linear is not None and self.preview_worker is not None and self.preview_worker.request[0] is self.linear
        if same_source and not self._close_after_preview and (generation==self._preview_generation or (getattr(self.preview_worker,'interactive',False) and self.is_preview_interactive())):
            self.apply_preview(result);self.report_gpu_failure()

    def preview_failed(self,generation,text):
        if generation==self._preview_generation:self.log.appendPlainText('Preview failed: '+text)

    def preview_finished(self):
        self.preview_worker.deleteLater();self.preview_worker=None
        if self.linear is None:self.preview_renderer.clear()
        if self._close_after_preview:
            self._preview_pending=False;QtCore.QTimer.singleShot(0,self.close)
        elif self._preview_pending:self.request_preview()

    def apply_preview(self,result):
        self._displayed_preview_settings=result['settings']
        self.histogram.set_data(result['bins']);black,white=result['black'],result['white']
        self.clip_summary.setText(f'Black clipping: {black:.3f}% • White clipping: {white:.3f}% (preview)')
        self._clipping_warning=max(black,white)>.1
        self.clip_summary.setStyleSheet('color: '+THEMES[self.theme_name]['warning' if self._clipping_warning else 'fg']+';')
        pixels=result['pixels']
        image=QtGui.QImage(pixels.data,pixels.shape[1],pixels.shape[0],pixels.strides[0],QtGui.QImage.Format_RGB888).copy()
        self.preview.set_image(image,result['source_size'])
        self.refresh_label_overlay()
        self.zoom_label.setText(f'{self.preview.transform().m11()*100:.0f}%'+(' • Live draft' if self.is_preview_interactive() else ''))

    def identify_objects(self):
        if self.linear is None or self.worker is not None or self.project_worker is not None:return
        header=self.solution_header if self.solution_header is not None else self.original_header
        source=Path(self.source_paths[0]).name if len(self.source_paths)==1 else self.source_name
        dialog=IdentifyDialog(self.original_linear,header,self.applied_crop,self,source_name=source,preview_image=self.preview.item.pixmap().toImage())
        try:
            if dialog.exec()==W.QDialog.Accepted:self.add_identified_objects(dialog.selected_rows(),dialog.solution)
        finally:dialog.deleteLater()
    def add_identified_objects(self,rows,solution=None):
        self.commit_history();seen={a.get('catalog_id') for a in self.annotations if a.get('catalog_id')};added=0
        for row in rows:
            if row['id'] in seen or len(self.annotations)>=500:continue
            if not (0<=row['x']<self.original_linear.shape[1] and 0<=row['y']<self.original_linear.shape[0]):continue
            self.annotations.append(dict(kind='Circle',text=row['name'][:200],color=self.labels_panel.color.currentData(),size=self.labels_panel.size.value(),x=float(row['x']),y=float(row['y']),catalog_id=row['id']))
            seen.add(row['id']);added+=1
        if solution is not None:self.solution_header=solution.copy()
        self.labels_visible=True;self.refresh_labels();self.commit_history();self.update_actions()
        self.log.appendPlainText(f'Added {added} catalog labels. Existing duplicates were kept once; projects support up to 500 labels. Check positions against visible stars.')

    def make_background(self,image):
        model=engine.background_model(image)
        return dict(display_encoded=True,background=model) if self.header.get('EASRASTR') else model
    def save_chime_preference(self,value):
        self.settings_store.setValue('notifications/stack_sound',value);self.settings_store.sync()
    def play_stack_chime(self):
        if sys.platform=='win32':
            import winsound
            winsound.PlaySound('SystemAsterisk',winsound.SND_ALIAS|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
        else:W.QApplication.beep()
    def refresh_label_overlay(self):
        if not hasattr(self,'preview'):return
        self.preview.annotations=self.annotations;self.preview.annotations_visible=self.labels_visible
        self.preview.annotation_crop=getattr(self,'applied_crop',(0,0,0,0))
        if getattr(self,'original_linear',None) is not None:self.preview.annotation_width=self.original_linear.shape[1]
        self.preview.viewport().update()
    def refresh_labels(self):
        if not hasattr(self,'labels_panel'):return
        row=self.labels_panel.list.currentRow();self.labels_panel.list.blockSignals(True);self.labels_panel.list.clear()
        self.labels_panel.list.addItems([f"{a['kind']}: {a['text'] or '(shape)'}" for a in self.annotations])
        self.labels_panel.list.setCurrentRow(min(max(0,row),len(self.annotations)-1));self.labels_panel.list.blockSignals(False)
        old=self.labels_panel.visible.blockSignals(True);self.labels_panel.visible.setChecked(self.labels_visible);self.labels_panel.visible.blockSignals(old)
        self.refresh_label_overlay()
    def begin_label(self):
        if self.linear is None:return
        if len(self.annotations)>=500:W.QMessageBox.information(self,'Labels','Maximum 500 labels per project.');return
        if self.labels_panel.kind.currentText()=='Text' and not self.labels_panel.text.text().strip():
            self.labels_panel.text.setFocus();return
        self.preview.mode=None;self.preview.annotation_placing=True
        self.statusBar().showMessage('Click the image to place the label. Escape cancels placement.')
    def keyPressEvent(self,event):
        if event.key()==QtCore.Qt.Key_Escape and self.preview.annotation_placing:
            self.preview.annotation_placing=False;self.statusBar().showMessage('Label placement cancelled');event.accept();return
        super().keyPressEvent(event)
    def place_label(self,x,y):
        if self.linear is None or self.worker is not None or self.project_worker is not None:return
        self.commit_history();a=self.labels_panel.values();ox,oy,_,_=self.applied_crop
        a.update(x=max(ox,min(ox+self.linear.shape[1]-1,x+ox)),y=max(oy,min(oy+self.linear.shape[0]-1,y+oy)))
        self.annotations.append(a);self.labels_visible=True;self.refresh_labels();self.labels_panel.list.setCurrentRow(len(self.annotations)-1);self.commit_history()
        self.statusBar().showMessage('Label added')
    def select_label(self,row):
        if not 0<=row<len(self.annotations):return
        a=self.annotations[row];p=self.labels_panel
        p.kind.setCurrentText(a['kind']);p.text.setText(a['text']);p.color.setCurrentIndex(p.color.findData(a['color']));p.size.setValue(a['size'])
    def edit_label(self):
        row=self.labels_panel.list.currentRow()
        if not 0<=row<len(self.annotations):return
        self.commit_history();self.annotations[row].update(self.labels_panel.values());self.refresh_labels();self.commit_history()
    def remove_label(self):
        row=self.labels_panel.list.currentRow()
        if not 0<=row<len(self.annotations):return
        self.commit_history();self.annotations.pop(row);self.refresh_labels();self.commit_history()
    def clear_labels(self):
        if not self.annotations:return
        if W.QMessageBox.question(self,'Clear labels?','Remove all labels? You can undo this change.',W.QMessageBox.Yes|W.QMessageBox.No,W.QMessageBox.No)!=W.QMessageBox.Yes:return
        self.commit_history();self.annotations=[];self.refresh_labels();self.commit_history()
    def set_labels_visible(self,value):
        self.commit_history();self.labels_visible=value;self.refresh_label_overlay();self.commit_history()
    def save_stacked_fits(self):
        if self.original_linear is None or not self.save_stack_button.isEnabled():return
        initial=engine.export_basename(self.original_header,self.source_name)+'_stacked.fits'
        if sys.platform=='darwin':
            path=select_save_file('Save full linear stack',initial,['fits','fit'])
        else:
            path,_=W.QFileDialog.getSaveFileName(self,'Save full linear stack',initial,'FITS (*.fits)')
        if not path:return
        if Path(path).suffix.lower() not in ('.fit','.fits'):path+='.fits'
        try:
            engine.save(path,self.original_linear,None,self.original_header);self.log.appendPlainText('Saved full linear stack: '+path)
        except Exception as exc:W.QMessageBox.critical(self,'Save stack failed',str(exc))
    def labeled_image(self):
        rendered=engine.render(self.linear,*self.settings(),model=self.background,gpu=self.gpu)
        pixels=np.ascontiguousarray(np.round(rendered*255).astype(np.uint8));h,w=pixels.shape[:2]
        image=QtGui.QImage(pixels.data,w,h,pixels.strides[0],QtGui.QImage.Format_RGB888).copy()
        painter=QtGui.QPainter(image)
        if self.labels_visible:paint_annotations(painter,self.annotations,self.applied_crop,self.original_linear.shape[1])
        painter.end();return image
    def export_labeled_image(self):
        if self.linear is None:return
        initial=engine.export_basename(self.header,self.source_name)+'_labeled.png'
        if sys.platform=='darwin':
            path=select_export_file(initial,formats=(('PNG',('png',)),('JPEG',('jpg','jpeg'))))
            selected='PNG'
        else:
            path,selected=W.QFileDialog.getSaveFileName(self,'Export labeled copy',initial,'PNG (*.png);;JPEG (*.jpg)')
        if not path:return
        if not Path(path).suffix:path+='.jpg' if 'JPEG' in selected else '.png'
        if Path(path).suffix.lower() not in ('.png','.jpg','.jpeg'):
            W.QMessageBox.information(self,'Export labeled image','Choose PNG or JPG.');return
        try:
            if not self.labeled_image().save(path,quality=95):raise OSError('Could not write image')
            self.log.appendPlainText('Saved labeled copy: '+path)
        except Exception as exc:W.QMessageBox.critical(self,'Export labels failed',str(exc))

    def save(self):
        if sys.platform == 'darwin':
            path = select_export_file(engine.export_basename(self.header, self.source_name)+'.tif')
        else:
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
        return dict(sliders={name:slider.value() for name,slider in self.sliders.items()},curve=list(self.curve.values),compare=self.baseline.isChecked(),
                    annotations=copy.deepcopy(self.annotations),labels_visible=self.labels_visible,applied_crop=list(self.applied_crop),selection=list(self.crop_bounds),ratio=self.crop_ratio.currentText(),guides=self.guides.currentText())
    def invalidate_file_cache(self,*args):self._files_json=None
    def project_signature(self):
        if self._files_json is None:self._files_json=json.dumps([self.files.item(i).text() for i in range(self.files.count())])
        return json.dumps(dict(state=self.edit_state(),bayer=self.bayer.currentText(),identification_wcs=self.solution_header.tostring(sep='\n',endcard=True,padding=False) if self.solution_header is not None else None),sort_keys=True)+'|'+self._files_json
    def schedule_history(self):
        if self._history_ready and not self._restoring:
            if self.preview.mode is not None or self.is_preview_interactive():self.history_timer.stop()
            else:self.history_timer.start(400)
            self.update_actions()
    def commit_history(self):
        if not self._history_ready or self._restoring:return
        self.history_timer.stop();self.history.push(self.edit_state());self.update_actions()
    def update_actions(self):
        if not hasattr(self,'undo_action'):return
        busy=self.worker is not None or self.project_worker is not None
        self.advanced_toggle.setText('Advanced: sky, color and noise'+(' • active' if any(self.sliders[name].value()!=self.slider_defaults[name] for name in self.advanced_names) else ''))
        self.review.setEnabled(not busy and self.files.count()>0)
        self.run.setEnabled(not busy and self.files.count()>=2);self.next_stack.setEnabled(not busy and self.files.count()>=2)
        self.reference_label.setText('Reference: '+Path(self.files.item(0).text()).name if self.files.count() else 'Reference: first exposure in the list')
        ready=self.linear is not None and self._history_ready
        self.auto_sky_preview.setEnabled(ready and not busy);self.auto_sky.setEnabled(ready and not busy)
        self.reset_crop_preview.setEnabled(ready and not busy);self.restore_crop.setEnabled(ready and not busy)
        self.labels_action.setEnabled(ready and not busy);self.labels_panel.setEnabled(ready and not busy)
        if busy:self.preview.annotation_placing=False
        self.save_stack_button.setEnabled(ready and not busy and not self.header.get('EASRASTR',False) and engine.frame_count(self.original_header)>1)
        self.export_labels_button.setEnabled(ready and not busy and bool(self.annotations))
        pending=ready and self.edit_state()!=self.history.states[self.history.index]
        self.undo_action.setEnabled(ready and not busy and (self.history.can_undo or pending))
        self.redo_action.setEnabled(ready and not busy and self.history.can_redo and not pending)
        self.save_project_action.setEnabled(ready and not busy);self.save_as_action.setEnabled(ready and not busy)
        self.open_project_action.setEnabled(not busy)
        self.new_project_action.setEnabled(not busy)
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
                self.applied_crop=rect;self.background=self.make_background(self.linear)
            self.curve.set_values(state.get('curve',list(NEUTRAL_CURVE)))
            self.annotations=copy.deepcopy(state.get('annotations',[]));self.labels_visible=state.get('labels_visible',True);self.refresh_labels()
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
    def new_project(self,confirmed=False):
        if self.worker is not None or self.project_worker is not None:return
        self.commit_history()
        if not confirmed and self._dirty and self.ask_on_close:
            choice=W.QMessageBox.question(self,'New Project','Save the current project before starting a new one?',
                W.QMessageBox.Save|W.QMessageBox.Discard|W.QMessageBox.Cancel,W.QMessageBox.Save)
            if choice==W.QMessageBox.Cancel:return
            if choice==W.QMessageBox.Save:
                self.save_project_dialog(after_save=self._clear_project)
                return
        elif self.linear is None and self.files.count() and self.ask_on_close:
            if W.QMessageBox.question(self,'New Project','Clear the current exposure list?',
                    W.QMessageBox.Discard|W.QMessageBox.Cancel,W.QMessageBox.Cancel)!=W.QMessageBox.Discard:return
        self._clear_project()

    def _clear_project(self):
        self.timer.stop();self.history_timer.stop();self._history_ready=False
        self._preview_generation+=1;self._preview_pending=False
        self.solution_header=None
        self.annotations=[];self.labels_visible=True;self.refresh_labels();self.labels_dock.hide();self.preview.annotation_placing=False
        blocker=QtCore.QSignalBlocker(self.curve);self.curve.set_values(NEUTRAL_CURVE);del blocker
        if self.preview_worker is None:self.preview_renderer.clear()
        self.linear=self.header=self.rendered=None
        self.original_linear=self.original_header=self.background=None
        self.project_path=None;self._saved_signature=None;self._dirty=False;self._after_io=None
        self.source_paths=[];self.pending_source_paths=[];self.source_name='image';self.pending_source_name='image'
        self.history=EditHistory();self.applied_crop=(0,0,0,0);self.crop_bounds=(0,0,0,0)
        self.files.clear()
        for name,slider in self.sliders.items():
            blocker=QtCore.QSignalBlocker(slider);slider.setValue(self.slider_defaults[name]);del blocker
            self.slider_rows[name].position_value()
        for widget,value in ((self.baseline,False),(self.mark_clipping,False),(self.crop_ratio,'Free'),(self.guides,'Thirds + rulers')):
            blocker=QtCore.QSignalBlocker(widget)
            if isinstance(value,bool):widget.setChecked(value)
            else:widget.setCurrentText(value)
            del blocker
        self.preview.item.setPixmap(QtGui.QPixmap());self.preview.item.setTransform(QtGui.QTransform())
        self.preview.source_size=None;self.preview.selection_pixels=None;self.preview.mode=None
        self.preview.pan_start=None;self.preview.ratio=None;self.preview.guide=self.guides.currentText();self.preview.fit_mode=True
        self.preview.resetTransform();self.preview.scene().setSceneRect(QtCore.QRectF());self.preview.viewport().update()
        self.zoom_label.setText('Fit');self.crop_dimensions.setText('No image loaded');self.crop_group.setEnabled(False)
        self.histogram.set_data(np.zeros((3,256),dtype=np.int64));self.histogram_panel.hide()
        self.clip_summary.setText('Black clipping: 0% • White clipping: 0%');self._clipping_warning=False
        self.step_adjust.setEnabled(False);self.step_export.setEnabled(False);self.export.setEnabled(False);self.next_adjust.setEnabled(False)
        self.progress_bar.setRange(0,100);self.progress_bar.setValue(0);self.progress_text.setText('Ready')
        self.log.clear();self.log.appendPlainText('New project. Select exposures or open an existing FITS stack.')
        self.setWindowTitle(self.base_title);self.update_actions();self.show_step(self.step_load)
        self.statusBar().showMessage('New project • '+('GPU adjustments enabled' if self.gpu is not None else 'CPU processing'))

    def allow_replace(self):
        self.commit_history()
        if not self._dirty or not self.ask_on_close:return True
        return W.QMessageBox.question(self,'Replace current image?','Unsaved project changes will be lost. Cancel and save the project first to keep them.',W.QMessageBox.Discard|W.QMessageBox.Cancel,W.QMessageBox.Cancel)==W.QMessageBox.Discard
    def project_manifest(self):
        self.commit_history()
        center=self.preview.mapToScene(self.preview.viewport().rect().center())
        return dict(state=self.edit_state(),identification_wcs=self.solution_header.tostring(sep='\n',endcard=True,padding=False) if self.solution_header is not None else None,source_name=self.source_name,source_files=self.source_paths,
                    input_files=[self.files.item(i).text() for i in range(self.files.count())],bayer=self.bayer.currentText(),
                    history=dict(states=copy.deepcopy(self.history.states),index=self.history.index),
                    view=dict(fit=self.preview.fit_mode,zoom=self.preview.transform().m11(),center=[center.x(),center.y()],
                              mark_clipping=self.mark_clipping.isChecked(),gpu=self.use_gpu.isChecked()))
    def save_project_dialog(self,checked=False,save_as=False,after_save=None):
        if self.linear is None or self.worker is not None or self.project_worker is not None:return
        path=None if save_as else self.project_path
        if not path:
            initial=str(Path(QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation))/(engine.export_basename(self.header,self.source_name)+'.astro'))
            if sys.platform == 'darwin':
                path = select_save_file('Save project', Path(initial).name, ['astro'])
            else:
                path,_=W.QFileDialog.getSaveFileName(self,'Save project',initial,'Easy Astro Studio project (*.astro)')
            if not path:return
            if Path(path).suffix.lower()!='.astro':path+='.astro'
        self.save_project_path(path,after_save)
    def save_project_path(self,path,after_save=None):
        self._after_io=after_save
        payload=(self.original_linear,self.original_header.copy(),self.project_manifest())
        self._start_project_io(path,payload)
    def open_project_dialog(self):
        if sys.platform == 'darwin':
            selected = select_files('Open saved project', ['astro'])
            path = selected[0] if selected else ''
        else:
            path,_=W.QFileDialog.getOpenFileName(self,'Open saved project','','Easy Astro Studio project (*.astro)')
        if path and self.allow_replace():self.open_project_path(path)
    def open_project_path(self,path):self._after_io=None;self._start_project_io(path,None)
    def _start_project_io(self,path,payload):
        if self.worker is not None or self.project_worker is not None:return
        self.timer.stop();self.history_timer.stop();self.preview.mode=None;self.preview.annotation_placing=False
        self._preview_generation+=1;self._preview_pending=False
        self.project_worker=ProjectWorker(str(path),payload)
        self._project_io_path=str(path)
        self._project_io_ok=False
        for widget in (self.step_equipment,self.step_load,self.step_stack,self.step_adjust,self.step_export,self.use_gpu,self.preview,self.zoom_in,self.zoom_out,self.zoom_fit,self.zoom_actual,self.mark_clipping):widget.setEnabled(False)
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
            for state in [meta['state'],*meta.get('history',{}).get('states',[])]:
                state['sliders'].setdefault('Background neutralization %',0)
                state['sliders'].setdefault('Sky brightness (stops ×100)',0)
                state['sliders'].setdefault('Sky background %',0);state.setdefault('annotations',[]);state.setdefault('labels_visible',True)
                state['sliders'].setdefault('Midtones %',0);state['sliders'].setdefault('Star-preserving noise reduction %',0);state['sliders'].setdefault('Star protection %',100);state.setdefault('curve',list(NEUTRAL_CURVE))
            self.validate_edit_state(meta['state'],linear.shape)
            for state in meta.get('history',{}).get('states',[]):self.validate_edit_state(state,linear.shape)
            self.loaded(linear,header)
            if meta.get('identification_wcs'):
                from astropy.io import fits
                self.solution_header=fits.Header.fromstring(meta['identification_wcs'],sep='\n')
            self.source_name=str(meta.get('source_name','image'))
            self.source_paths=list(meta.get('source_files',[]))
            self.files.clear()
            if sandboxed():
                if meta.get('input_files'):
                    self.log.appendPlainText('Project image restored. To stack the original exposures again, select them with Add exposures.')
            else:
                self.files.addItems(meta.get('input_files',[]))
            if self.bayer.findText(meta.get('bayer','Auto'))>=0:self.bayer.setCurrentText(meta.get('bayer','Auto'))
            self.apply_edit_state(meta['state'])
            if any(meta['state']['sliders'][name]!=self.slider_defaults[name] for name in self.advanced_names):self.advanced_toggle.setChecked(True)
            history=meta.get('history')
            if history:self.history.states=copy.deepcopy(history['states']);self.history.index=history['index']
            else:self.history.reset(self.edit_state())
            view=meta.get('view',{})
            self.mark_clipping.setChecked(bool(view.get('mark_clipping',False)))
            # An older saved project can seed the preference on first use,
            # but never override an explicit saved application preference.
            if not self.settings_store.contains('processing/use_gpu') and view.get('gpu',False):self.use_gpu.setChecked(True)
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
        self.step_equipment.setEnabled(True);self.step_load.setEnabled(True);self.step_stack.setEnabled(True)
        for widget in (self.use_gpu,self.preview,self.zoom_in,self.zoom_out,self.zoom_fit,self.zoom_actual,self.mark_clipping):widget.setEnabled(True)
        self.use_gpu.setEnabled(True)
        self.step_adjust.setEnabled(self.linear is not None);self.step_export.setEnabled(self.linear is not None)
        self.progress_bar.setRange(0,100);self.progress_bar.setValue(100 if self._project_io_ok else 0)
        self.update_actions()
        callback=self._after_io;self._after_io=None
        if callback:QtCore.QTimer.singleShot(0,callback)
        elif self.linear is not None:self.schedule_preview()
    def closeEvent(self, event):
        if self.project_worker is not None:
            self.log.appendPlainText('Project save/load is in progress. Close again after it finishes.');event.ignore();return
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption();self.log.appendPlainText('Cancelling. Close again after processing stops.');event.ignore();return
        self.commit_history()
        if self._dirty and self.ask_on_close and not self._close_after_preview:
            result=W.QMessageBox.question(self,'Save project before closing?','Save your image and editing state as a project before closing?',W.QMessageBox.Save|W.QMessageBox.Discard|W.QMessageBox.Cancel,W.QMessageBox.Save)
            if result==W.QMessageBox.Cancel:event.ignore();return
            if result==W.QMessageBox.Save:
                event.ignore();self.save_project_dialog(after_save=self.close);return
        self.timer.stop();self._preview_pending=False
        if self.preview_worker is not None:
            self._close_after_preview=True;self.setEnabled(False);event.ignore();return
        self._close_after_preview=False;self.setEnabled(True);event.accept()

if __name__ == '__main__':
    from windows_identity import configure_taskbar_identity,has_package_identity
    configure_taskbar_identity()
    configure_storage()
    if '--sandbox-probe' in sys.argv:
        assert sandboxed(), 'Expected App Sandbox container'
        denied_path = Path(sys.argv[sys.argv.index('--sandbox-probe')+1])
        try:
            denied_path.read_bytes()
        except PermissionError:
            pass
        else:
            raise AssertionError('Sandbox allowed access to an unselected external file')
    app = W.QApplication(sys.argv)
    app.aboutToQuit.connect(file_access.close)
    app.setApplicationName('Easy Astro Studio')
    app.setApplicationDisplayName('Easy Astro Studio')
    app.setStyle('Fusion')
    window = Window(ask_on_close='--smoke-test' not in sys.argv); window.show()
    install_reopen_handler(app, window)
    if '--smoke-test' in sys.argv:
        if '--smoke-write-theme' in sys.argv:window.set_theme(sys.argv[sys.argv.index('--smoke-write-theme')+1])
        if '--smoke-expect-theme' in sys.argv:assert window.theme_name==sys.argv[sys.argv.index('--smoke-expect-theme')+1]
        from astropy.io import fits
        from network_tls import https_context
        assert https_context().cert_store_stats()['x509_ca'] > 0, 'Bundled HTTPS roots missing'
        assert window.coffee_button.isEnabled() and window.feedback_button.isEnabled()
        assert 'https://planner.astrivanta.com' in window.planner_banner.text()
        feedback=FeedbackDialog(window);assert feedback.send.isEnabled();feedback.close()
        assert VERSION in window.windowTitle() and window.about_action.text()=='About'
        review=FrameReviewDialog([], 'Auto',window);review.close()
        assert window.artwork_path.is_file(), 'Bundled header artwork missing'
        assert window.header_art.pixmap() is not None and not window.header_art.pixmap().isNull(), 'Header artwork failed to load'
        sample = np.ones((60, 80, 3), dtype=np.float32)*100
        sample[20:30, 20:30] = 500
        from stack_store import AlignedFrames,combine
        with AlignedFrames(sample.shape) as frames:
            frames.append(sample);frames.append(sample)
            assert np.array_equal(combine(frames),sample)
        window.loaded(sample, fits.Header())
        if sys.platform == 'darwin':
            import ctypes
            metal = ctypes.CDLL('/System/Library/Frameworks/Metal.framework/Metal')
            metal.MTLCreateSystemDefaultDevice.restype = ctypes.c_void_p
            if metal.MTLCreateSystemDefaultDevice():
                window.use_gpu.setChecked(True)
                assert window.gpu is not None and window.use_gpu.isChecked(), 'Bundled Metal backend failed: '+window.log.toPlainText()
                reference = engine.render(sample, *window.settings())
                accelerated = engine.render(sample, *window.settings(), gpu=window.gpu)
                assert not window.gpu.disabled, window.gpu.last_error
                np.testing.assert_allclose(accelerated, reference, atol=3e-5, rtol=3e-5)
                window.use_gpu.setChecked(False)
                print('Metal device available: bundled GPU validation passed', flush=True)
            else:
                print('No Metal device on this runner: GPU execution requires hardware testing', flush=True)
        if sys.platform == 'darwin':
            window.showMinimized(); app.processEvents()
            app._mac_reopen_handler.handleReopen_withReplyEvent_(None, None)
            app.processEvents()
            assert not window.isMinimized(), 'Dock reopen failed to restore the window'
            assert window.isVisible()
            np.testing.assert_array_equal(window.linear, sample)
        assert window.reset_crop_preview.isEnabled() and window.auto_sky_preview.isEnabled()
        window.auto_sky_preview.click()
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
        window.reset_crop_preview.click();assert window.crop_ratio.currentText()=='Free'
        window.preview.set_zoom(1)
        window.zoom_fit.click()
        window.sliders['Background neutralization %'].setValue(75)
        window.sliders['Midtones %'].setValue(30)
        window.sliders['Star-preserving noise reduction %'].setValue(40)
        window.curve.set_values((0,200,600,850,1000),emit=True)
        noise_sample=np.random.default_rng(15).uniform(100,200,sample.shape).astype(np.float32)
        assert np.isfinite(engine.render(noise_sample,*window.settings())).all()
        if sys.platform == 'darwin' and metal.MTLCreateSystemDefaultDevice():
            window.use_gpu.setChecked(True)
            assert window.gpu is not None, window.log.toPlainText()
            cpu_advanced=engine.render(noise_sample,*window.settings())
            metal_advanced=engine.render(noise_sample,*window.settings(),gpu=window.gpu)
            assert not window.gpu.disabled, window.gpu.last_error
            np.testing.assert_allclose(metal_advanced,cpu_advanced,atol=3e-5,rtol=3e-5)
            window.use_gpu.setChecked(False)
        window.update_preview()
        app.processEvents()
        import tempfile,time
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'smoke.jpg'
            engine.save(output,window.linear,engine.render(window.linear,*window.settings()),window.header)
            from PIL import Image
            with Image.open(output) as exported:
                assert exported.format=='JPEG'
            from privacy_viewer import PrivacyDialog
            privacy=PrivacyDialog(window);assert 'Optional Gaia star matching' in privacy.policy_text;privacy.reject()
            from gaia_matching import match_candidates
            from object_identification import catalog
            from astropy.wcs import WCS
            target=next(r for r in catalog() if r['id']=='OpenNGC:NGC0224')
            sky=WCS(naxis=2);sky.wcs.crpix=[40,30];sky.wcs.crval=[target['ra'],target['dec']];sky.wcs.cdelt=[-1/3600,1/3600];sky.wcs.ctype=['RA---TAN','DEC--TAN']
            identification=IdentifyDialog(window.original_linear,sky.to_header(),window.applied_crop,window);identification.identify()
            deadline=time.monotonic()+20
            while identification.worker is not None and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
            assert identification.worker is None and identification.selected_rows(),'Packaged offline identification failed'
            window.add_identified_objects(identification.selected_rows(),identification.solution);identification.reject()
            gaia_source=dict(id='Gaia DR3:1234567890123456789',name='Gaia DR3 1234567890123456789',category='Stars',ra=target['ra'],dec=target['dec'],epoch=2016.,pmra=0.,pmdec=0.,mag=12.,priority=2)
            matched=match_candidates(sky,sky.to_header(),window.applied_crop,[gaia_source],dict(x=[40.],y=[30.]),5.,100)
            assert matched and matched[0]['match_arcsec']<.01,'Packaged Gaia matching failed'

            raster,raster_header=engine.read_image(output);assert raster_header['EASRASTR'] and raster.shape==window.linear.shape
            window.labels_panel.text.setText('Test target');window.place_label(30,25)
            assert window.labeled_image().save(str(Path(folder)/'labeled.png'))
            assert window.annotations and window.labels_action.isEnabled()
            window.commit_history()
            project=Path(folder)/'smoke.astro'
            save_project(project,window.original_linear,window.original_header,window.project_manifest())
            restored,restored_header,meta=load_project(project)
            assert np.array_equal(restored,window.original_linear)
            assert meta['state']==window.edit_state()
            import time
            review_paths=[]
            for index in range(2):
                path=Path(folder)/f'exposure-{index}.fits'
                fits.writeto(path,sample[...,0],fits.Header({'EXPTIME':20.}))
                review_paths.append(str(path))
            review=FrameReviewDialog(review_paths,'None',window);review.show();app.processEvents()
            def wait_review():
                deadline=time.monotonic()+20
                while review.worker is not None and time.monotonic()<deadline:
                    app.processEvents();time.sleep(.01)
                assert review.worker is None,'Exposure review timed out'
            wait_review();assert not review.view.item.pixmap().isNull()
            review.start_analysis();wait_review();assert len(review.records)==2
            review.close()

        deadline=time.monotonic()+30
        while (window.preview_worker is not None or window.timer.isActive()) and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        assert window.preview_worker is None,'Preview worker timed out'
        window.new_project()
        app.processEvents()
        assert window.linear is None and window.files.count()==0
        assert not window.save_project_action.isEnabled() and not window.undo_action.isEnabled()
        assert not window.review.isEnabled()
        project_actions=window.findChild(W.QToolBar).actions()
        assert all('Preview / rate exposures' not in action.text() for action in project_actions)
        assert project_actions.index(window.new_project_action)+1==project_actions.index(window.open_project_action)

        if '--require-package-identity' in sys.argv:assert has_package_identity(),'Expected MSIX package identity'
        if '--smoke-result' in sys.argv:
            destination=Path(sys.argv[sys.argv.index('--smoke-result')+1])
            destination.write_text(json.dumps(dict(ok=True,version=VERSION,package_identity=has_package_identity())),encoding='utf-8')
        window.close()
        file_access.close()
        sys.exit(0)
    sys.exit(app.exec())
