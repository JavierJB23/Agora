"""Reusable PC/mobile import dialog; returns bytes without storing private originals."""
from pathlib import Path
from io import BytesIO
import queue
from PySide6.QtCore import Qt,QTimer,QByteArray
from PySide6.QtGui import QPixmap,QImage
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QMessageBox
from .controls import SafeComboBox
from .answer_import import MAX_BYTES
from .transfer import UploadSession,local_addresses

def text(s):
    w=QLabel(s); w.setWordWrap(True); w.setTextFormat(Qt.TextFormat.PlainText); return w

class ImportDialog(QDialog):
    def __init__(self,parent,extensions=('.pdf','.docx')):
        super().__init__(parent); self.setWindowTitle('Importar documento'); self.resize(550,440); self.setAcceptDrops(True); self.extensions=extensions; self.item=None; self.session=None
        self.layout_=QVBoxLayout(self); self.layout_.setSpacing(12)
        title=text('¿Desde dónde quieres cargar tu documento?'); title.setObjectName('heading'); self.layout_.addWidget(title)
        self.layout_.addWidget(text('Selecciona un archivo o arrástralo aquí. Formatos: '+', '.join(extensions)+' · Máximo 25 MB.'))
        row=QHBoxLayout(); pc=QPushButton('Desde ordenador'); mobile=QPushButton('Desde móvil · QR'); pc.clicked.connect(self.pc); mobile.clicked.connect(self.mobile); row.addWidget(pc); row.addWidget(mobile); self.layout_.addLayout(row)
        self.info=text(''); self.layout_.addWidget(self.info)
        self.address=SafeComboBox(); self.address.hide(); self.address.currentTextChanged.connect(self.draw_qr); self.layout_.addWidget(self.address)
        self.qr=QLabel(); self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter); self.layout_.addWidget(self.qr)
        self.link=text(''); self.link.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); self.layout_.addWidget(self.link)
        self.layout_.addStretch(); cancel=QPushButton('Cancelar'); cancel.clicked.connect(self.reject); self.layout_.addWidget(cancel)
        self.timer=QTimer(self); self.timer.setInterval(200); self.timer.timeout.connect(self.poll)
        self.expiry=QTimer(self); self.expiry.setSingleShot(True); self.expiry.timeout.connect(self.expire)
        self.finished.connect(self.cleanup)
    def pc(self):
        path,_=QFileDialog.getOpenFileName(self,'Seleccionar documento','','Documentos ('+' '.join('*'+s for s in self.extensions)+')')
        if path: self.load(path)
    def load(self,path):
        try:
            p=Path(path)
            if p.suffix.lower() not in self.extensions: raise ValueError('Formato no admitido.')
            if not 0<p.stat().st_size<=MAX_BYTES: raise ValueError('Documento vacío o superior a 25 MB.')
            with p.open('rb') as f: data=f.read(MAX_BYTES+1)
            if not 0<len(data)<=MAX_BYTES: raise ValueError('Tamaño no válido.')
            self.item=(p.name,data); self.accept()
        except Exception as e: self.info.setText(str(e))
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls() and len(e.mimeData().urls())==1 and e.mimeData().urls()[0].isLocalFile(): e.acceptProposedAction()
    def dropEvent(self,e):
        urls=e.mimeData().urls()
        if len(urls)==1 and urls[0].isLocalFile(): e.acceptProposedAction(); self.load(urls[0].toLocalFile())
    def mobile(self):
        if self.session: return
        ips=local_addresses()
        if not ips: self.info.setText('No se ha encontrado una red local. Conecta ambos dispositivos a la misma Wi-Fi.'); return
        try: self.session=UploadSession(extensions=self.extensions)
        except OSError as e: self.info.setText('No se pudo iniciar la conexión local: '+str(e)); return
        self.info.setText('Escanea el QR con la cámara del móvil. Ambos dispositivos deben estar en la misma red privada. Si Windows pregunta, permite el acceso solo en redes privadas. Si no conecta, prueba otra dirección del desplegable.')
        self.address.clear(); self.address.addItems(ips); self.address.show(); self.draw_qr(self.address.currentText()); self.timer.start(); self.expiry.start(300000)
    def draw_qr(self,ip):
        if not self.session or not ip: return
        import qrcode
        from qrcode.image.svg import SvgPathImage
        url=self.session.url(ip); stream=BytesIO(); qrcode.make(url,image_factory=SvgPathImage,border=4).save(stream)
        renderer=QSvgRenderer(QByteArray(stream.getvalue())); image=QImage(256,256,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.white); painter=QPainter(image); renderer.render(painter); painter.end(); self.qr.setPixmap(QPixmap.fromImage(image)); self.link.setText(url)
    def poll(self):
        if not self.session: return
        try: self.item=self.session.items.get_nowait()
        except queue.Empty: return
        self.accept()
    def expire(self):
        self.cleanup(); self.qr.clear(); self.link.clear(); self.address.hide(); self.info.setText('Sesión caducada. Pulsa Desde móvil para generar otro QR.')
    def cleanup(self,*_):
        self.timer.stop(); self.expiry.stop()
        if self.session: self.session.close(); self.session=None
