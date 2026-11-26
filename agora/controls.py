"""Safe form widgets: scrolling the page must never change exam settings."""
from PySide6.QtWidgets import QComboBox, QSpinBox, QDoubleSpinBox

class SafeComboBox(QComboBox):
    def wheelEvent(self, event):
        # The popup list handles its own scrolling; the closed field never changes.
        event.ignore()

class SafeSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class SafeDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()


# One centered icon/text layout for every large navigation/import tile.
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QIcon, QPainter, QColor
from PySide6.QtWidgets import QToolButton, QStyle, QStyleOptionToolButton

class CenteredTile(QToolButton):
    def __init__(self, name, artwork):
        super().__init__()
        self.setObjectName('homeTile'); self.setText(name); self.setAccessibleName(name)
        self.setIcon(artwork); self.setIconSize(QSize(64,64))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def content_rects(self):
        fm=self.fontMetrics(); lines=self.text().count('\n')+1
        iw=min(self.iconSize().width(),max(16,self.width()-20))
        th=lines*fm.lineSpacing()+4; gap=12
        ih=min(self.iconSize().height(),max(16,self.height()-th-gap-16),iw)
        top=(self.height()-ih-gap-th)//2
        return QRect((self.width()-ih)//2,top,ih,ih), QRect(8,top+ih+gap,max(1,self.width()-16),th)

    def paintEvent(self,event):
        opt=QStyleOptionToolButton(); self.initStyleOption(opt)
        opt.text=''; opt.icon=QIcon()
        painter=QPainter(self)
        self.style().drawComplexControl(QStyle.ComplexControl.CC_ToolButton,opt,painter,self)
        ir,tr=self.content_rects()
        self.icon().paint(painter,ir,Qt.AlignmentFlag.AlignCenter,QIcon.Mode.Normal if self.isEnabled() else QIcon.Mode.Disabled)
        painter.setFont(self.font()); painter.setPen(QColor('#73425A'))
        painter.drawText(tr,Qt.AlignmentFlag.AlignCenter,self.text()); painter.end()
