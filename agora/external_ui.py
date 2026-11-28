"""Review and store a blank model. The live exam remains untouched."""
from pathlib import Path
from io import BytesIO
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt,QThread,Signal,QEventLoop
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QLineEdit,QMessageBox,QInputDialog,QFileDialog,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox,QProgressDialog,QScrollArea,QSizePolicy,QComboBox,QWidget)
from .controls import SafeSpinBox,SafeComboBox
from .omr_ui import pix,compact_btn
from .import_ui import ImportDialog
from . import omr
from .external_models import ExternalLibrary,learn_items,preview,metadata,suggest_numbering,detected_options,detected_counts,page_kind,reorder_pages,next_label,Page,Block
from .manual import confirm
A=Qt.AlignmentFlag

class LearnWorker(QThread):
    def __init__(self,items,options,parent):
        super().__init__(parent); self.items=items; self.options=options; self.pages=None; self.error=None
    def run(self):
        try: self.pages=learn_items(self.items,self.options)
        except Exception as e: self.error=str(e)

def host_window(parent):
    # Walk the parent hierarchy; only the main window owns the mobile session.
    w=parent
    while w is not None:
        if hasattr(w,'storage') and hasattr(w,'mobile_connection'): return w
        w=w.parentWidget()
    raise RuntimeError('No se encuentra el almacenamiento de Ágora.')

def get_library(parent): return ExternalLibrary(host_window(parent).storage.directory)

def import_model(parent):
    d=ImportDialog(host_window(parent),omr.EXTENSIONS,multiple=True,max_files=20); d.destination_label='Mi temario · Importar modelo en blanco'
    if d.exec()==QDialog.DialogCode.Accepted: return receive_items(parent,d.items)
    return None

def receive_items(parent,items):
    d=QDialog(parent); d.setWindowTitle('Aprender modelo en blanco'); d.setMinimumWidth(460); l=QVBoxLayout(d); form=QGridLayout(); l.addLayout(form)
    name=QLineEdit(Path(items[0][0]).stem[:100]); name.setMaxLength(100); form.addWidget(QLabel('Nombre del modelo'),0,0); form.addWidget(name,0,1); form.setColumnStretch(1,1)
    fields=[]
    for i,(title,lo,hi,value) in enumerate([('Preguntas ordinarias',1,500,120),('Preguntas de reserva',0,100,0),('Casillas impresas por fila',2,5,3)],1):
        w=SafeSpinBox(); w.setRange(lo,hi); w.setValue(value); fields.append(w); form.addWidget(QLabel(title),i,0); form.addWidget(w,i,1)
    hint=QLabel('Las cantidades son orientativas. Se comprobarán al leer las páginas.'); hint.setWordWrap(True); l.addWidget(hint)
    row=QHBoxLayout(); row.addWidget(compact_btn('Cancelar',d.reject)); row.addWidget(compact_btn('Detectar casillas',d.accept,True)); l.addLayout(row)
    if d.exec()!=QDialog.DialogCode.Accepted: return None
    q,r,o=[w.value() for w in fields]; title=name.text().strip()
    if not title: QMessageBox.warning(parent,'Nombre del modelo','Introduce un nombre.'); return None
    progress=QProgressDialog('Reconociendo la estructura de las hojas…','',0,0,parent); progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setMinimumDuration(0); progress.show()
    worker=LearnWorker(items,o,parent); loop=QEventLoop(); worker.finished.connect(loop.quit); worker.start();
    if not worker.isFinished(): loop.exec()
    worker.wait(); progress.close(); pages,error=worker.pages,worker.error; worker.items=[]; worker.pages=None; worker.deleteLater()
    if error: QMessageBox.warning(parent,'No se pudo importar',error); return None
    try:
        detected_q,detected_r=suggest_numbering(pages,q,r); actual_o=detected_options(pages,o)
        review=ReviewDialog(parent,title,pages,detected_q,detected_r,actual_o,items,get_library(parent),expected=(q,r,o))
    except Exception as e: QMessageBox.warning(parent,'No se pudo importar',str(e)); return None
    if review.exec()==QDialog.DialogCode.Accepted: return review.saved_id
    return None

class OrderDialog(QDialog):
    def __init__(self,parent,pages):
        super().__init__(parent); self.setWindowTitle('Ordenar páginas'); self.resize(690,420); self.pages=pages
        self.order=list(range(len(pages))); self.kinds=[page_kind(p) for p in pages]
        root=QVBoxLayout(self); self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(['Página','Documento','Tipo']); self.table.verticalHeader().hide(); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header=self.table.horizontalHeader(); header.setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch); header.setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents); root.addWidget(self.table,1)
        row=QHBoxLayout(); row.addWidget(compact_btn('↑ Subir',lambda:self.move(-1))); row.addWidget(compact_btn('↓ Bajar',lambda:self.move(1))); row.addStretch(); root.addLayout(row)
        actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(compact_btn('Cancelar',self.reject)); actions.addWidget(compact_btn('Aplicar orden',self.accept,True)); root.addLayout(actions); self.refresh()
    def refresh(self):
        self.table.setRowCount(len(self.order))
        for i,(idx,kind) in enumerate(zip(self.order,self.kinds)):
            for j,t in enumerate((str(i+1),self.pages[idx].source)):
                item=QTableWidgetItem(t); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable); self.table.setItem(i,j,item)
            combo=SafeComboBox(); combo.addItem('Ordinarias','ordinary'); combo.addItem('Reservas','reserve')
            if page_kind(self.pages[idx])=='mixed': combo.addItem('Mixta','mixed')
            combo.setCurrentIndex(combo.findData(kind)); combo.currentIndexChanged.connect(lambda _,i=i,c=combo:self.set_kind(i,c.currentData())); self.table.setCellWidget(i,2,combo)
    def set_kind(self,i,kind): self.kinds[i]=kind
    def move(self,delta):
        i=self.table.currentRow(); j=i+delta
        if i<0 or not 0<=j<len(self.order): return
        self.order[i],self.order[j]=self.order[j],self.order[i]; self.kinds[i],self.kinds[j]=self.kinds[j],self.kinds[i]; self.refresh(); self.table.selectRow(j)


class ReviewDialog(QDialog):
    def __init__(self,parent,name,pages,q,r,o,items,library,read_only=False,expected=None,edit_id=None):
        super().__init__(parent); self.name=name; self.pages=pages; self.q=q; self.r=r; self.o=o; self.items=items; self.library=library; self.read_only=read_only; self.index=0; self.saved_id=None; self.expected=expected; self.row_map=[]; self.edit_id=edit_id
        self.setWindowTitle('Consultar modelo en blanco' if read_only else 'Editar modelo en blanco' if edit_id else 'Revisar modelo en blanco'); self.resize(1120,min(760,self.screen().availableGeometry().height()-60)); root=QVBoxLayout(self)
        heading=QLabel(name); heading.setObjectName('heading'); heading.setWordWrap(True); root.addWidget(heading)
        self.summary=QLabel(); self.summary.setWordWrap(True); root.addWidget(self.summary); body=QHBoxLayout(); root.addLayout(body,1)
        self.paper=QLabel(); self.paper.setAlignment(A.AlignCenter); self.paper.setMinimumSize(160,200); self.paper.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored); self.paper.setStyleSheet('background:#EDE5E9;border-radius:8px;'); body.addWidget(self.paper,3)
        side=QVBoxLayout(); body.addLayout(side,3); self.source=QLabel(); self.source.setWordWrap(True); side.addWidget(self.source)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['Página','Columna','Filas','Primera','Última']); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.verticalHeader().hide(); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection); side.addWidget(self.table,1)
        self.table.currentCellChanged.connect(self.select_page)
        if not read_only:
            self.table.cellChanged.connect(self.update_start)
            line=QHBoxLayout(); line.addStretch(); line.addWidget(compact_btn('Ordenar páginas',self.order_pages)); side.addLayout(line)
            if edit_id:
                line=QHBoxLayout(); line.addWidget(compact_btn('Añadir páginas',self.add_pages)); line.addWidget(compact_btn('Eliminar página',self.remove_page)); side.addLayout(line)
            self.checked=QCheckBox('He comprobado las casillas y la numeración de todas las páginas'); self.checked.setStyleSheet('QCheckBox {spacing:8px;}'); root.addWidget(self.checked)
        nav=QHBoxLayout(); self.prev=compact_btn('‹ Anterior',lambda:self.go(-1)); self.next=compact_btn('Siguiente ›',lambda:self.go(1)); self.counter=QLabel(); nav.addWidget(self.prev); nav.addStretch(); nav.addWidget(self.counter); nav.addStretch(); nav.addWidget(self.next); root.addLayout(nav)
        action=QHBoxLayout(); action.addWidget(compact_btn('Cerrar' if read_only else 'Cancelar',self.reject)); action.addStretch()
        if not read_only: action.addWidget(compact_btn('Guardar modelo',self.save,True))
        root.addLayout(action); self.refresh()
    def refresh(self):
        self.table.blockSignals(True); self.row_map=[]
        for pi,p in enumerate(self.pages):
            for ci,b in enumerate(p.blocks): self.row_map.append((pi,ci,b))
        self.table.setRowCount(len(self.row_map))
        for i,(pi,ci,b) in enumerate(self.row_map):
            for j,value in enumerate((str(pi+1),str(ci+1),str(len(b.rows)),b.start,self.last_number(b))):
                it=QTableWidgetItem(value); it.setTextAlignment(A.AlignCenter)
                if j!=3 or self.read_only: it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i,j,it)
        self.table.blockSignals(False); self.show_page(); self.update_summary()
    def show_page(self):
        p=self.pages[self.index]; kind={'ordinary':'Ordinarias','reserve':'Reservas','mixed':'Mixta'}[page_kind(p)]
        self.source.setText(p.source+' · '+kind); self.counter.setText(f'{self.index+1} / {len(self.pages)}'); self.prev.setEnabled(self.index>0); self.next.setEnabled(self.index+1<len(self.pages)); self.fit()
    def last_number(self,b):
        try: return next_label(b.start,len(b.rows)-1)
        except ValueError: return '—'
    def update_summary(self):
        if not self.read_only: self.q,self.r=detected_counts(self.pages)
        msg=f'{self.q} ordinarias · {self.r} reservas · {self.o} opciones · {len(self.pages)} páginas'
        if self.expected and self.expected!=(self.q,self.r,self.o): msg+=f'\nConfiguración inicial: {self.expected[0]} ordinarias, {self.expected[1]} reservas y {self.expected[2]} opciones. Se muestran las detectadas.'
        if not self.read_only and any(not p.blocks for p in self.pages): msg+='\nHay páginas sin casillas reconocidas.'
        elif not self.read_only and any(not p.labels for p in self.pages): msg+='\nNumeración propuesta en alguna página: comprueba la tabla.'
        self.summary.setText(msg)
    def fit(self):
        self.paper.setPixmap(pix(preview(self.pages[self.index])).scaled(self.paper.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'paper'): self.fit()
    def go(self,delta):
        if 0<=self.index+delta<len(self.pages): self.index+=delta; self.show_page()
    def select_page(self,row,*_):
        if 0<=row<len(self.row_map):
            self.index=self.row_map[row][0]; self.show_page()
    def update_start(self,i,j):
        if j==3:
            import re
            b=self.row_map[i][2]; value=self.table.item(i,j).text().strip().upper().replace('-','')
            if not re.fullmatch(r'R?[1-9][0-9]{0,2}',value): value=b.start
            b.start=value; self.checked.setChecked(False); self.table.blockSignals(True); self.table.item(i,3).setText(value); self.table.item(i,4).setText(self.last_number(b)); self.table.blockSignals(False); self.update_summary(); self.show_page()
    def order_pages(self):
        d=OrderDialog(self,self.pages)
        if d.exec()==QDialog.DialogCode.Accepted and (d.order!=list(range(len(self.pages))) or d.kinds!=[page_kind(p) for p in self.pages]):
            self.pages=reorder_pages(self.pages,d.order,d.kinds); self.index=0; self.checked.setChecked(False); self.refresh()
    def remove_page(self):
        if len(self.pages)<=1: QMessageBox.warning(self,'Eliminar página','El modelo debe conservar al menos una página.'); return
        if not confirm(self,'Eliminar página',f'¿Quitar la página {self.index+1} del modelo? Los cambios se guardarán al confirmar.'): return
        self.pages.pop(self.index); self.pages=reorder_pages(self.pages,list(range(len(self.pages))),[page_kind(p) for p in self.pages]); self.index=min(self.index,len(self.pages)-1); self.checked.setChecked(False); self.refresh()
    def add_pages(self):
        d=ImportDialog(host_window(self),omr.EXTENSIONS,multiple=True,max_files=20); d.destination_label='Mi temario · Editar modelo en blanco'
        if d.exec()!=QDialog.DialogCode.Accepted or not d.items: return
        # Reimporting an original is allowed to recover previously removed pages.
        used={name for name,_ in self.items}; by_data={data:name for name,data in self.items}; incoming=[]; added_sources=[]
        for name,data in d.items:
            if data in by_data:
                base=by_data[data]
                if not any(n==base for n,_ in incoming): incoming.append((base,data))
                continue
            stem=Path(name).stem; suffix=Path(name).suffix; base=name; i=2
            while base in used: base=f'{stem} ({i}){suffix}'; i+=1
            used.add(base); by_data[data]=base; incoming.append((base,data)); added_sources.append((base,data))
        if not incoming: return
        progress=QProgressDialog('Reconociendo nuevas páginas…','',0,0,self); progress.setCancelButton(None); progress.setWindowModality(Qt.WindowModality.WindowModal); progress.setMinimumDuration(0); progress.show()
        worker=LearnWorker(incoming,self.o,self); loop=QEventLoop(); worker.finished.connect(loop.quit); worker.start()
        if not worker.isFinished(): loop.exec()
        worker.wait(); progress.close(); new,error=worker.pages,worker.error; worker.deleteLater()
        try:
            if error: raise ValueError(error)
            existing={p.source for p in self.pages}; new=[p for p in new if p.source not in existing]
            if not new: raise ValueError('Todas las páginas seleccionadas ya forman parte del modelo.')
            if len(self.pages)+len(new)>200: raise ValueError('Máximo 200 páginas por modelo.')
            if any(not p.blocks for p in new): raise ValueError('Alguna página no tiene casillas reconocidas.')
            if detected_options(new,self.o)!=self.o: raise ValueError('Las nuevas páginas tienen un número de opciones diferente.')
            suggest_numbering(new,500,0)
            self.items.extend(added_sources); self.pages.extend(new); self.pages=reorder_pages(self.pages,list(range(len(self.pages))),[page_kind(p) for p in self.pages]); self.index=len(self.pages)-len(new); self.checked.setChecked(False); self.refresh()
        except Exception as e: QMessageBox.warning(self,'No se pudieron añadir páginas',str(e))
    def save(self):
        if not self.checked.isChecked(): QMessageBox.warning(self,'Revisar modelo','Confirma la numeración y las casillas antes de guardar.'); return
        try:
            if self.edit_id: self.saved_id=self.library.update(self.edit_id,self.name,self.items,self.pages,self.q,self.r,self.o)
            else: self.saved_id=self.library.save(self.name,self.items,self.pages,self.q,self.r,self.o)
        except Exception as e: QMessageBox.warning(self,'No se pudo guardar',str(e)); return
        self.accept()

def restore_pages(mid,meta,lib):
    pages=[]
    for (_,data),p in zip(lib.files(mid,'reference'),meta['pages']):
        im=np.array(Image.open(BytesIO(data)).convert('RGB')); h,w=im.shape[:2]; blocks=[]
        for b in p['blocks']:
            runs=[]
            for row in b['rows']:
                number=row['number']
                if not runs or number!=next_label(runs[-1].start,len(runs[-1].rows)): runs.append(Block([],number))
                runs[-1].rows.append([(x*w,y*h,cw*w,ch*h) for x,y,cw,ch in row['cells']])
            blocks.extend(runs)
        pages.append(Page(im,blocks,p['source']))
    if len(pages)!=len(meta['pages']): raise ValueError('Faltan imágenes de referencia del modelo.')
    return pages

def consult(parent,mid,name,meta,lib):
    try:
        pages=restore_pages(mid,meta,lib)
        if pages: ReviewDialog(parent,name,pages,meta['questions'],meta['reserves'],meta['options'],[],lib,True).exec()
    except Exception as e: QMessageBox.warning(parent,'No se pudo consultar',str(e))

def edit_model(parent,mid,name,meta,lib):
    try:
        pages=restore_pages(mid,meta,lib)
        if pages: ReviewDialog(parent,name,pages,meta['questions'],meta['reserves'],meta['options'],lib.files(mid,'original'),lib,edit_id=mid).exec()
    except Exception as e: QMessageBox.warning(parent,'No se pudo editar',str(e))

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
