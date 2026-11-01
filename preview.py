"""Zoomable image preview with crop edges in source-pixel coordinates."""
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as W
import engine


class ImagePreview(W.QGraphicsView):
    selection = QtCore.Signal(int,int,int,int)
    zoomChanged = QtCore.Signal(float)
    def __init__(self, text='Your image will appear here'):
        super().__init__()
        self.setScene(W.QGraphicsScene(self))
        self.item = W.QGraphicsPixmapItem(); self.scene().addItem(self.item)
        self.item.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self.source_size = None
        self.selection_pixels = None
        self.ratio = None
        self.guide = 'Thirds + rulers'
        self.fit_mode = True
        self.mode = None
        self.pan_start = None
        self.setMouseTracking(True)
        self.setBackgroundBrush(QtGui.QColor('#080e18'))
        self.setFrameShape(W.QFrame.NoFrame)
        self.setTransformationAnchor(W.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(W.QGraphicsView.AnchorViewCenter)
        self.setMinimumSize(400,300)
        self.setToolTip('Drag crop edges or corners. Drag inside a crop to move it. Wheel to zoom; right-drag or middle-drag to pan.')
    def set_image(self, image, source_size):
        previous_size = self.sceneRect().size()
        self.source_size = tuple(source_size)
        w,h = self.source_size
        self.item.setPixmap(QtGui.QPixmap.fromImage(image))
        self.item.setTransform(QtGui.QTransform.fromScale(w/image.width(),h/image.height()))
        self.scene().setSceneRect(0,0,w,h)
        if previous_size != QtCore.QSizeF(w,h):
            self.fit_mode = True
        if self.fit_mode:
            self.fit_image()
        self.viewport().update()
    def fit_image(self):
        if self.item.pixmap().isNull(): return
        old=self.transform().m11(); self.fit_mode=True
        self.fitInView(self.sceneRect(),QtCore.Qt.KeepAspectRatio)
        if abs(old-self.transform().m11())>1e-6:
            self.zoomChanged.emit(self.transform().m11())
    def set_zoom(self, scale):
        if self.item.pixmap().isNull(): return
        scale=max(.01,min(16.,float(scale)))
        self.fit_mode=False
        self.scale(scale/self.transform().m11(),scale/self.transform().m22())
        self.zoomChanged.emit(self.transform().m11()); self.viewport().update()
    def zoom_by(self, factor): self.set_zoom(self.transform().m11()*factor)
    def wheelEvent(self,event):
        if not self.source_size: event.ignore(); return
        self.zoom_by(1.25**(event.angleDelta().y()/120)); event.accept()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.fit_mode: self.fit_image()
    def image_rect(self):
        if not self.source_size: return QtCore.QRect()
        w,h=self.source_size
        return self.mapFromScene(QtCore.QRectF(0,0,w,h)).boundingRect()
    def selection_rect(self):
        if not self.selection_pixels: return self.image_rect()
        x0,y0,x1,y1=self.selection_pixels
        return self.mapFromScene(QtCore.QRectF(x0,y0,x1-x0,y1-y0)).boundingRect()
    def update_band(self): self.viewport().update()
    def pixels_at(self,point):
        p=self.mapToScene(point);w,h=self.source_size
        return max(0,min(w,round(p.x()))),max(0,min(h,round(p.y())))
    def hit_handle(self,point):
        if not self.selection_pixels: return None
        r=self.selection_rect(); tolerance=10
        if not r.adjusted(-tolerance,-tolerance,tolerance,tolerance).contains(point): return None
        edges=''
        if abs(point.x()-r.left())<=tolerance: edges+='l'
        elif abs(point.x()-r.right())<=tolerance: edges+='r'
        if abs(point.y()-r.top())<=tolerance: edges+='t'
        elif abs(point.y()-r.bottom())<=tolerance: edges+='b'
        return edges or None
    def mousePressEvent(self,event):
        if not self.source_size: return super().mousePressEvent(event)
        pos=event.position().toPoint()
        if event.button() in (QtCore.Qt.RightButton,QtCore.Qt.MiddleButton):
            self.pan_start=pos; self.pan_values=(self.horizontalScrollBar().value(),self.verticalScrollBar().value())
            self.setCursor(QtCore.Qt.ClosedHandCursor); event.accept(); return
        if event.button()!=QtCore.Qt.LeftButton: return
        self.start_pixel=self.pixels_at(pos)
        self.start_bounds=self.selection_pixels or (0,0,*self.source_size)
        edge=self.hit_handle(pos)
        w,h=self.source_size
        if edge:
            self.mode=edge
        elif self.selection_rect().contains(pos) and self.start_bounds != (0,0,w,h):
            self.mode='move'
        elif self.image_rect().contains(pos):
            self.mode='new'
        else: self.mode=None
        event.accept()
    def mouseMoveEvent(self,event):
        pos=event.position().toPoint()
        if self.pan_start is not None:
            delta=pos-self.pan_start
            self.horizontalScrollBar().setValue(self.pan_values[0]-delta.x())
            self.verticalScrollBar().setValue(self.pan_values[1]-delta.y())
            event.accept(); return
        if self.mode:
            pixel=self.pixels_at(pos);w,h=self.source_size
            try:
                if self.mode=='new':
                    sx,sy=self.start_pixel;px,py=pixel
                    bounds=engine.fit_crop_ratio((min(sx,px),min(sy,py),max(sx,px),max(sy,py)),self.ratio)
                elif self.mode=='move':
                    x0,y0,x1,y1=self.start_bounds
                    dx=max(-x0,min(w-x1,pixel[0]-self.start_pixel[0]))
                    dy=max(-y0,min(h-y1,pixel[1]-self.start_pixel[1]))
                    bounds=(x0+dx,y0+dy,x1+dx,y1+dy)
                else:
                    bounds=engine.resize_crop(self.start_bounds,self.mode,pixel,self.source_size,self.ratio)
                self.selection_pixels=bounds
                self.selection.emit(*bounds);self.viewport().update()
            except ValueError:
                pass
            event.accept();return
        edge=self.hit_handle(pos)
        if edge in ('lt','rb'): cursor=QtCore.Qt.SizeFDiagCursor
        elif edge in ('rt','lb'): cursor=QtCore.Qt.SizeBDiagCursor
        elif edge in ('l','r'): cursor=QtCore.Qt.SizeHorCursor
        elif edge in ('t','b'): cursor=QtCore.Qt.SizeVerCursor
        elif self.source_size and self.selection_pixels != (0,0,*self.source_size) and self.selection_rect().contains(pos): cursor=QtCore.Qt.SizeAllCursor
        else: cursor=QtCore.Qt.CrossCursor
        self.setCursor(cursor)
    def mouseReleaseEvent(self,event):
        if self.pan_start is not None and event.button() in (QtCore.Qt.RightButton,QtCore.Qt.MiddleButton):
            self.pan_start=None;self.setCursor(QtCore.Qt.CrossCursor);event.accept();return
        if event.button()==QtCore.Qt.LeftButton:
            if self.mode: self.mouseMoveEvent(event)
            self.mode=None;event.accept()
    def paintEvent(self,event):
        super().paintEvent(event)
        if not self.source_size or self.item.pixmap().isNull(): return
        painter=QtGui.QPainter(self.viewport())
        area=self.image_rect().intersected(self.viewport().rect())
        painter.setClipRect(area)
        crop=self.selection_rect()
        if self.guide!='Off':
            painter.setPen(QtGui.QPen(QtGui.QColor(90,230,255,170),1,QtCore.Qt.DashLine))
            count=3 if self.guide.startswith('Thirds') else 10 if self.guide.startswith('Grid') else 2
            for part in range(1,count):
                x=crop.x()+round(crop.width()*part/count);y=crop.y()+round(crop.height()*part/count)
                painter.drawLine(x,crop.top(),x,crop.bottom());painter.drawLine(crop.left(),y,crop.right(),y)
            painter.fillRect(area.x(),area.y(),area.width(),18,QtGui.QColor(0,0,0,180))
            painter.setPen(QtGui.QColor(220,250,255));font=painter.font();font.setPixelSize(11);painter.setFont(font)
            for part in range(5):
                f=part/4;x=area.left()+round((area.width()-1)*f);y=area.top()+round((area.height()-1)*f)
                px,_=self.pixels_at(QtCore.QPoint(x,area.top()));_,py=self.pixels_at(QtCore.QPoint(area.left(),y))
                label=f'{px:,}';tx=min(x+2,area.right()-painter.fontMetrics().horizontalAdvance(label))
                painter.drawText(tx,area.top()+15,label)
                if part:
                    label=f'{py:,}';painter.fillRect(area.left(),max(area.top(),y-13),painter.fontMetrics().horizontalAdvance(label)+5,15,QtGui.QColor(0,0,0,180))
                    painter.drawText(area.left()+3,min(y,area.bottom()-1),label)
        painter.setPen(QtGui.QPen(QtGui.QColor('#5ae6ff'),1));painter.setBrush(QtCore.Qt.NoBrush);painter.drawRect(crop)
        painter.setBrush(QtGui.QColor('#effcff'))
        handles=[crop.topLeft(),crop.topRight(),crop.bottomLeft(),crop.bottomRight(),
                 QtCore.QPoint(crop.center().x(),crop.top()),QtCore.QPoint(crop.center().x(),crop.bottom()),
                 QtCore.QPoint(crop.left(),crop.center().y()),QtCore.QPoint(crop.right(),crop.center().y())]
        for point in handles:painter.drawRect(QtCore.QRect(point.x()-4,point.y()-4,8,8))
        painter.end()
