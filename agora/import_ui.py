"""Reusable PC/mobile import dialog, with distinct source and QR screens."""
from pathlib import Path
from io import BytesIO
import queue
from PySide6.QtCore import Qt,QTimer,QByteArray,QSize
from PySide6.QtGui import QPixmap,QImage,QIcon,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QToolButton,QWidget,QStackedWidget)
from .controls import SafeComboBox, CenteredTile
from .answer_import import MAX_BYTES
from .transfer import UploadSession,local_addresses
ASSETS=Path(__file__).resolve().parent.parent/'assets'
ALIGN=Qt.AlignmentFlag

def text(s):
    w=QLabel(s); w.setWordWrap(True); w.setTextFormat(Qt.TextFormat.PlainText); return w

def centered_button(s,fn):
    b=QPushButton(s); b.setObjectName('importCancel'); b.setFixedWidth(136); b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(fn); return b

class ImportDialog(QDialog):
    def __init__(self,parent,extensions=('.pdf','.docx'),multiple=False,max_files=2):
        super().__init__(parent); self.setWindowTitle('Importar documento'); self.setAcceptDrops(True); self.extensions=extensions; self.item=None; self.items=[]; self.multiple=multiple; self.max_files=max(2,min(20,int(max_files))) if multiple else 1; self.session=None
        root=QVBoxLayout(self); root.setContentsMargins(18,18,18,18); root.setSpacing(12)
        self.stack=QStackedWidget(); root.addWidget(self.stack)
        self.source=QWidget(); source=QVBoxLayout(self.source); source.setContentsMargins(0,0,0,0); source.setSpacing(14)
        title=text('¿Desde dónde quieres cargarlo?'); title.setObjectName('heading'); title.setAlignment(ALIGN.AlignCenter); source.addWidget(title)
        row=QHBoxLayout(); row.setSpacing(14)
        for name,asset,fn in [('Desde PC','monitor',self.pc),('Desde móvil','qr-code',self.mobile)]:
            b=CenteredTile(name,QIcon(str(ASSETS/(asset+'.svg')))); b.setFixedSize(170,170); b.clicked.connect(fn); row.addWidget(b)
        source.addLayout(row); note=text((f'Selecciona o arrastra hasta {self.max_files} archivos (100 MB en total).\nFormatos: ' if multiple else 'También puedes arrastrar un documento aquí.\nFormatos: ')+', '.join(extensions)+f' · Hasta {MAX_BYTES//(1024**2)} MB.'); note.setObjectName('muted'); note.setAlignment(ALIGN.AlignCenter); source.addWidget(note)
        self.source_error=text(''); self.source_error.hide(); source.addWidget(self.source_error); self.stack.addWidget(self.source)
        self.mobile_page=QWidget(); mob=QVBoxLayout(self.mobile_page); mob.setContentsMargins(0,0,0,0); mob.setSpacing(12)
        title=text('Escanea el código QR'); title.setObjectName('heading'); title.setAlignment(ALIGN.AlignCenter); mob.addWidget(title)
        self.info=text(''); self.info.setAlignment(ALIGN.AlignCenter); mob.addWidget(self.info)
        self.qr=QLabel(); self.qr.setAlignment(ALIGN.AlignCenter); mob.addWidget(self.qr,1)
        self.address=SafeComboBox(); self.address.currentTextChanged.connect(self.draw_qr); self.address.hide()
        self.network=QPushButton('¿Problemas de conexión?'); self.network.setObjectName('importCancel'); self.network.setCheckable(True); self.network.toggled.connect(self.address.setVisible); mob.addWidget(self.network,0,ALIGN.AlignCenter); mob.addWidget(self.address)
        self.received_info=text(''); self.received_info.setAlignment(ALIGN.AlignCenter); self.received_info.hide(); mob.addWidget(self.received_info)
        self.finish_button=centered_button('Importar archivos',self.finish_upload); self.finish_button.setFixedWidth(210); self.finish_button.setObjectName('primary'); self.finish_button.setStyleSheet('text-align:center;'); self.finish_button.hide(); mob.addWidget(self.finish_button,0,ALIGN.AlignCenter)
        self.retry=centered_button('Generar otro QR',self.mobile); self.retry.hide(); mob.addWidget(self.retry,0,ALIGN.AlignCenter)
        self.stack.addWidget(self.mobile_page)
        self.cancel=centered_button('Cancelar',self.reject); root.addWidget(self.cancel,0,ALIGN.AlignCenter)
        self.setStyleSheet('QPushButton#importCancel {text-align:center;}'); self.resize(460,335)
        self.timer=QTimer(self); self.timer.setInterval(200); self.timer.timeout.connect(self.poll)
        self.expiry=QTimer(self); self.expiry.setSingleShot(True); self.expiry.timeout.connect(self.expire); self.finished.connect(self.cleanup)
    def error(self,s): self.source_error.setText(s); self.source_error.show(); self.adjustSize()
    def pc(self):
        pattern='Documentos ('+' '.join('*'+s for s in self.extensions)+')'
        if self.multiple:
            paths,_=QFileDialog.getOpenFileNames(self,'Seleccionar hojas','',pattern)
            if paths: self.load_many(paths)
        else:
            path,_=QFileDialog.getOpenFileName(self,'Seleccionar documento','',pattern)
            if path: self.load(path)
    def load(self,path): self.load_many([path])
    def load_many(self,paths):
        try:
            if not 1<=len(paths)<=self.max_files: raise ValueError(f'Selecciona como máximo {self.max_files} archivos.')
            files=[Path(x) for x in paths]
            if any(p.suffix.lower() not in self.extensions for p in files): raise ValueError('Formato no admitido.')
            if any(p.stat().st_size<=0 for p in files) or sum(p.stat().st_size for p in files)>MAX_BYTES: raise ValueError('Archivos vacíos o superiores a 100 MB en total.')
            items=[]; remaining=MAX_BYTES
            for p in files:
                with p.open('rb') as f: data=f.read(remaining+1)
                if not 0<len(data)<=remaining: raise ValueError('Tamaño no válido.')
                items.append((p.name,data)); remaining-=len(data)
            self.items=items; self.item=items[0]; self.accept()
        except Exception as e: self.error(str(e))
    def dragEnterEvent(self,e):
        urls=e.mimeData().urls()
        if self.stack.currentWidget() is self.source and 1<=len(urls)<=self.max_files and all(u.isLocalFile() for u in urls): e.acceptProposedAction()
    def dropEvent(self,e):
        urls=e.mimeData().urls()
        if self.stack.currentWidget() is self.source and urls and all(u.isLocalFile() for u in urls): e.acceptProposedAction(); self.load_many([u.toLocalFile() for u in urls])
    def mobile(self):
        if self.session: return
        ips=local_addresses()
        if not ips:
            if self.stack.currentWidget() is self.source: self.error('No se ha encontrado una red local.')
            else: self.info.setText('No se ha encontrado una red local. Inténtalo de nuevo.')
            return
        try: self.session=UploadSession(extensions=self.extensions,multiple=self.multiple,max_files=self.max_files-len(self.items),reusable=self.multiple,max_bytes=MAX_BYTES-sum(len(data) for _,data in self.items))
        except OSError as e:
            if self.stack.currentWidget() is self.source: self.error('No se pudo iniciar la conexión local: '+str(e))
            else: self.info.setText('No se pudo iniciar la conexión local: '+str(e))
            return
        self.info.setText('Abre la cámara del móvil y escanea el QR. Ambos dispositivos deben estar en la misma red privada. Si Windows pregunta, permite el acceso solo en redes privadas.')
        if self.multiple: self.info.setText(self.info.text()+' Puedes enviar varias tandas sin volver a escanear. Pulsa Importar archivos al terminar.')
        self.retry.hide(); self.network.show(); self.network.setChecked(False); self.address.clear(); self.address.addItems(ips); self.draw_qr(self.address.currentText()); self.stack.setCurrentWidget(self.mobile_page); self.resize(480,min(600,self.screen().availableGeometry().height()-80)); self.timer.start(); self.expiry.start(900000 if self.multiple else 300000)
    def draw_qr(self,ip):
        if not self.session or not ip: return
        import qrcode
        from qrcode.image.svg import SvgPathImage
        stream=BytesIO(); qrcode.make(self.session.url(ip),image_factory=SvgPathImage,border=4).save(stream)
        renderer=QSvgRenderer(QByteArray(stream.getvalue())); image=QImage(288,288,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.white); painter=QPainter(image); renderer.render(painter); painter.end(); self.qr.setPixmap(QPixmap.fromImage(image))
    def poll(self):
        if not self.session: return
        try: received=self.session.items.get_nowait()
        except queue.Empty: return
        if not self.multiple:
            self.items=[received]; self.item=self.items[0]; self.accept(); return
        self.items.extend(received); self.item=self.items[0]
        full=len(self.items)>=self.max_files or sum(len(data) for _,data in self.items)>=MAX_BYTES
        self.received_info.setText(f'{len(received)} archivo(s) nuevo(s) recibido(s). Total: {len(self.items)}. '+('Límite alcanzado; importa los recibidos.' if full else 'Puedes enviar más o importar los recibidos.'))
        self.received_info.setToolTip('\n'.join(name for name,_ in self.items))
        self.received_info.show(); self.finish_button.setText(f'Importar archivos ({len(self.items)})'); self.finish_button.show(); self.expiry.start(900000 if self.multiple else 300000)
    def finish_upload(self):
        if self.session and not self.session.seal():
            self.received_info.setText('Hay una transferencia en curso. Espera a que termine.'); return
        self.poll()
        if self.items: self.accept()
    def expire(self):
        if self.session and not self.session.seal(): self.expiry.start(30000); return
        self.poll()
        self.cleanup(); self.qr.clear(); self.network.hide(); self.address.hide(); self.info.setText('El QR ha caducado. Puedes importar lo recibido o generar otro para continuar.'); self.retry.setVisible(len(self.items)<self.max_files and sum(len(data) for _,data in self.items)<MAX_BYTES)
    def reject(self):
        if self.multiple and self.items:
            from .manual import confirm
            if not confirm(self,'Descartar archivos',f'Se han recibido {len(self.items)} archivos. ¿Cerrar sin importarlos?'): return
        super().reject()
    def cleanup(self,*_):
        self.timer.stop(); self.expiry.stop()
        if self.session: self.session.close(); self.session=None
