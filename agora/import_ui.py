"""Reusable PC/mobile import dialog, with distinct source and QR screens."""
from pathlib import Path
from io import BytesIO
import queue
from PySide6.QtCore import Qt,QTimer,QByteArray,QSize
from PySide6.QtGui import QPixmap,QImage,QIcon,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QToolButton,QWidget,QStackedWidget)
from .controls import SafeComboBox
from .answer_import import MAX_BYTES
from .transfer import UploadSession,local_addresses
ASSETS=Path(__file__).resolve().parent.parent/'assets'
ALIGN=Qt.AlignmentFlag

def text(s):
    w=QLabel(s); w.setWordWrap(True); w.setTextFormat(Qt.TextFormat.PlainText); return w

def centered_button(s,fn):
    b=QPushButton(s); b.setObjectName('importCancel'); b.setFixedWidth(136); b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(fn); return b

class ImportDialog(QDialog):
    def __init__(self,parent,extensions=('.pdf','.docx')):
        super().__init__(parent); self.setWindowTitle('Importar documento'); self.setAcceptDrops(True); self.extensions=extensions; self.item=None; self.session=None
        root=QVBoxLayout(self); root.setContentsMargins(18,18,18,18); root.setSpacing(12)
        self.stack=QStackedWidget(); root.addWidget(self.stack)
        self.source=QWidget(); source=QVBoxLayout(self.source); source.setContentsMargins(0,0,0,0); source.setSpacing(14)
        title=text('¿Desde dónde quieres cargarlo?'); title.setObjectName('heading'); title.setAlignment(ALIGN.AlignCenter); source.addWidget(title)
        row=QHBoxLayout(); row.setSpacing(14)
        for name,asset,fn in [('Desde PC','monitor',self.pc),('Desde móvil','qr-code',self.mobile)]:
            b=QToolButton(); b.setObjectName('homeTile'); b.setText(name); b.setIcon(QIcon(str(ASSETS/(asset+'.svg')))); b.setIconSize(QSize(64,64)); b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon); b.setFixedSize(170,170); b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(fn); row.addWidget(b)
        source.addLayout(row); note=text('También puedes arrastrar un documento aquí.\nFormatos: '+', '.join(extensions)+f' · Hasta {MAX_BYTES//(1024**2)} MB.'); note.setObjectName('muted'); note.setAlignment(ALIGN.AlignCenter); source.addWidget(note)
        self.source_error=text(''); self.source_error.hide(); source.addWidget(self.source_error); self.stack.addWidget(self.source)
        self.mobile_page=QWidget(); mob=QVBoxLayout(self.mobile_page); mob.setContentsMargins(0,0,0,0); mob.setSpacing(12)
        title=text('Escanea el código QR'); title.setObjectName('heading'); title.setAlignment(ALIGN.AlignCenter); mob.addWidget(title)
        self.info=text(''); self.info.setAlignment(ALIGN.AlignCenter); mob.addWidget(self.info)
        self.qr=QLabel(); self.qr.setAlignment(ALIGN.AlignCenter); mob.addWidget(self.qr,1)
        self.address=SafeComboBox(); self.address.currentTextChanged.connect(self.draw_qr); self.address.hide()
        self.network=QPushButton('¿Problemas de conexión?'); self.network.setObjectName('importCancel'); self.network.setCheckable(True); self.network.toggled.connect(self.address.setVisible); mob.addWidget(self.network,0,ALIGN.AlignCenter); mob.addWidget(self.address)
        self.retry=centered_button('Generar otro QR',self.mobile); self.retry.hide(); mob.addWidget(self.retry,0,ALIGN.AlignCenter)
        self.stack.addWidget(self.mobile_page)
        self.cancel=centered_button('Cancelar',self.reject); root.addWidget(self.cancel,0,ALIGN.AlignCenter)
        self.setStyleSheet('QPushButton#importCancel {text-align:center;}'); self.resize(460,335)
        self.timer=QTimer(self); self.timer.setInterval(200); self.timer.timeout.connect(self.poll)
        self.expiry=QTimer(self); self.expiry.setSingleShot(True); self.expiry.timeout.connect(self.expire); self.finished.connect(self.cleanup)
    def error(self,s): self.source_error.setText(s); self.source_error.show(); self.adjustSize()
    def pc(self):
        path,_=QFileDialog.getOpenFileName(self,'Seleccionar documento','','Documentos ('+' '.join('*'+s for s in self.extensions)+')')
        if path: self.load(path)
    def load(self,path):
        try:
            p=Path(path)
            if p.suffix.lower() not in self.extensions: raise ValueError('Formato no admitido.')
            if not 0<p.stat().st_size<=MAX_BYTES: raise ValueError(f'Documento vacío o superior a {MAX_BYTES//(1024**2)} MB.')
            with p.open('rb') as f: data=f.read(MAX_BYTES+1)
            if not 0<len(data)<=MAX_BYTES: raise ValueError('Tamaño no válido.')
            self.item=(p.name,data); self.accept()
        except Exception as e: self.error(str(e))
    def dragEnterEvent(self,e):
        if self.stack.currentWidget() is self.source and e.mimeData().hasUrls() and len(e.mimeData().urls())==1 and e.mimeData().urls()[0].isLocalFile(): e.acceptProposedAction()
    def dropEvent(self,e):
        urls=e.mimeData().urls()
        if self.stack.currentWidget() is self.source and len(urls)==1 and urls[0].isLocalFile(): e.acceptProposedAction(); self.load(urls[0].toLocalFile())
    def mobile(self):
        if self.session: return
        ips=local_addresses()
        if not ips:
            if self.stack.currentWidget() is self.source: self.error('No se ha encontrado una red local.')
            else: self.info.setText('No se ha encontrado una red local. Inténtalo de nuevo.')
            return
        try: self.session=UploadSession(extensions=self.extensions)
        except OSError as e:
            if self.stack.currentWidget() is self.source: self.error('No se pudo iniciar la conexión local: '+str(e))
            else: self.info.setText('No se pudo iniciar la conexión local: '+str(e))
            return
        self.info.setText('Abre la cámara del móvil y escanea el QR. Ambos dispositivos deben estar en la misma red privada. Si Windows pregunta, permite el acceso solo en redes privadas.')
        self.retry.hide(); self.network.show(); self.network.setChecked(False); self.address.clear(); self.address.addItems(ips); self.draw_qr(self.address.currentText()); self.stack.setCurrentWidget(self.mobile_page); self.resize(480,510); self.timer.start(); self.expiry.start(300000)
    def draw_qr(self,ip):
        if not self.session or not ip: return
        import qrcode
        from qrcode.image.svg import SvgPathImage
        stream=BytesIO(); qrcode.make(self.session.url(ip),image_factory=SvgPathImage,border=4).save(stream)
        renderer=QSvgRenderer(QByteArray(stream.getvalue())); image=QImage(288,288,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.white); painter=QPainter(image); renderer.render(painter); painter.end(); self.qr.setPixmap(QPixmap.fromImage(image))
    def poll(self):
        if not self.session: return
        try: self.item=self.session.items.get_nowait()
        except queue.Empty: return
        self.accept()
    def expire(self):
        self.cleanup(); self.qr.clear(); self.network.hide(); self.address.hide(); self.info.setText('El QR ha caducado. Genera otro para continuar.'); self.retry.show()
    def cleanup(self,*_):
        self.timer.stop(); self.expiry.stop()
        if self.session: self.session.close(); self.session=None
