"""Reviewable automatic labels with explicit opt-in to source-list upload."""
from PySide6 import QtCore,QtGui,QtWidgets as W
from controls import VisibleGpuCheckBox as VisibleCheckBox
from object_identification import CATEGORIES,IdentificationWorker,celestial_wcs,SERVICE


class NumericItem(W.QTableWidgetItem):
    def __lt__(self,other):return self.data(QtCore.Qt.UserRole)<other.data(QtCore.Qt.UserRole)


class IdentifyDialog(W.QDialog):
    def __init__(self,image,header,crop,parent=None,worker_factory=IdentificationWorker):
        super().__init__(parent);self.setWindowTitle('Identify objects');self.resize(820,720)
        self.image=image;self.header=header.copy();self.crop=crop;self.worker=None;self.worker_factory=worker_factory;self.closing=False;self.solution=None
        layout=W.QVBoxLayout(self)
        intro=W.QLabel('Find cataloged objects at sky coordinates. Results are catalog locations, not confirmation that an object is visible. Check that labels line up with the stars before using them.');intro.setWordWrap(True);layout.addWidget(intro)
        self.controls=W.QWidget();form=W.QFormLayout(self.controls);form.setContentsMargins(0,0,0,0);self.controls_scroll=W.QScrollArea();self.controls_scroll.setWidgetResizable(True);self.controls_scroll.setWidget(self.controls);self.controls_scroll.setMaximumHeight(340);self.controls_scroll.setMinimumHeight(180);layout.addWidget(self.controls_scroll)
        self.method=W.QComboBox();self.method.addItems(['Use existing FITS / project sky coordinates (offline)','Solve with Astrometry.net (online)']);form.addRow('Method',self.method)
        try:celestial_wcs(header,image.shape);self.has_wcs=True
        except Exception:self.has_wcs=False;self.method.setCurrentIndex(1)
        self.local_note=W.QLabel('Existing sky coordinates are available.' if self.has_wcs else 'No complete sky solution found. An online solve is needed first.');self.local_note.setWordWrap(True);form.addRow(self.local_note)
        self.online=W.QWidget();online_layout=W.QVBoxLayout(self.online);online_layout.setContentsMargins(0,0,0,0)
        text=W.QLabel('Online solving sends up to 2,000 extracted star positions (ranked by brightness), original image dimensions and your API key over HTTPS to Astrometry.net. It does not send image pixels, filenames, paths or FITS headers. Sky location can be inferred from star positions. Private visibility and restrictive reuse are requested; service terms and retention apply. Cancel stops waiting locally; it cannot withdraw an upload. Your API key is kept only for this dialog and is not saved in projects or settings.');text.setWordWrap(True);online_layout.addWidget(text)
        keyrow=W.QHBoxLayout();self.key=W.QLineEdit();self.key.setEchoMode(W.QLineEdit.Password);self.key.setMaxLength(200);self.key.setPlaceholderText('Your Astrometry.net API key');keyrow.addWidget(self.key)
        self.key_link=W.QPushButton('Get API key…');self.key_link.clicked.connect(lambda:QtGui.QDesktopServices.openUrl(QtCore.QUrl(SERVICE+'/api_help')));keyrow.addWidget(self.key_link);online_layout.addLayout(keyrow)
        links=W.QHBoxLayout()
        for caption,url in [('Service information','https://astrometry.net/doc/net/api.html'),('App privacy policy',None)]:
            b=W.QPushButton(caption)
            if url:b.clicked.connect(lambda checked=False,dest=url:QtGui.QDesktopServices.openUrl(QtCore.QUrl(dest)))
            else:
                from community_links import PRIVACY_URL
                b.clicked.connect(lambda:QtGui.QDesktopServices.openUrl(QtCore.QUrl(PRIVACY_URL)))
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
        self.status=W.QLabel('Choose categories, then Identify. Results are limited to the current crop.');self.status.setTextFormat(QtCore.Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        self.table=W.QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['Use','Object','Category','Magnitude']);self.table.setEditTriggers(W.QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(1,W.QHeaderView.Stretch);self.table.setSortingEnabled(True);layout.addWidget(self.table,1)
        select=W.QHBoxLayout()
        for title,state in [('Select all',QtCore.Qt.Checked),('Select none',QtCore.Qt.Unchecked)]:
            b=W.QPushButton(title);b.clicked.connect(lambda checked=False,value=state:self.check_rows(value));select.addWidget(b)
        self.credits=W.QPushButton('Catalog credits');self.credits.clicked.connect(self.show_credits);select.addWidget(self.credits);layout.addLayout(select)
        buttons=W.QHBoxLayout();self.start=W.QPushButton('Identify');self.start.clicked.connect(self.identify);buttons.addWidget(self.start)
        self.apply=W.QPushButton('Add selected labels');self.apply.setEnabled(False);self.apply.clicked.connect(self.accept);buttons.addWidget(self.apply)
        self.cancel=W.QPushButton('Close');self.cancel.clicked.connect(self.reject);buttons.addWidget(self.cancel);layout.addLayout(buttons)
        self.method.currentIndexChanged.connect(self.method_changed);self.consent.toggled.connect(self.update_start);self.key.textChanged.connect(self.update_start);self.table.itemChanged.connect(self.update_apply)
        self.method_changed()
    def show_credits(self):
        W.QMessageBox.information(self,'Catalog credits','Deep-sky positions: OpenNGC, Mattia Verga and contributors (github.com/mattiaverga/OpenNGC). Stars: HYG v4.1, David Nash / Astronomy Nexus and contributors (github.com/astronexus/HYG-Database). Reduced catalogs are CC BY-SA 4.0. Source details and the full license are bundled in assets/catalogs. Catalog matches do not guarantee image detection.')
    def method_changed(self,*args):
        self.online.setVisible(self.method.currentIndex()==1);self.update_start()
    def update_start(self,*args):
        online=self.method.currentIndex()==1
        self.start.setEnabled(self.worker is None and ((online and self.consent.isChecked() and bool(self.key.text().strip())) or (not online and self.has_wcs)))
    def update_apply(self,*args):self.apply.setEnabled(self.worker is None and bool(self.selected_rows()))
    def check_rows(self,state):
        for row in range(self.table.rowCount()):self.table.item(row,0).setCheckState(state)
    def selected_rows(self):return [self.table.item(row,1).data(QtCore.Qt.UserRole) for row in range(self.table.rowCount()) if self.table.item(row,0).checkState()==QtCore.Qt.Checked]
    def identify(self):
        if not self.start.isEnabled() or self.worker is not None:return
        categories=[name for name,box in self.categories.items() if box.isChecked()]
        if not categories:self.status.setText('Choose at least one object category.');return
        options=dict(categories=categories,magnitude=self.magnitude.value(),limit=self.limit.value(),include_unknown=self.unknown.isChecked())
        key=self.key.text().strip() if self.method.currentIndex()==1 else None
        self.table.setRowCount(0);self.solution=None;self.apply.setEnabled(False);self.controls.setEnabled(False);self.cancel.setText('Cancel operation')
        self.worker=self.worker_factory(self.image,self.header,self.crop,options,key=key)
        self.worker.progress.connect(self.status.setText);self.worker.done.connect(self.receive);self.worker.failed.connect(self.failed);self.worker.finished.connect(self.worker_finished)
        self.update_start();self.worker.start()
    def receive(self,rows,header):
        if self.closing:return
        self.solution=header.copy();self.header=header.copy();self.has_wcs=True
        self.local_note.setText('Sky coordinates are available. Repeat using the offline method to change filters without uploading again.')
        self.method.setCurrentIndex(0);self.key.clear();self.consent.setChecked(False)
        self.table.blockSignals(True);self.table.setSortingEnabled(False);self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            check=W.QTableWidgetItem();check.setFlags(QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsUserCheckable);check.setCheckState(QtCore.Qt.Checked);self.table.setItem(i,0,check)
            name=W.QTableWidgetItem(r['name']);name.setData(QtCore.Qt.UserRole,r);self.table.setItem(i,1,name)
            self.table.setItem(i,2,W.QTableWidgetItem(r['category']))
            mag=NumericItem('Unknown' if r['mag'] is None else f"{r['mag']:.1f}");mag.setData(QtCore.Qt.UserRole,r['mag'] if r['mag'] is not None else 99.);self.table.setItem(i,3,mag)
        self.table.setSortingEnabled(True);self.table.blockSignals(False);self.update_apply();self.status.setText(f'{len(rows)} catalog objects in the current crop. Select the labels you want to add.' if rows else 'No catalog objects matched this crop and filter. Try a wider crop, more categories or a higher magnitude limit.')
    def failed(self,text):
        if not self.closing:self.status.setText(text)
    def worker_finished(self):
        self.worker.deleteLater();self.worker=None
        if self.closing:self.key.clear();super().reject();return
        self.controls.setEnabled(True);self.cancel.setText('Close');self.update_start();self.update_apply()
    def reject(self):
        if self.worker is not None:
            self.closing=True;self.worker.requestInterruption();self.controls.setEnabled(False);self.start.setEnabled(False);self.apply.setEnabled(False);self.cancel.setEnabled(False);self.status.setText('Cancelling… Waiting for the current request to finish (up to 20 seconds). Uploaded requests may continue on the service.');return
        self.key.clear();super().reject()
    def accept(self):
        if self.worker is None and self.selected_rows():self.key.clear();super().accept()
    def closeEvent(self,event):
        if self.worker is not None:self.reject();event.ignore();return
        self.key.clear();super().closeEvent(event)
