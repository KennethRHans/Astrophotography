"""Visual sky-sample editor. All sample coordinates follow the original image."""
import cv2
import numpy as np
from PySide6 import QtCore,QtGui,QtWidgets as W
from preview import ImagePreview
from background_extraction import sky_grid,fit_sky
import engine


class SkyPreview(ImagePreview):
    pointClicked=QtCore.Signal(float,float)
    def __init__(self):
        super().__init__();self.points=[];self.guide='Off';self.setToolTip('Left-click to add/remove a sky sample. Wheel to zoom; right- or middle-drag to pan.')
    def paintEvent(self,event):W.QGraphicsView.paintEvent(self,event)
    def mousePressEvent(self,event):
        if event.button()==QtCore.Qt.LeftButton and self.source_size and self.image_rect().contains(event.position().toPoint()):
            p=self.mapToScene(event.position().toPoint());w,h=self.source_size
            self.pointClicked.emit(float(np.clip(p.x()/max(w-1,1),0,1)),float(np.clip(p.y()/max(h-1,1),0,1)));return
        super().mousePressEvent(event)
    def drawForeground(self,painter,rect):
        if not self.source_size:return
        w,h=self.source_size;pen=QtGui.QPen(QtGui.QColor('#5ae6ff'));pen.setCosmetic(True);painter.setPen(pen)
        radius=max(2,min(128,round(min(h,w)*.025)))
        for x,y in self.points:painter.drawRect(QtCore.QRectF(x*(w-1)-radius,y*(h-1)-radius,2*radius,2*radius))


class BackgroundDialog(W.QDialog):
    def __init__(self,image,config=None,parent=None):
        super().__init__(parent);self.image=image;self.config=None;self.setWindowTitle('Background extraction — select clear sky');self.resize(1000,760)
        layout=W.QVBoxLayout(self);note=W.QLabel('Click clear sky to add a sample; click near a box to remove it. Avoid galaxies, nebulae and bright stars. Spread samples across the full field. Auto points protect the center only: review every box. This removes a smooth gradient, not a global color cast.');note.setWordWrap(True);layout.addWidget(note)
        self.view=SkyPreview();layout.addWidget(self.view,1);self.view.points=[list(p) for p in config['points']] if config else sky_grid();self.view.pointClicked.connect(self.point)
        h,w,_=image.shape;scale=min(1,1000/max(h,w));small=cv2.resize(image,(max(1,round(w*scale)),max(1,round(h*scale))))
        pixels=np.ascontiguousarray(np.round(engine.render(small)*255).astype(np.uint8));q=QtGui.QImage(pixels.data,pixels.shape[1],pixels.shape[0],pixels.strides[0],QtGui.QImage.Format_RGB888).copy();self.view.set_image(q,(w,h))
        row=W.QHBoxLayout();layout.addLayout(row)
        for label,fn in [('Auto points (protect center)',self.auto),('Clear points',self.clear),('Fit view',self.view.fit_image)]:
            button=W.QPushButton(label);button.clicked.connect(fn);row.addWidget(button)
        self.order=W.QComboBox();self.order.addItems(['Plane — safer for extended targets','Quadratic — curved gradients']);self.order.setCurrentIndex(config['order']-1 if config else 0);row.addWidget(self.order)
        self.status=W.QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.Apply|W.QDialogButtonBox.Cancel);layout.addWidget(buttons);buttons.button(W.QDialogButtonBox.Apply).clicked.connect(self.apply);buttons.rejected.connect(self.reject)
        automatic=W.QPushButton('Restore automatic background fit');buttons.addButton(automatic,W.QDialogButtonBox.ResetRole);automatic.clicked.connect(self.restore_auto)
        self.refresh()
    def refresh(self):self.status.setText(f'{len(self.view.points)} sky samples. Applying also sets Gradient removal to 100%; adjust it afterward if needed. Faint extended targets can be subtracted if marked as sky. Undo restores the prior fit.');self.view.viewport().update()
    def point(self,x,y):
        if self.view.points:
            distances=[(px-x)**2+(py-y)**2 for px,py in self.view.points];i=int(np.argmin(distances))
            if distances[i]<.04**2:self.view.points.pop(i);self.refresh();return
        if len(self.view.points)<144:self.view.points.append([x,y]);self.refresh()
    def auto(self):self.view.points=sky_grid();self.refresh()
    def clear(self):self.view.points=[];self.refresh()
    def restore_auto(self):self.config=None;self.accept()
    def apply(self):
        config=dict(order=self.order.currentIndex()+1,points=self.view.points)
        try:fit_sky(self.image,config)
        except ValueError as exc:self.status.setText('Cannot apply: '+str(exc));return
        self.config=config;self.accept()
