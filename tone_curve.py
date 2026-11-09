"""Five-point monotone luminance curve with three draggable interior handles."""
from PySide6 import QtCore,QtGui,QtWidgets as W
from astro_adjustments import NEUTRAL_CURVE,validate_curve,curve_lut


class ToneCurve(W.QWidget):
    changed=QtCore.Signal();editStarted=QtCore.Signal();editFinished=QtCore.Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.values=NEUTRAL_CURVE;self.dragging=False;self.selected=None
        self.setMinimumHeight(170);self.setMinimumWidth(220);self.setMouseTracking(True)
        self.setToolTip('Drag the three interior points up/down. Left: shadows; middle: midtones; right: highlights. Black and white endpoints are fixed. The curve remains monotone. Reset curve restores the diagonal.')
        self.setAccessibleName('Luminance tone curve')
    def set_values(self,values,emit=False):
        self.values=validate_curve(values);self.update()
        if emit:self.changed.emit()
    def area(self):return QtCore.QRectF(self.rect()).adjusted(24,12,-12,-24)
    def point(self,index):
        r=self.area();return QtCore.QPointF(r.left()+index*r.width()/4,r.bottom()-self.values[index]*r.height()/1000)
    def paintEvent(self,event):
        p=QtGui.QPainter(self);p.setRenderHint(QtGui.QPainter.Antialiasing);p.fillRect(self.rect(),QtGui.QColor('#071321'));r=self.area()
        p.setPen(QtGui.QPen(QtGui.QColor('#31516c'),1));p.drawRect(r)
        for i in range(1,4):
            p.drawLine(QtCore.QPointF(r.left()+r.width()*i/4,r.top()),QtCore.QPointF(r.left()+r.width()*i/4,r.bottom()))
            p.drawLine(QtCore.QPointF(r.left(),r.top()+r.height()*i/4),QtCore.QPointF(r.right(),r.top()+r.height()*i/4))
        p.setPen(QtGui.QPen(QtGui.QColor('#73879a'),1,QtCore.Qt.DashLine));p.drawLine(r.bottomLeft(),r.topRight())
        x,y=curve_lut(self.values);path=QtGui.QPainterPath()
        for i in range(0,len(x),16):
            point=QtCore.QPointF(r.left()+float(x[i])*r.width(),r.bottom()-float(y[i])*r.height())
            if i==0:path.moveTo(point)
            else:path.lineTo(point)
        path.lineTo(r.topRight());p.setPen(QtGui.QPen(QtGui.QColor('#5ae6ff'),2));p.drawPath(path)
        for i in range(5):
            p.setBrush(QtGui.QColor('#ffffff' if i in (0,4) else '#5ae6ff'));p.drawEllipse(self.point(i),5,5)
        p.setPen(QtGui.QColor('#cde1f3'));p.drawText(24,self.height()-5,'Shadows → Input brightness → Highlights');p.end()
    def mousePressEvent(self,event):
        if event.button()!=QtCore.Qt.LeftButton:return
        pos=event.position();i=min(range(1,4),key=lambda j:abs(self.point(j).x()-pos.x()))
        if self.area().adjusted(-8,-8,8,8).contains(pos):
            self.editStarted.emit();self.dragging=True;self.selected=i;self.move_point(pos);event.accept()
    def move_point(self,pos):
        r=self.area();value=round((r.bottom()-pos.y())/max(r.height(),1)*1000);values=list(self.values);i=self.selected
        values[i]=max(values[i-1],min(values[i+1],value))
        if tuple(values)!=self.values:self.values=tuple(values);self.update();self.changed.emit()
    def mouseMoveEvent(self,event):
        if self.dragging:self.move_point(event.position());event.accept()
    def mouseReleaseEvent(self,event):
        if event.button()==QtCore.Qt.LeftButton and self.dragging:
            self.move_point(event.position());self.dragging=False;self.selected=None;self.editFinished.emit();event.accept()
