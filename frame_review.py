"""Single-exposure preview and optional batch quality review, one frame in RAM."""
from pathlib import Path
import numpy as np
import cv2
from PySide6 import QtCore,QtGui,QtWidgets as W
import engine
from frame_quality import measure,rate_batch
from preview import ImagePreview
from review_stretch import render_review


class ReviewPreview(ImagePreview):
    def __init__(self):
        super().__init__('Select an exposure, then Preview selected')
        self.guide='Off';self.setToolTip('Mouse wheel to zoom. Right- or middle-drag to pan. Use Full resolution to inspect native stars.')
    def paintEvent(self,event):
        W.QGraphicsView.paintEvent(self,event)
        if self.item.pixmap().isNull():
            painter=QtGui.QPainter(self.viewport());painter.setPen(QtGui.QColor('#c2d9f2'))
            painter.drawText(self.viewport().rect(),QtCore.Qt.AlignCenter,self.empty_text)
    def mousePressEvent(self,event):
        if event.button()==QtCore.Qt.LeftButton:event.ignore();return
        super().mousePressEvent(event)


class ReviewWorker(QtCore.QThread):
    rowReady=QtCore.Signal(str,object)
    previewReady=QtCore.Signal(str,object,str)
    progress=QtCore.Signal(int,int)
    failed=QtCore.Signal(str)
    def __init__(self,paths,bayer,scan=False,full=False,auto_stretch=True):
        super().__init__();self.paths=list(paths);self.bayer=bayer;self.scan=scan;self.full=full;self.auto_stretch=auto_stretch
    def run(self):
        for index,path in enumerate(self.paths):
            if self.isInterruptionRequested():break
            try:
                data,header=engine.read_fits(path,self.bayer)
                if self.scan:
                    row=measure(data,header);self.rowReady.emit(path,row)
                else:
                    h,w,_=data.shape
                    scale=1 if self.full else max(1,max(h,w)/1600)
                    size=(max(1,round(w/scale)),max(1,round(h/scale)))
                    if self.auto_stretch:
                        rendered=render_review(data,size)
                    else:
                        small=cv2.resize(data,size,interpolation=cv2.INTER_AREA) if scale>1 else data
                        rendered=engine.render(small)
                    pixels=np.ascontiguousarray(np.round(rendered*255).astype(np.uint8))
                    mode='Full resolution' if self.full else 'Preview (up to 1600 px); enable Full resolution to inspect stars'
                    display='Auto stretch (darker sky)' if self.auto_stretch else 'Standard stretch'
                    self.previewReady.emit(path,(pixels,(w,h)),f'{Path(path).name} • {w} × {h} • {mode} • {display}')
                del data
            except Exception as exc:
                if self.scan:self.rowReady.emit(path,dict(stars=0,fwhm=None,elongation=None,score=None,status=str(exc)))
                else:self.failed.emit(str(exc))
            self.progress.emit(index+1,len(self.paths))


class ScoreItem(W.QTableWidgetItem):
    def __lt__(self,other):
        return (self.data(QtCore.Qt.UserRole) if self.data(QtCore.Qt.UserRole) is not None else -1)<(other.data(QtCore.Qt.UserRole) if other.data(QtCore.Qt.UserRole) is not None else -1)


class FrameReviewDialog(W.QDialog):
    def __init__(self,paths,bayer,parent=None,selected=None):
        super().__init__(parent)
        self.setWindowTitle('Preview exposures and choose a reference');self.resize(1180,780)
        self.paths=list(paths);self.bayer=bayer;self.records={};self.worker=None;self.chosen_path=None;self._closing=False;self._selection_path=None
        root=W.QVBoxLayout(self)
        hint=W.QLabel('The reference is the frame other exposures align to. Preview stars, or analyze the batch for relative scores. Use as reference moves your choice to the top; all exposures remain in the list.')
        hint.setWordWrap(True);root.addWidget(hint)
        split=W.QSplitter();root.addWidget(split,1)
        self.table=W.QTableWidget(len(paths),6);self.table.setHorizontalHeaderLabels(['Exposure','Score / 100','Stars','Approx. FWHM (px)','Elongation','Assessment'])
        self.table.setEditTriggers(W.QAbstractItemView.NoEditTriggers);self.table.setSelectionBehavior(W.QAbstractItemView.SelectRows);self.table.setSelectionMode(W.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(W.QHeaderView.Interactive)
        for col,width in enumerate([240,80,55,130,90,240]):self.table.setColumnWidth(col,width)
        self.table.setTextElideMode(QtCore.Qt.ElideMiddle);self.table.setWordWrap(False)
        for row,path in enumerate(paths):
            item=W.QTableWidgetItem(Path(path).name);item.setData(QtCore.Qt.UserRole,path);item.setToolTip(path);self.table.setItem(row,0,item)
            for column in range(1,6):self.table.setItem(row,column,ScoreItem('—') if column in (1,2,3,4) else W.QTableWidgetItem('Not analyzed' if column==5 else '—'))
        self.table.setSortingEnabled(True);self.table.sortItems(0,QtCore.Qt.AscendingOrder)
        self.table.horizontalHeader().setToolTip('Click a column heading to sort; click again to reverse the order.')
        split.addWidget(self.table)
        right=W.QWidget();column=W.QVBoxLayout(right);column.setContentsMargins(4,0,0,0)
        self.view=ReviewPreview();column.addWidget(self.view,1)
        self.caption=W.QLabel('');self.caption.setWordWrap(True);self.caption.setMinimumHeight(64);self.caption.setTextFormat(QtCore.Qt.PlainText);column.addWidget(self.caption)
        zoom=W.QHBoxLayout();column.addLayout(zoom)
        fit=W.QPushButton('Fit');fit.clicked.connect(self.view.fit_image);zoom.addWidget(fit)
        native=W.QPushButton('100%');native.clicked.connect(lambda:self.view.set_zoom(1));zoom.addWidget(native)
        self.full=W.QCheckBox('Full resolution (slower)');zoom.addWidget(self.full)
        display=W.QHBoxLayout();column.addLayout(display);display.addWidget(W.QLabel('Display:'))
        self.stretch_mode=W.QComboBox();self.stretch_mode.addItems(['Auto stretch (darker sky)','Standard stretch'])
        self.stretch_mode.setToolTip('Display only. Measurements, scores and source pixels are unchanged. Auto estimates the sky level; it does not color-calibrate the exposure.')
        display.addWidget(self.stretch_mode,1)
        self.stretch_mode.currentIndexChanged.connect(lambda *_:self.start_preview())
        split.addWidget(right);split.setSizes([620,560])
        note=W.QLabel('Scores compare matching target, dimensions, exposure time and filter only. Higher favors sharper, rounder stars and more detections. Clouds, nebulosity, hot pixels and missing metadata can mislead scoring; a score cannot guarantee alignment. Approximate FWHM is measured on a reduced image. Display stretch changes only the preview; analysis uses the original linear pixels.')
        note.setWordWrap(True);root.addWidget(note)
        self.progress=W.QProgressBar();self.progress.setValue(0);root.addWidget(self.progress)
        self.status=W.QLabel('Choose a frame to preview, or analyze all exposures.');self.status.setWordWrap(True);root.addWidget(self.status)
        buttons=W.QHBoxLayout();root.addLayout(buttons)
        self.preview_button=W.QPushButton('Preview selected');self.preview_button.clicked.connect(self.start_preview);buttons.addWidget(self.preview_button)
        self.analyze=W.QPushButton('Analyze all exposures');self.analyze.clicked.connect(self.start_analysis);buttons.addWidget(self.analyze)
        self.best=W.QPushButton('Select highest score');self.best.setToolTip('Select the highest score in the selected exposure’s matching group');self.best.setEnabled(False);self.best.clicked.connect(self.select_best);buttons.addWidget(self.best)
        self.cancel=W.QPushButton('Cancel analysis');self.cancel.setEnabled(False);self.cancel.clicked.connect(self.cancel_work);buttons.addWidget(self.cancel)
        buttons.addStretch()
        self.use=W.QPushButton('Use as reference');self.use.clicked.connect(self.choose_reference);buttons.addWidget(self.use)
        close=W.QPushButton('Close');close.clicked.connect(self.reject);buttons.addWidget(close)
        self.table.cellDoubleClicked.connect(lambda *_:self.start_preview())
        self.table.itemSelectionChanged.connect(self.selection_changed)
        initial=selected if selected in self.paths else self.paths[0] if self.paths else None
        if initial is not None:self.table.selectRow(next(i for i in range(self.table.rowCount()) if self.table.item(i,0).data(QtCore.Qt.UserRole)==initial))
        QtCore.QTimer.singleShot(0,lambda:self.start_preview() if self.isVisible() else None)

    def selected_path(self):
        row=self.table.currentRow()
        return self.table.item(row,0).data(QtCore.Qt.UserRole) if row>=0 else None

    def launch(self,worker):
        if self.worker is not None:return
        self.worker=worker
        for control in (self.preview_button,self.analyze,self.best,self.use,self.full,self.stretch_mode):control.setEnabled(False)
        self.cancel.setEnabled(True)
        self.progress.setRange(0,len(worker.paths));self.progress.setValue(0)
        worker.rowReady.connect(self.receive_row);worker.previewReady.connect(self.receive_preview)
        worker.progress.connect(lambda done,total:(self.progress.setMaximum(total),self.progress.setValue(done)))
        worker.failed.connect(lambda text:self.status.setText('Could not preview: '+text))
        worker.finished.connect(self.finish_work);worker.start()

    def start_preview(self):
        if self.worker is not None or self._closing:return
        path=self.selected_path()
        if path:
            self.caption.setText('Loading '+Path(path).name+'…')
            self.view.item.setPixmap(QtGui.QPixmap());self.view.source_size=None;self.view.viewport().update()
            self.status.setText('Loading one exposure; the main image and edits are preserved.')
            self.launch(ReviewWorker([path],self.bayer,full=self.full.isChecked(),auto_stretch=self.stretch_mode.currentIndex()==0))

    def start_analysis(self):
        if self.worker is not None:return
        self.records={}
        self.table.setSortingEnabled(False)
        for row in range(self.table.rowCount()):
            for col in range(1,6):self.table.setItem(row,col,ScoreItem('—') if col in (1,2,3,4) else W.QTableWidgetItem('Not analyzed' if col==5 else '—'))
        self.table.setSortingEnabled(True)
        self.status.setText('Analyzing one exposure at a time. Cancel stops between files.')
        self.launch(ReviewWorker(self.paths,self.bayer,scan=True))

    def receive_row(self,path,record):
        self.records[path]=record
        self.refresh_row(path,record)

    def refresh_row(self,path,record):
        self.table.setSortingEnabled(False)
        row=next(i for i in range(self.table.rowCount()) if self.table.item(i,0).data(QtCore.Qt.UserRole)==path)
        score=record.get('score');item=ScoreItem(f'{score:.1f}' if score is not None else '—');item.setData(QtCore.Qt.UserRole,score);self.table.setItem(row,1,item)
        for column,key in ((2,'stars'),(3,'fwhm'),(4,'elongation'),(5,'status')):
            value=record.get(key)
            text=f'{value:.2f}' if isinstance(value,float) else str(value) if value is not None else '—'
            item=ScoreItem(text) if column in (2,3,4) else W.QTableWidgetItem(text)
            if column in (2,3,4):item.setData(QtCore.Qt.UserRole,value)
            item.setToolTip(item.text());self.table.setItem(row,column,item)
        self.table.setSortingEnabled(True)

    def receive_preview(self,path,payload,caption):
        pixels,size=payload;h,w,_=pixels.shape
        image=QtGui.QImage(pixels.data,w,h,pixels.strides[0],QtGui.QImage.Format_RGB888).copy()
        self.view.set_image(image,size);self.view.fit_image();self.caption.setText(caption)
        self.status.setText('Preview only. Choose Use as reference to change the alignment reference.')

    def finish_work(self):
        scanned=self.worker.scan;cancelled=self.worker.isInterruptionRequested()
        self.worker.deleteLater();self.worker=None
        if scanned:
            self.records=rate_batch(self.records)
            for path,row in self.records.items():self.refresh_row(path,row)
            self.status.setText(('Analysis stopped. ' if cancelled else 'Analysis complete. ')+f'{len(self.records)}/{len(self.paths)} exposures checked. Scores do not remove frames.')
        for control in (self.preview_button,self.analyze,self.use,self.full,self.stretch_mode):control.setEnabled(True)
        self.refresh_best_button();self.cancel.setEnabled(False)
        if self._closing:super().reject()

    def selection_changed(self):
        self.refresh_best_button()
        path=self.selected_path()
        changed=path!=self._selection_path;self._selection_path=path
        if self.worker is None and changed:
            self.view.item.setPixmap(QtGui.QPixmap());self.view.source_size=None;self.view.viewport().update()
            self.caption.setText('Selected: '+Path(self.selected_path()).name+' • Click Preview selected' if self.selected_path() else '')

    def refresh_best_button(self):
        group=self.records.get(self.selected_path(),{}).get('group')
        self.best.setEnabled(self.worker is None and group is not None and any(r.get('score') is not None and r.get('group')==group for r in self.records.values()))

    def select_best(self):
        group=self.records.get(self.selected_path(),{}).get('group')
        candidates=[(r['score'],p) for p,r in self.records.items() if r.get('score') is not None and group is not None and r.get('group')==group]
        if not candidates:return
        path=max(candidates,key=lambda pair:pair[0])[1]
        row=next(i for i in range(self.table.rowCount()) if self.table.item(i,0).data(QtCore.Qt.UserRole)==path)
        self.table.selectRow(row);self.start_preview()

    def choose_reference(self):
        if self.worker is None:
            self.chosen_path=self.selected_path()
            if self.chosen_path:self.accept()

    def cancel_work(self):
        if self.worker is not None:self.worker.requestInterruption();self.status.setText('Stopping after the current exposure…')

    def reject(self):
        if self.worker is not None:self._closing=True;self.cancel_work();return
        super().reject()

    def closeEvent(self,event):
        if self.worker is not None:self._closing=True;self.cancel_work();event.ignore();return
        super().closeEvent(event)
