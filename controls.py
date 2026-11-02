"""Accessible desktop controls with clear indicators and anchored value labels."""
from PySide6 import QtCore,QtGui,QtWidgets as W


class VisibleGpuCheckBox(W.QCheckBox):
    def paintEvent(self,event):
        super().paintEvent(event)
        option=W.QStyleOptionButton();self.initStyleOption(option)
        rect=self.style().subElementRect(W.QStyle.SE_CheckBoxIndicator,option,self).adjusted(1,1,-1,-1)
        painter=QtGui.QPainter(self);painter.setRenderHint(QtGui.QPainter.Antialiasing)
        color=QtGui.QColor('#ffffff' if self.isEnabled() else '#91a5bf')
        painter.setPen(QtGui.QPen(color,2))
        painter.setBrush(QtGui.QColor('#247eb6' if self.isChecked() else '#071321'))
        painter.drawRoundedRect(QtCore.QRectF(rect),3,3)
        if self.isChecked():
            path=QtGui.QPainterPath()
            path.moveTo(rect.left()+rect.width()*.18,rect.top()+rect.height()*.52)
            path.lineTo(rect.left()+rect.width()*.42,rect.top()+rect.height()*.75)
            path.lineTo(rect.left()+rect.width()*.84,rect.top()+rect.height()*.23)
            painter.setPen(QtGui.QPen(color,2.5,QtCore.Qt.SolidLine,QtCore.Qt.RoundCap,QtCore.Qt.RoundJoin))
            painter.drawPath(path)
        painter.end()


class WheelSlider(W.QSlider):
    """Keep the outer 5% on each side available for panel scrolling."""
    def wheelEvent(self,event):
        margin=self.width()*.05
        if event.position().x()<margin or event.position().x()>self.width()-margin:
            event.ignore();return
        super().wheelEvent(event)


class SliderValueRow(W.QWidget):
    def __init__(self,minimum,maximum,value,parent=None):
        super().__init__(parent)
        self.setMinimumHeight(58);self.setSizePolicy(W.QSizePolicy.Expanding,W.QSizePolicy.Fixed)
        self.slider=WheelSlider(QtCore.Qt.Horizontal,self)
        self.slider.setMinimumHeight(36);self.slider.setRange(minimum,maximum);self.slider.setValue(value)
        self.value_label=W.QLabel(str(value),self)
        self.value_label.setObjectName('sliderValue');self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.value_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.slider.valueChanged.connect(self.position_value)
        QtCore.QTimer.singleShot(0,self.position_value)
    def sizeHint(self):return QtCore.QSize(180,58)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.slider.setGeometry(0,0,self.width(),36)
        self.position_value()
    def showEvent(self,event):
        super().showEvent(event);self.position_value()
    def position_value(self,*args):
        self.value_label.setText(str(self.slider.value()));self.value_label.adjustSize()
        option=W.QStyleOptionSlider();self.slider.initStyleOption(option)
        handle=self.slider.style().subControlRect(W.QStyle.CC_Slider,option,W.QStyle.SC_SliderHandle,self.slider)
        x=round(handle.center().x()-self.value_label.width()/2)
        x=max(0,min(self.width()-self.value_label.width(),x))
        self.value_label.move(x,36)
