"""Review and store a blank model. The live exam remains untouched."""
from pathlib import Path
from io import BytesIO
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt,QThread,Signal,QEventLoop
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QLineEdit,QMessageBox,QInputDialog,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox,QProgressDialog,QScrollArea,QSizePolicy)
from .controls import SafeSpinBox
from .omr_ui import pix,CornerImage,compact_btn
from .import_ui import ImportDialog
from . import omr
from .external_models import ExternalLibrary,learn_items,preview,metadata,propose_starts,manual_block,Page,Block
from .manual import confirm
A=Qt.AlignmentFlag

class LearnWorker(QThread):
    def __init__(self,items,options,parent):
        super().__init__(parent); self.items=items; self.options=options; self.pages=None; self.error=None
    def run(self):
        try: self.pages=learn_items(self.items,self.options)
        except Exception as e: self.error=str(e)

def get_library(parent): return ExternalLibrary(parent.window().storage.directory)

def import_model(parent):
    d=ImportDialog(parent,omr.EXTENSIONS,multiple=True,max_files=20); d.destination_label='Mi temario · Importar modelo en blanco'
    if d.exec()==QDialog.DialogCode.Accepted: return receive_items(parent,d.items)
    return None

def receive_items(parent,items):
    d=QDialog(parent); d.setWindowTitle('Aprender modelo en blanco'); l=QVBoxLayout(d); form=QGridLayout(); l.addLayout(form)
    name=QLineEdit(Path(items[0][0]).stem[:100]); name.setMaxLength(100); form.addWidget(QLabel('Nombre del modelo'),0,0); form.addWidget(name,0,1)
    fields=[]
    for i,(title,lo,hi,value) in enumerate([('Preguntas ordinarias',1,500,120),('Preguntas de reserva',0,100,0),('Casillas impresas por fila',2,5,3)],1):
        w=SafeSpinBox(); w.setRange(lo,hi); w.setValue(value); fields.append(w); form.addWidget(QLabel(title),i,0); form.addWidget(w,i,1)
    row=QHBoxLayout(); row.addWidget(compact_btn('Cancelar',d.reject)); row.addWidget(compact_btn('Detectar casillas',d.accept,True)); l.addLayout(row)
    if d.exec()!=QDialog.DialogCode.Accepted: return None
    q,r,o=[w.value() for w in fields]; title=name.text().strip()
    if not title: QMessageBox.warning(parent,'Nombre del modelo','Introduce un nombre.'); return None
    progress=QProgressDialog('Reconociendo la estructura de las hojas…','',0,0,parent); progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setMinimumDuration(0); progress.show()
    worker=LearnWorker(items,o,parent); loop=QEventLoop(); worker.finished.connect(loop.quit); worker.start();
    if not worker.isFinished(): loop.exec()
    worker.wait(); progress.close(); pages,error=worker.pages,worker.error; worker.items=[]; worker.pages=None; worker.deleteLater()
    if error: QMessageBox.warning(parent,'No se pudo importar',error); return None
    propose_starts(pages,q)
    review=ReviewDialog(parent,title,pages,q,r,o,items,get_library(parent))
    if review.exec()==QDialog.DialogCode.Accepted: return review.saved_id
    return None

class ReviewDialog(QDialog):
    def __init__(self,parent,name,pages,q,r,o,items,library,read_only=False):
        super().__init__(parent); self.name=name; self.pages=pages; self.q=q; self.r=r; self.o=o; self.items=items; self.library=library; self.read_only=read_only; self.index=0; self.saved_id=None
        self.setWindowTitle('Consultar modelo externo' if read_only else 'Revisar modelo en blanco'); self.resize(1050,min(760,self.screen().availableGeometry().height()-60)); root=QVBoxLayout(self)
        heading=QLabel(name); heading.setObjectName('heading'); heading.setWordWrap(True); root.addWidget(heading)
        self.summary=QLabel(); root.addWidget(self.summary); body=QHBoxLayout(); root.addLayout(body,1)
        self.paper=QLabel(); self.paper.setAlignment(A.AlignCenter); self.paper.setMinimumSize(160,200); self.paper.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored); self.paper.setStyleSheet('background:#EDE5E9;border-radius:8px;'); body.addWidget(self.paper,3)
        side=QVBoxLayout(); body.addLayout(side,2); self.source=QLabel(); self.source.setWordWrap(True); side.addWidget(self.source)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['Bloque','Primera pregunta','Filas','Última']); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.verticalHeader().hide(); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection); side.addWidget(self.table,1)
        if not read_only:
            self.table.cellChanged.connect(self.update_start)
            for t,fn in [('Añadir bloque',self.add),('Recortar filas',self.trim),('Eliminar bloque',self.remove)]: side.addWidget(compact_btn(t,fn))
            self.checked=QCheckBox('He comprobado las casillas y la numeración de todas las páginas'); self.checked.setStyleSheet('QCheckBox {spacing:8px;}'); root.addWidget(self.checked)
        nav=QHBoxLayout(); self.prev=compact_btn('‹ Anterior',lambda:self.go(-1)); self.next=compact_btn('Siguiente ›',lambda:self.go(1)); self.counter=QLabel(); nav.addWidget(self.prev); nav.addStretch(); nav.addWidget(self.counter); nav.addStretch(); nav.addWidget(self.next); root.addLayout(nav)
        action=QHBoxLayout(); action.addWidget(compact_btn('Cerrar' if read_only else 'Cancelar',self.reject)); action.addStretch()
        if not read_only: action.addWidget(compact_btn('Guardar modelo',self.save,True))
        root.addLayout(action); self.refresh()
    def refresh(self):
        p=self.pages[self.index]; self.table.blockSignals(True); self.table.setRowCount(len(p.blocks))
        for i,b in enumerate(p.blocks):
            for j,value in enumerate((str(i+1),b.start,str(len(b.rows)),self.last_number(b))):
                it=QTableWidgetItem(value); it.setTextAlignment(A.AlignCenter)
                if j!=1 or self.read_only: it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i,j,it)
        self.table.blockSignals(False); self.source.setText(p.source if self.read_only else p.source+'\nComprueba el primer número de cada bloque. R1 = primera reserva.'); self.counter.setText(f'{self.index+1} / {len(self.pages)}'); self.prev.setEnabled(self.index>0); self.next.setEnabled(self.index+1<len(self.pages)); self.fit(); self.update_summary()
    def last_number(self,b):
        try:
            start=b.start.strip().upper().replace('-',''); reserve=start.startswith('R'); n=int(start.lstrip('R')); end=n+len(b.rows)-1
            if reserve: return 'R'+str(end)
            return str(end) if end<=self.q or n>self.q else 'R'+str(end-self.q)
        except ValueError: return '—'
    def update_summary(self):
        count=sum(len(b.rows) for p in self.pages for b in p.blocks); self.summary.setText(f'{self.q} ordinarias · {self.r} reservas · {self.o} opciones · {count}/{self.q+self.r} filas reconocidas')
    def fit(self):
        self.paper.setPixmap(pix(preview(self.pages[self.index])).scaled(self.paper.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'paper'): self.fit()
    def go(self,delta):
        if 0<=self.index+delta<len(self.pages): self.index+=delta; self.refresh()
    def update_start(self,i,j):
        if j==1:
            b=self.pages[self.index].blocks[i]; b.start=self.table.item(i,j).text(); self.checked.setChecked(False); self.table.blockSignals(True); self.table.item(i,3).setText(self.last_number(b)); self.table.blockSignals(False)
    def remove(self):
        i=self.table.currentRow()
        if i>=0 and confirm(self,'Eliminar bloque','¿Eliminar únicamente este bloque del modelo?'):
            self.pages[self.index].blocks.pop(i); self.checked.setChecked(False); self.refresh()
    def trim(self):
        i=self.table.currentRow()
        if i<0: return
        b=self.pages[self.index].blocks[i]; a,ok=QInputDialog.getInt(self,'Recortar filas','Omitir filas iniciales',0,0,len(b.rows)-1)
        if not ok: return
        z,ok=QInputDialog.getInt(self,'Recortar filas','Omitir filas finales',0,0,len(b.rows)-1-a)
        if ok: b.rows=b.rows[a:len(b.rows)-z]; self.checked.setChecked(False); self.refresh()
    def add(self):
        start,ok=QInputDialog.getText(self,'Añadir bloque','Primera pregunta (1, 31, R1…)')
        if not ok: return
        rows,ok=QInputDialog.getInt(self,'Añadir bloque','Número de filas',30,1,500)
        if not ok: return
        d=QDialog(self); d.setWindowTitle('Definir bloque de la hoja en blanco'); d.resize(720,min(790,self.screen().availableGeometry().height()-60)); l=QVBoxLayout(d); status=QLabel(); l.addWidget(status)
        needed=2 if rows==1 else 4; refs=['Primera fila · primera opción','Primera fila · última opción','Última fila · última opción','Última fila · primera opción']; apply=compact_btn('Añadir',d.accept,True)
        def update(n): status.setText(refs[n] if n<needed else 'Referencias seleccionadas'); apply.setEnabled(n==needed)
        im=CornerImage(self.pages[self.index].image,update); scroll=QScrollArea(); scroll.setWidget(im); scroll.setAlignment(A.AlignCenter); l.addWidget(scroll,1); row=QHBoxLayout(); row.addWidget(compact_btn('Deshacer',im.undo)); row.addWidget(compact_btn('Ampliar',lambda:im.set_zoom(2 if im.zoom==1 else 1))); row.addWidget(compact_btn('Cancelar',d.reject)); row.addWidget(apply); l.addLayout(row)
        if d.exec()!=QDialog.DialogCode.Accepted: return
        try: b=manual_block(im.corners(),rows,self.o,start); self.pages[self.index].blocks.append(b); self.checked.setChecked(False); self.refresh()
        except ValueError as e: QMessageBox.warning(self,'Bloque incorrecto',str(e))
    def save(self):
        if not self.checked.isChecked(): QMessageBox.warning(self,'Revisar modelo','Confirma la numeración y las casillas antes de guardar.'); return
        try: self.saved_id=self.library.save(self.name,self.items,self.pages,self.q,self.r,self.o)
        except Exception as e: QMessageBox.warning(self,'No se pudo guardar',str(e)); return
        self.accept()

def consult(parent,mid,name,meta,lib):
    pages=[]
    for (_,data),p in zip(lib.files(mid,'reference'),meta['pages']):
        im=np.array(Image.open(BytesIO(data)).convert('RGB')); h,w=im.shape[:2]; blocks=[]
        for b in p['blocks']:
            blocks.append(Block([[(x*w,y*h,cw*w,ch*h) for x,y,cw,ch in row['cells']] for row in b['rows']],b['start']))
        pages.append(Page(im,blocks,p['source']))
    if pages: ReviewDialog(parent,name,pages,meta['questions'],meta['reserves'],meta['options'],[],lib,True).exec()

def export_original(parent,mid,lib):
    files=lib.files(mid,'original')
    if len(files)==1:
        name,data=files[0]; path,_=QFileDialog.getSaveFileName(parent,'Guardar original',name)
        if path:
            try: Path(path).write_bytes(data)
            except OSError as e: QMessageBox.warning(parent,'No se pudo exportar',str(e))
    elif files:
        import zipfile
        path,_=QFileDialog.getSaveFileName(parent,'Guardar originales','Modelo externo.zip','ZIP (*.zip)')
        if path:
            try:
                with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                    for i,(name,data) in enumerate(files,1): z.writestr(f'{i:02d}-{Path(name).name}',data)
            except OSError as e: QMessageBox.warning(parent,'No se pudo exportar',str(e))
