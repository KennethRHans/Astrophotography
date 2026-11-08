"""Manual annotations in original image coordinates, shared by preview and export."""
import math
from PySide6 import QtCore, QtGui, QtWidgets as W


def validate_annotations(items, shape):
    if not isinstance(items,list) or len(items)>500:raise ValueError('Invalid annotation list (maximum 500)')
    h,w,_=shape
    for a in items:
        if not isinstance(a,dict) or a.get('kind') not in ('Text','Arrow','Circle'):raise ValueError('Invalid annotation type')
        if not isinstance(a.get('text'),str) or len(a['text'])>200:raise ValueError('Invalid annotation text')
        if not isinstance(a.get('color'),str) or not QtGui.QColor(a['color']).isValid():raise ValueError('Invalid annotation color')
        for key,limit in (('x',w),('y',h)):
            v=a.get(key)
            if type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<limit:raise ValueError('Annotation lies outside original image')
        if type(a.get('size')) is not int or not 8<=a['size']<=96:raise ValueError('Invalid annotation size')
    return items


def paint_annotations(painter,items,crop,original_width):
    x0,y0,x1,y1=crop
    painter.save();painter.setClipRect(QtCore.QRectF(0,0,x1-x0,y1-y0))
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    for a in items:
        if not x0<=a['x']<x1 or not y0<=a['y']<y1:continue
        x,y=a['x']-x0,a['y']-y0
        size=max(1.,original_width*a['size']/1200.)
        pen=QtGui.QPen(QtGui.QColor(a['color']),max(1.,size/12));painter.setPen(pen);painter.setBrush(QtCore.Qt.NoBrush)
        if a['kind']=='Circle':painter.drawEllipse(QtCore.QPointF(x,y),size*2,size*2)
        elif a['kind']=='Arrow':
            start=QtCore.QPointF(x+size*3,y-size*3);tip=QtCore.QPointF(x,y)
            painter.drawLine(start,tip)
            painter.drawLine(tip,QtCore.QPointF(x+size,y-size*.2));painter.drawLine(tip,QtCore.QPointF(x+size*.2,y-size))
        if a['text']:
            font=QtGui.QFont('Arial');font.setPixelSize(max(1,round(size)));painter.setFont(font)
            pos=QtCore.QPointF(x+size*.5,y-size*.5)
            path=QtGui.QPainterPath();path.addText(pos,font,a['text'])
            painter.setPen(QtGui.QPen(QtGui.QColor('black'),max(1.,size/8)))
            painter.setBrush(QtGui.QColor(a['color']));painter.drawPath(path);painter.fillPath(path,QtGui.QColor(a['color']))
    painter.restore()


class LabelsPanel(W.QWidget):
    place=QtCore.Signal();changed=QtCore.Signal();remove=QtCore.Signal();clear=QtCore.Signal()
    def __init__(self):
        super().__init__();layout=W.QVBoxLayout(self)
        hint=W.QLabel('Manual labels: choose a type, then click Place and click the image. Coordinates follow the original image through cropping.');hint.setWordWrap(True);layout.addWidget(hint)
        self.kind=W.QComboBox();self.kind.addItems(['Text','Arrow','Circle']);layout.addWidget(self.kind)
        self.text=W.QLineEdit();self.text.setMaxLength(200);self.text.setPlaceholderText('Object name or note');layout.addWidget(self.text)
        self.color=W.QComboBox()
        for name,value in [('Cyan','#5ae6ff'),('White','#ffffff'),('Yellow','#ffff00'),('Orange','#ff9900'),('Red','#ff5555'),('Green','#55ff88')]:self.color.addItem(name,value)
        layout.addWidget(self.color)
        self.size=W.QSpinBox();self.size.setRange(8,96);self.size.setValue(24);self.size.setPrefix('Text size: ');layout.addWidget(self.size)
        self.place_button=W.QPushButton('Place on image');self.place_button.clicked.connect(self.place);layout.addWidget(self.place_button)
        self.visible=W.QCheckBox('Show labels');self.visible.setChecked(True);layout.addWidget(self.visible)
        self.list=W.QListWidget();layout.addWidget(self.list)
        self.apply_button=W.QPushButton('Apply changes to selected');self.apply_button.clicked.connect(self.changed);layout.addWidget(self.apply_button)
        self.remove_button=W.QPushButton('Remove selected');self.remove_button.clicked.connect(self.remove);layout.addWidget(self.remove_button)
        self.clear_button=W.QPushButton('Clear all labels');self.clear_button.clicked.connect(self.clear);layout.addWidget(self.clear_button)
        note=W.QLabel('Automatic object identification will require plate solving and is planned for a later release. Export a labeled copy from section 5.');note.setWordWrap(True);layout.addWidget(note)
    def values(self):return dict(kind=self.kind.currentText(),text=self.text.text().strip(),color=self.color.currentData(),size=self.size.value())
