"""Reviewable automatic labels with explicit opt-in to source-list upload."""
import numpy as np
import cv2
from PySide6 import QtCore,QtGui,QtWidgets as W
from controls import VisibleGpuCheckBox as VisibleCheckBox
from privacy_viewer import show_privacy
from object_identification import CATEGORIES,IdentificationWorker,celestial_wcs,SERVICE


class NumericItem(W.QTableWidgetItem):
    def __lt__(self,other):return self.data(QtCore.Qt.UserRole)<other.data(QtCore.Qt.UserRole)


class IdentifyDialog(W.QDialog):
    def __init__(self,image,header,crop,parent=None,worker_factory=IdentificationWorker,source_name=None,preview_image=None):
        super().__init__(parent);self.setWindowTitle('Identify objects');self.resize(1060,1020)
        self.image=image;self.header=header.copy();self.crop=crop;self.worker=None;self.worker_factory=worker_factory;self.closing=False;self.solution=None;self.result_warning=''
        root_layout=W.QVBoxLayout(self)
        self.body_scroll=W.QScrollArea();self.body_scroll.setWidgetResizable(True);self.body_scroll.setFrameShape(W.QFrame.NoFrame)
        content=W.QWidget();self.body_scroll.setWidget(content);root_layout.addWidget(self.body_scroll,1);layout=W.QVBoxLayout(content);layout.setContentsMargins(0,0,0,0)
        source_row=W.QHBoxLayout();layout.addLayout(source_row)
        self.image_thumbnail=W.QLabel();self.image_thumbnail.setFixedSize(100,76);self.image_thumbnail.setAlignment(QtCore.Qt.AlignCenter)
        self.image_thumbnail.setStyleSheet('border:1px solid #3789bb; background:black;');source_row.addWidget(self.image_thumbnail)
        if preview_image is None or preview_image.isNull():
            # Bounded fallback for standalone use. The main window passes its
            # current adjusted crop so it matches the image the user is editing.
            h,w=image.shape[:2];scale=min(1.,130/w,100/h)
            small=cv2.resize(image,(max(1,round(w*scale)),max(1,round(h*scale))),interpolation=cv2.INTER_AREA)
            if header.get('EASRASTR'):pixels=np.clip(small,0,1)
            else:
                import engine
                pixels=engine.render(small)
            pixels=np.ascontiguousarray(np.round(pixels*255).astype(np.uint8))
            preview_image=QtGui.QImage(pixels.data,pixels.shape[1],pixels.shape[0],pixels.strides[0],QtGui.QImage.Format_RGB888).copy()
        self.image_thumbnail.setPixmap(QtGui.QPixmap.fromImage(preview_image).scaled(96,72,QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation))
        h,w=image.shape[:2];x0,y0,x1,y1=crop
        name=source_name or str(header.get('OBJECT','Current image'))
        self.source_summary=W.QLabel(f'Image loaded: {name}\nFull image: {w:,} × {h:,} pixels • Identification area: {x1-x0:,} × {y1-y0:,} pixels (current crop)\nThe image already open in Easy Astro Studio is used. No second file selection is needed.')
        self.source_summary.setTextFormat(QtCore.Qt.PlainText);self.source_summary.setWordWrap(True);self.source_summary.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse);source_row.addWidget(self.source_summary,1)
        intro=W.QLabel('Find cataloged objects at sky coordinates. Results are catalog locations, not confirmation that an object is visible. Check that labels line up with the stars before using them.');intro.setWordWrap(True);layout.addWidget(intro)
        self.controls=W.QWidget();form=W.QFormLayout(self.controls);form.setContentsMargins(0,0,0,0);self.controls.setSizePolicy(W.QSizePolicy.Preferred,W.QSizePolicy.Minimum);layout.addWidget(self.controls)
        self.method=W.QComboBox();self.method.addItems(['Use existing FITS / project sky coordinates (offline)','Solve with Astrometry.net (online)']);form.addRow('Method',self.method)
        self.wcs_reason=''
        try:celestial_wcs(header,image.shape);self.has_wcs=True
        except Exception as exc:self.has_wcs=False;self.wcs_reason=str(exc)
        self.local_note=W.QLabel('Sky solution available: offline catalog matching is ready.' if self.has_wcs else 'Image loaded, but no usable sky-coordinate solution (WCS) is available. Offline catalogs cannot locate objects from pixels or the target name alone. Solve once online, or open a FITS/project that already has a sky solution.\nDetails: '+self.wcs_reason)
        self.local_note.setTextFormat(QtCore.Qt.PlainText);self.local_note.setWordWrap(True);form.addRow(self.local_note)
        self.choose_online=W.QPushButton('Set up online solving…');self.choose_online.clicked.connect(lambda:self.method.setCurrentIndex(1));form.addRow(self.choose_online)
        self.online=W.QWidget();online_layout=W.QVBoxLayout(self.online);online_layout.setContentsMargins(0,0,0,0)
        text=W.QLabel('Online solving sends up to 2,000 extracted star positions (ranked by brightness), original image dimensions and your API key over HTTPS to Astrometry.net. It does not send image pixels, filenames, paths or FITS headers. Sky location can be inferred from star positions. Private visibility and restrictive reuse are requested; service terms and retention apply. Cancel stops waiting locally; it cannot withdraw an upload. Your API key is kept only for this dialog and is not saved in projects or settings.');text.setWordWrap(True);online_layout.addWidget(text)
        keyrow=W.QHBoxLayout();self.key=W.QLineEdit();self.key.setEchoMode(W.QLineEdit.Password);self.key.setMaxLength(200);self.key.setPlaceholderText('Your Astrometry.net API key');keyrow.addWidget(self.key)
        self.key_link=W.QPushButton('Get Free API Key…');self.key_link.clicked.connect(lambda:QtGui.QDesktopServices.openUrl(QtCore.QUrl(SERVICE+'/api_help')));keyrow.addWidget(self.key_link);online_layout.addLayout(keyrow)
        links=W.QHBoxLayout()
        for caption,url in [('Service information','https://astrometry.net/doc/net/api.html'),('App privacy policy',None)]:
            b=W.QPushButton(caption)
            if url:b.clicked.connect(lambda checked=False,dest=url:QtGui.QDesktopServices.openUrl(QtCore.QUrl(dest)))
            else:
                b.clicked.connect(lambda:show_privacy(self))
            links.addWidget(b)
        online_layout.addLayout(links)
        self.consent=VisibleCheckBox('I agree to send the star-position data above to Astrometry.net for this solve.');online_layout.addWidget(self.consent)
        form.addRow(self.online)
        filters=W.QHBoxLayout();self.categories={}
        for name in CATEGORIES:
            box=VisibleCheckBox(name);box.setChecked(True);self.categories[name]=box;filters.addWidget(box)
        form.addRow('Object categories',filters)
        self.magnitude=W.QDoubleSpinBox();self.magnitude.setRange(-5,22);self.magnitude.setValue(16);self.magnitude.setDecimals(1);form.addRow('Faintest catalog magnitude',self.magnitude)
        self.unknown=VisibleCheckBox('Include objects without a magnitude');self.unknown.setChecked(True);form.addRow(self.unknown)
        self.limit=W.QSpinBox();self.limit.setRange(1,300);self.limit.setValue(100);form.addRow('Maximum results',self.limit)
        self.gaia=VisibleCheckBox('Match detected stars with Gaia DR3 (online)');form.addRow(self.gaia)
        self.gaia_options=W.QWidget();gaia_layout=W.QVBoxLayout(self.gaia_options);gaia_layout.setContentsMargins(0,0,0,0)
        gaia_note=W.QLabel('Gaia is a star catalog, not a plate solver. After a sky solution is available, this optional query sends the current crop’s sky center, search radius and magnitude limit to ESA’s Gaia Archive (gea.esac.esa.int). No image pixels, detected star positions, filenames or Astrometry.net API key are sent to Gaia. Up to 5,000 bright catalog sources are compared with locally detected stars. These are candidate matches, not guaranteed identifications.');gaia_note.setWordWrap(True);gaia_layout.addWidget(gaia_note)
        self.gaia_consent=VisibleCheckBox('I agree to send this sky-region query to ESA Gaia Archive for this search.');gaia_layout.addWidget(self.gaia_consent)
        tolerance_row=W.QHBoxLayout();tolerance_row.addWidget(W.QLabel('Maximum match separation (arcseconds)'))
        self.gaia_tolerance=W.QDoubleSpinBox();self.gaia_tolerance.setRange(.5,15);self.gaia_tolerance.setValue(5.);tolerance_row.addWidget(self.gaia_tolerance);tolerance_row.addStretch();gaia_layout.addLayout(tolerance_row);form.addRow(self.gaia_options);self.gaia_options.hide()
        self.status=W.QLabel('Choose categories, then Identify. Results are limited to the current crop.' if self.has_wcs else 'Your image is loaded. Offline identification is unavailable until it has a sky solution; no network request has been sent.');self.status.setTextFormat(QtCore.Qt.PlainText);self.status.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse);self.status.setWordWrap(True);root_layout.addWidget(self.status)
        self.table=W.QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['Use','Object','Category','Magnitude','Match (arcsec)']);self.table.setEditTriggers(W.QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(1,W.QHeaderView.Stretch);self.table.setSortingEnabled(True);self.table.setMinimumHeight(150);layout.addWidget(self.table,1)
        select=W.QHBoxLayout()
        for title,state in [('Select all',QtCore.Qt.Checked),('Select none',QtCore.Qt.Unchecked)]:
            b=W.QPushButton(title);b.clicked.connect(lambda checked=False,value=state:self.check_rows(value));select.addWidget(b)
        self.credits=W.QPushButton('Catalog credits');self.credits.clicked.connect(self.show_credits);select.addWidget(self.credits);layout.addLayout(select)
        buttons=W.QHBoxLayout();self.start=W.QPushButton('Identify');self.start.clicked.connect(self.identify);buttons.addWidget(self.start)
        self.apply=W.QPushButton('Add selected labels');self.apply.setEnabled(False);self.apply.clicked.connect(self.accept);buttons.addWidget(self.apply)
        self.cancel=W.QPushButton('Close');self.cancel.clicked.connect(self.reject);buttons.addWidget(self.cancel);root_layout.addLayout(buttons)
        self.method.currentIndexChanged.connect(self.method_changed);self.consent.toggled.connect(self.update_start);self.key.textChanged.connect(self.update_start);self.table.itemChanged.connect(self.update_apply)
        self.gaia.toggled.connect(self.gaia_changed);self.gaia_consent.toggled.connect(self.update_start)
        self.categories['Stars'].toggled.connect(self.update_start)
        self.method_changed()
        screen=self.screen().availableGeometry();self.resize(min(1060,screen.width()-40),min(1020,screen.height()-60))
    def set_status(self,text,kind='info'):
        colors={'info':('#edf7ff','#102c45','#4281a9'),'progress':('#edf7ff','#102c45','#4281a9'),'warning':('#ffe6a6','#382600','#dfaa35'),'error':('#ffffff','#5c1820','#ff7180')}
        fg,bg,border=colors[kind];prefix='ERROR — ' if kind=='error' else 'ATTENTION — ' if kind=='warning' else ''
        self.status.setText(prefix+text);self.status.setStyleSheet(f'color:{fg}; background:{bg}; border:2px solid {border}; border-radius:5px; padding:9px; font-weight:bold; font-size:14px;')
        self.status.setAccessibleName('Identification '+kind);self.status.setMinimumHeight(44)
    def gaia_changed(self,enabled):
        self.gaia_options.setVisible(enabled)
        if enabled:self.categories['Stars'].setChecked(True)
        else:self.gaia_consent.setChecked(False)
        self.update_start()
    def show_credits(self):
        W.QMessageBox.information(self,'Catalog credits','Deep-sky positions: OpenNGC, Mattia Verga and contributors (github.com/mattiaverga/OpenNGC). Stars: HYG v4.1, David Nash / Astronomy Nexus and contributors (github.com/astronexus/HYG-Database). Reduced catalogs are CC BY-SA 4.0. Source details and the full license are bundled in assets/catalogs. Gaia DR3: ESA mission Gaia and DPAC; DPAC funding by national institutions participating in the Gaia Multilateral Agreement. Gaia candidate matches use your sky solution and locally detected stars; they do not independently solve or verify the image. Catalog matches do not guarantee image detection.')
    def method_changed(self,*args):
        online=self.method.currentIndex()==1
        self.online.setVisible(online);self.choose_online.setVisible(not online and not self.has_wcs)
        if self.worker is None and self.table.rowCount()==0:
            self.set_status('Your current image is loaded. Enter your API key and give consent, then Solve and identify.' if online else 'Choose categories, then Identify offline.' if self.has_wcs else 'Your image is loaded. Offline identification needs a sky solution; no network request has been sent.','warning' if not online and not self.has_wcs else 'info')
        self.update_start()
    def update_start(self,*args):
        online=self.method.currentIndex()==1
        self.start.setText('Solve and identify' if online else 'Identify with Gaia' if self.gaia.isChecked() and self.has_wcs else 'Identify offline' if self.has_wcs else 'Identify offline (sky solution required)')
        self.start.setToolTip('This image needs a plate solve before offline catalog matching.' if not online and not self.has_wcs else 'Identify catalog objects in the current image crop.')
        self.start.setEnabled(self.worker is None and (not self.gaia.isChecked() or (self.gaia_consent.isChecked() and self.categories['Stars'].isChecked())) and ((online and self.consent.isChecked() and bool(self.key.text().strip())) or (not online and self.has_wcs)))
    def update_apply(self,*args):self.apply.setEnabled(self.worker is None and bool(self.selected_rows()))
    def check_rows(self,state):
        for row in range(self.table.rowCount()):self.table.item(row,0).setCheckState(state)
    def selected_rows(self):return [self.table.item(row,1).data(QtCore.Qt.UserRole) for row in range(self.table.rowCount()) if self.table.item(row,0).checkState()==QtCore.Qt.Checked]
    def identify(self):
        if not self.start.isEnabled() or self.worker is not None:return
        categories=[name for name,box in self.categories.items() if box.isChecked()]
        if not categories:self.set_status('Choose at least one object category.','warning');return
        options=dict(categories=categories,magnitude=self.magnitude.value(),limit=self.limit.value(),include_unknown=self.unknown.isChecked(),gaia=self.gaia.isChecked(),gaia_tolerance=self.gaia_tolerance.value())
        key=self.key.text().strip() if self.method.currentIndex()==1 else None
        self.table.setRowCount(0);self.solution=None;self.apply.setEnabled(False);self.controls.setEnabled(False);self.cancel.setText('Cancel operation')
        self.result_warning=''
        self.worker=self.worker_factory(self.image,self.header,self.crop,options,key=key)
        self.worker.progress.connect(lambda text:self.set_status(text,'progress'));self.worker.done.connect(self.receive);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.worker_finished)
        if hasattr(self.worker,'warning'):self.worker.warning.connect(self.receive_warning)
        self.update_start();self.worker.start()
    def receive_warning(self,text):
        self.result_warning=text
        if not self.closing:self.set_status(text,'warning')
    def receive(self,rows,header):
        if self.closing:return
        self.solution=header.copy();self.header=header.copy();self.has_wcs=True
        self.local_note.setText('Sky coordinates are available. Repeat using the offline method to change filters without uploading again.')
        self.method.setCurrentIndex(0);self.choose_online.hide();self.key.clear();self.consent.setChecked(False);self.gaia_consent.setChecked(False)
        self.table.blockSignals(True);self.table.setSortingEnabled(False);self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            check=W.QTableWidgetItem();check.setFlags(QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsUserCheckable);check.setCheckState(QtCore.Qt.Checked);self.table.setItem(i,0,check)
            name=W.QTableWidgetItem(r['name']);name.setData(QtCore.Qt.UserRole,r);self.table.setItem(i,1,name)
            self.table.setItem(i,2,W.QTableWidgetItem(r['category']))
            separation=NumericItem(f"{r['match_arcsec']:.2f}" if 'match_arcsec' in r else '—');separation.setData(QtCore.Qt.UserRole,r.get('match_arcsec',999.));self.table.setItem(i,4,separation)
            mag=NumericItem('Unknown' if r['mag'] is None else f"{r['mag']:.1f}");mag.setData(QtCore.Qt.UserRole,r['mag'] if r['mag'] is not None else 99.);self.table.setItem(i,3,mag)
        self.table.setSortingEnabled(True);self.table.blockSignals(False);self.update_apply();self.set_status(f'{len(rows)} catalog objects in the current crop, including '+str(sum('match_arcsec' in r for r in rows))+' Gaia star candidates. Select labels to add.' if rows else 'No catalog objects matched this crop and filter. Try a wider crop, more categories or a higher magnitude limit.','info' if rows else 'warning')
        if self.result_warning:self.set_status(self.result_warning,'warning')
    def failed(self,text):
        if not self.closing:self.set_status(text,'error')
    def worker_finished(self):
        self.worker.deleteLater();self.worker=None
        if self.closing:self.key.clear();super().reject();return
        self.controls.setEnabled(True);self.cancel.setText('Close');self.update_start();self.update_apply()
    def reject(self):
        if self.worker is not None:
            self.closing=True;self.worker.requestInterruption();self.controls.setEnabled(False);self.start.setEnabled(False);self.apply.setEnabled(False);self.cancel.setEnabled(False);self.set_status('Cancelling… Waiting for the current network request to finish (normally up to 60 seconds). Uploaded requests may continue on the service.','progress');return
        self.key.clear();super().reject()
    def accept(self):
        if self.worker is None and self.selected_rows():self.key.clear();super().accept()
    def closeEvent(self,event):
        if self.worker is not None:self.reject();event.ignore();return
        self.key.clear();super().closeEvent(event)
