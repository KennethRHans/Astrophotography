import sys
import copy
import json
from pathlib import Path
import numpy as np
import cv2
from PySide6 import QtCore, QtGui, QtWidgets as W
import engine
from macos_access import configure_storage, sandboxed

from preview import ImagePreview
from project_store import EditHistory,validate_state,save_project,load_project
from histogram import HistogramView,histogram_data
import community_links
from feedback import FeedbackDialog
from app_version import VERSION
from themes import THEMES,apply_theme
from frame_review import FrameReviewDialog

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
    def __init__(self,ask_on_close=True,settings=None):
        super().__init__()
        self.ask_on_close=ask_on_close
        self.history=EditHistory()
        self._history_ready=False;self._restoring=False
        self.project_worker=None;self.project_path=None;self._saved_signature=None;self._dirty=False;self._after_io=None
        self.source_paths=[]
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
            self.use_gpu.setEnabled(False)
            self.use_gpu.setText('CPU processing (Mac preview)')
        self.use_gpu.setToolTip('GPU acceleration is unavailable in the Mac preview.' if sys.platform == 'darwin' else 'Accelerates row combining, stretch, saturation and smoothing. Star alignment stays on CPU. Uses bounded chunks with CPU fallback.')
        self.use_gpu.toggled.connect(self.toggle_gpu); gpu_row.addWidget(self.use_gpu); left_column.addWidget(self.gpu_panel)
        controls = W.QWidget(); controls.setObjectName('controlPanel')
        sidebar = W.QVBoxLayout(controls)
        scroll = W.QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(controls)
        scroll.setMinimumWidth(360); left_column.addWidget(scroll,1)
        self.sidebar_scroll = scroll
        instructions = W.QLabel('Instructions For Use:'); instructions.setStyleSheet('font-weight:bold; font-size:15px'); sidebar.addWidget(instructions)
        intro = W.QLabel('1. Set Bayer Pattern (Equipment-based)\n2. Load FITS Stack or Multiple Files to Stack\n3. Align and Stack Exposures\n4. Adjust and Crop\n5. Export'); intro.setWordWrap(True); intro.setContentsMargins(12,0,0,6); sidebar.addWidget(intro)
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
        self.step_load=W.QGroupBox();self.step_load.setObjectName('stepLoad');self.step_load.setAccessibleName('2. Load FITS Stack or Multiple Files to Stack')
        outer_sidebar.addWidget(self.step_load);sidebar=W.QVBoxLayout(self.step_load)
        section_title=W.QLabel('2. Load FITS Stack or Multiple Files to Stack');section_title.setObjectName('sectionTitle');section_title.setWordWrap(True);sidebar.addWidget(section_title)
        load_hint=W.QLabel('Open an existing stack and continue to step 4, or add individual exposures for step 3.');load_hint.setWordWrap(True);sidebar.addWidget(load_hint)
        self.open = W.QPushButton('Open existing FITS stack…'); self.open.clicked.connect(lambda: self.start(True)); sidebar.addWidget(self.open)
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
        next_export = W.QPushButton('Continue to step 5: Export →')
        next_export.clicked.connect(lambda: self.show_step(self.step_export)); sidebar.addWidget(next_export)
        outer_sidebar.addSpacing(20)
        self.step_export = W.QGroupBox(); self.step_export.setAccessibleName('5. Export'); self.step_export.setObjectName('stepExport')
        self.step_export.setEnabled(False); outer_sidebar.addWidget(self.step_export)
        sidebar = W.QVBoxLayout(self.step_export)
        section_title = W.QLabel('5. Export'); section_title.setObjectName('sectionTitle'); section_title.setWordWrap(True); sidebar.addWidget(section_title)
        export_hint = W.QLabel('Save the adjusted picture as TIFF, PNG or JPG, or keep linear data as FITS. Choose the format and filename in the save window.'); export_hint.setWordWrap(True); sidebar.addWidget(export_hint)
        self.export = W.QPushButton('5. Export image…'); self.export.setEnabled(False); self.export.clicked.connect(self.save); sidebar.addWidget(self.export)
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
        self.open_project_action=QtGui.QAction('Open project…',self);self.open_project_action.setShortcut(QtGui.QKeySequence.StandardKey.Open);self.open_project_action.triggered.connect(self.open_project_dialog)
        self.save_project_action=QtGui.QAction('Save project',self);self.save_project_action.setShortcut(QtGui.QKeySequence.StandardKey.Save);self.save_project_action.triggered.connect(self.save_project_dialog)
        self.save_as_action=QtGui.QAction('Save project as…',self);self.save_as_action.setShortcut(QtGui.QKeySequence.StandardKey.SaveAs);self.save_as_action.triggered.connect(lambda: self.save_project_dialog(save_as=True))
        self.undo_action=QtGui.QAction('Undo',self);self.undo_action.setShortcut(QtGui.QKeySequence.StandardKey.Undo);self.undo_action.triggered.connect(self.undo_edit)
        self.redo_action=QtGui.QAction('Redo',self);self.redo_action.setShortcuts(QtGui.QKeySequence.keyBindings(QtGui.QKeySequence.StandardKey.Redo));self.redo_action.triggered.connect(self.redo_edit)
        for action in (self.open_project_action,self.save_project_action,self.undo_action,self.redo_action):toolbar.addAction(action)
        file_menu=self.menuBar().addMenu('File');file_menu.addActions([self.open_project_action,self.save_project_action,self.save_as_action])
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
        self.privacy_action=QtGui.QAction('Privacy Policy',self);self.privacy_action.triggered.connect(lambda:self.open_community_link(community_links.PRIVACY_URL));settings_menu.addAction(self.privacy_action)
        self.theme_actions={};self.theme_group=QtGui.QActionGroup(self);self.theme_group.setExclusive(True)
        for name in THEMES:
            action=QtGui.QAction(name,self);action.setCheckable(True);action.setChecked(name==self.theme_name)
            action.triggered.connect(lambda checked=False,choice=name:self.set_theme(choice))
            self.theme_group.addAction(action);theme_menu.addAction(action);self.theme_actions[name]=action
        self.about_action=QtGui.QAction('About',self);self.about_action.triggered.connect(self.show_about)
        self.menuBar().addAction(self.about_action)
        self.update_actions()
        self.statusBar().showMessage('Ready • CPU processing • Originals are preserved')
    def update_planner_banner(self):
        color=THEMES[self.theme_name]['link'];url=community_links.PLANNER_URL
        self.planner_banner.setText(f'Plan tonight\'s observing at <a style="color:{color}; text-decoration:underline" href="{url}">{url}</a>')

    def set_theme(self,name):
        self.theme_name=apply_theme(W.QApplication.instance(),name)
        self.settings_store.setValue('appearance/theme',self.theme_name);self.settings_store.sync()
        self.theme_actions[self.theme_name].setChecked(True);self.update_planner_banner()
        if hasattr(self,'_clipping_warning'):self.clip_summary.setStyleSheet('color: '+THEMES[self.theme_name]['warning' if self._clipping_warning else 'fg']+';')

    def show_about(self):
        W.QMessageBox.about(self,'About Easy Astro Studio',
            '<h2>Easy Astro Studio</h2><p>Version '+VERSION+'</p><p>by Astrivanta ©</p>'
            '<p>Align and stack FITS exposures, adjust and crop images, and export FITS, TIFF, PNG or JPEG.</p>'
            '<p><a href="'+community_links.PRIVACY_URL+'">Privacy Policy</a> · Privacy contact: starsandfits@gmail.com</p>')

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
        self.use_gpu.setEnabled(sys.platform != 'darwin')
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
        self._clipping_warning=max(black,white)>.1
        self.clip_summary.setStyleSheet('color: '+THEMES[self.theme_name]['warning' if self._clipping_warning else 'fg']+';')
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
        self.review.setEnabled(not busy and self.files.count()>0)
        self.run.setEnabled(not busy and self.files.count()>=2);self.next_stack.setEnabled(not busy and self.files.count()>=2)
        self.reference_label.setText('Reference: '+Path(self.files.item(0).text()).name if self.files.count() else 'Reference: first exposure in the list')
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
            self.validate_edit_state(meta['state'],linear.shape)
            for state in meta.get('history',{}).get('states',[]):self.validate_edit_state(state,linear.shape)
            self.loaded(linear,header)
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
            history=meta.get('history')
            if history:self.history.states=copy.deepcopy(history['states']);self.history.index=history['index']
            else:self.history.reset(self.edit_state())
            view=meta.get('view',{})
            self.mark_clipping.setChecked(bool(view.get('mark_clipping',False)))
            self.use_gpu.setChecked(bool(view.get('gpu',False)) and sys.platform != 'darwin')
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
        self.use_gpu.setEnabled(sys.platform != 'darwin')
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
    app.setApplicationName('Easy Astro Studio')
    app.setApplicationDisplayName('Easy Astro Studio')
    app.setStyle('Fusion')
    window = Window(ask_on_close='--smoke-test' not in sys.argv); window.show()
    if '--smoke-test' in sys.argv:
        if '--smoke-write-theme' in sys.argv:window.set_theme(sys.argv[sys.argv.index('--smoke-write-theme')+1])
        if '--smoke-expect-theme' in sys.argv:assert window.theme_name==sys.argv[sys.argv.index('--smoke-expect-theme')+1]
        from astropy.io import fits
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

        if '--require-package-identity' in sys.argv:assert has_package_identity(),'Expected MSIX package identity'
        if '--smoke-result' in sys.argv:
            destination=Path(sys.argv[sys.argv.index('--smoke-result')+1])
            destination.write_text(json.dumps(dict(ok=True,version=VERSION,package_identity=has_package_identity())),encoding='utf-8')
        window.close()
        sys.exit(0)
    sys.exit(app.exec())
