"""Display-only RGB histogram and clipping counts for the rendered preview."""
import numpy as np
from PySide6 import QtCore,QtGui,QtWidgets as W


def histogram_data(image,valid=None):
    if valid is None:valid=np.ones(image.shape[:2],dtype=bool)
    values=image[valid]
    if not len(values):return np.zeros((3,256),dtype=np.int64),0.,0.
    bins=np.stack([np.histogram(values[:,i],bins=256,range=(0,1))[0] for i in range(3)])
    return bins,float(np.mean(np.any(values<=0,axis=-1))*100),float(np.mean(np.any(values>=1,axis=-1))*100)


class HistogramView(W.QWidget):
    def __init__(self):
        super().__init__();self.setMinimumHeight(76);self.setMaximumHeight(90)
        self.bins=np.zeros((3,256),dtype=np.int64)
        self.setToolTip('RGB distribution of the rendered preview sample, with logarithmic vertical scale. Excludes pixels without image coverage.')
    def set_data(self,bins):self.bins=bins;self.update()
    def paintEvent(self,event):
        painter=QtGui.QPainter(self);painter.fillRect(self.rect(),QtGui.QColor('#071321'))
        area=self.rect().adjusted(7,5,-7,-8)
        painter.setPen(QtGui.QPen(QtGui.QColor('#284c70'),1));painter.drawRect(area)
        counts=np.log1p(self.bins);peak=max(float(counts.max()),1)
        for channel,color in enumerate(('#ff7d86','#79e2a3','#80bdff')):
            path=QtGui.QPainterPath()
            for i,value in enumerate(counts[channel]):
                x=area.left()+i*area.width()/255;y=area.bottom()-value*area.height()/peak
                if i==0:path.moveTo(x,y)
                else:path.lineTo(x,y)
            painter.setPen(QtGui.QPen(QtGui.QColor(color),1));painter.drawPath(path)
        painter.end()
