"""Model library and live printable PDF editor."""
from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QPixmap,QImage,QColor,QPainter
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QLineEdit,QCheckBox,QScrollArea,QFileDialog,QMessageBox,QColorDialog,QInputDialog,QSizePolicy)
from .controls import SafeComboBox,SafeSpinBox
from .models import Model,ModelLibrary,PRESETS,pdf_bytes,layout,color_name
from .ui import button,label,frame,vertical,ASSETS
from .manual import confirm


def render_page(data,index,scale=1.5):
    import pypdfium2 as pdfium
    doc=pdfium.PdfDocument(data)
    try:
        page=doc[index]
        try:
            bitmap=page.render(scale=scale)
            try:
                im=bitmap.to_pil().convert('RGB'); raw=im.tobytes(); return QImage(raw,im.width,im.height,im.width*3,QImage.Format.Format_RGB888).copy()
            finally: bitmap.close()
        finally: page.close()
    finally: doc.close()

class ModelEditor(QDialog):
    def __init__(self,parent,model,save_callback=None,read_only=False):
        super().__init__(parent); self.setWindowTitle('Consultar modelo' if read_only else 'Personalizar modelo'); self.setMinimumSize(760,520); self.resize(1130,760); self.source=model; self.read_only=read_only; self.save_callback=save_callback; self.data=None; self.index=0; self.color=model.color
        root=QVBoxLayout(self); root.addWidget(label('Consultar modelo' if read_only else 'Crear modelo personalizado','heading')); body=QHBoxLayout(); root.addLayout(body,1)
        controls=QWidget(); form=QGridLayout(controls); form.setContentsMargins(8,8,8,8); form.setColumnStretch(1,1); self.fields={}; self.row=0
        def add(title,w,key):
            form.addWidget(label(title,wrap=True),self.row,0); form.addWidget(w,self.row,1); self.row+=1; self.fields[key]=w
        for key,title in [('name','Nombre'),('title','Título de la hoja')]:
            w=QLineEdit(getattr(model,key)); w.setMaxLength(100); w.setReadOnly(read_only); add(title,w,key); w.textChanged.connect(self.schedule)
        for key,title,lo,hi in [('questions','Preguntas ordinarias',1,500),('reserves','Preguntas de reserva',0,100),('options','Opciones por pregunta',2,5),('columns','Columnas máximas',1,4),('size','Casilla (mm)',4,8),('margin','Margen (mm)',10,22)]:
            if read_only:
                w=QLineEdit(str(getattr(model,key))); w.setReadOnly(True); add(title,w,key)
            else:
                w=SafeSpinBox(); w.setRange(lo,hi); w.setValue(getattr(model,key)); add(title,w,key); w.valueChanged.connect(self.schedule)
        for key,title,choices in [('shape','Forma',[('Círculos','circle'),('Cuadrados','square'),('Óvalos','oval')]),('orientation','Orientación A4',[('Vertical','portrait'),('Horizontal','landscape')])]:
            if read_only:
                w=QLineEdit(next(n for n,v in choices if v==getattr(model,key))); w.setReadOnly(True); add(title,w,key)
            else:
                w=SafeComboBox(); [w.addItem(n,v) for n,v in choices]; w.setCurrentIndex(w.findData(getattr(model,key))); add(title,w,key); w.currentIndexChanged.connect(self.schedule)
        self.color_button=QLineEdit() if read_only else button('',role='softAction');
        if read_only: self.color_button.setReadOnly(True); self.color_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else: self.color_button.clicked.connect(self.pick_color)
        self.update_color(); form.addWidget(label('Color de impresión'),self.row,0); form.addWidget(self.color_button,self.row,1); self.row+=1
        for key,title in [('header','Datos del examen'),('logo','Logotipo de Ágora'),('stripe','Filas alternas'),('notes','Espacio para notas'),('separate','Reservas en página independiente')]:
            w=QCheckBox(title); w.setChecked(getattr(model,key)); w.setEnabled(not read_only);
            if read_only: w.setStyleSheet('QCheckBox:disabled {color:#867881;} QCheckBox::indicator:disabled {background:#E8E0E5;border:1px solid #BBAAB4;border-radius:2px;} QCheckBox::indicator:checked:disabled {background:#B7A2AF;image:url("'+str(ASSETS / 'check.svg').replace('\\','/')+'");}')
            form.addWidget(w,self.row,0,1,2); self.row+=1; self.fields[key]=w; w.toggled.connect(self.schedule)
        form.setRowStretch(self.row,1); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(controls); scroll.setMinimumWidth(335); scroll.setMaximumWidth(435); body.addWidget(scroll,0)
        preview=QWidget(); pl=vertical(preview,spacing=8); self.summary=label('',wrap=True); pl.addWidget(self.summary)
        self.paper=QLabel(); self.paper.setAlignment(Qt.AlignmentFlag.AlignCenter); self.paper.setMinimumSize(180,220); self.paper.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Ignored); self.paper.setStyleSheet('background:#EDE5E9;border-radius:8px;'); pl.addWidget(self.paper,1)
        nav=QHBoxLayout(); self.prev=button('‹ Anterior'); self.next=button('Siguiente ›'); self.counter=label(''); nav.addWidget(self.prev); nav.addStretch(); nav.addWidget(self.counter); nav.addStretch(); nav.addWidget(self.next); pl.addLayout(nav); self.prev.clicked.connect(lambda:self.change_page(-1)); self.next.clicked.connect(lambda:self.change_page(1)); body.addWidget(preview,1)
        actions=QHBoxLayout(); close=button('Cerrar' if read_only else 'Cancelar'); close.clicked.connect(self.reject); actions.addWidget(close); actions.addStretch(); self.export_button=button('Exportar PDF',role='softAction'); self.export_button.clicked.connect(self.export); actions.addWidget(self.export_button); self.print_button=button('Imprimir',role='softAction'); self.print_button.clicked.connect(self.print_pdf); actions.addWidget(self.print_button)
        if save_callback is not None:
            self.save_button=button('Guardar modelo',role='primary'); self.save_button.clicked.connect(self.save); actions.addWidget(self.save_button)
        root.addLayout(actions); self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.refresh); self.refresh()
    def model(self):
        if self.read_only: return self.source
        values={}
        for key,w in self.fields.items():
            if isinstance(w,QLineEdit): values[key]=w.text().strip()
            elif isinstance(w,QCheckBox): values[key]=w.isChecked()
            elif isinstance(w,SafeSpinBox): values[key]=w.value()
            else: values[key]=w.currentData()
        return Model(**values,color=self.color)
    def update_color(self):
        c=QColor(self.color); rgb=[v/255 for v in (c.red(),c.green(),c.blue())]; linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        luminance=sum(a*b for a,b in zip(linear,(.2126,.7152,.0722))); fg='#222222' if luminance>.179 else '#FFFFFF'
        self.color_button.setText(color_name(self.color)); self.color_button.setStyleSheet(f'background:{self.color}; color:{fg}; border:1px solid #C6B1BD; border-radius:8px; padding:9px 5px; text-align:center;')
    def pick_color(self):
        c=QColorDialog.getColor(QColor(self.color),self,'Color de impresión')
        if c.isValid(): self.color=c.name().upper(); self.update_color(); self.schedule()
    def schedule(self,*_):
        if hasattr(self,'timer'): self.timer.start(180)
    def refresh(self):
        try:
            self.current=self.model(); self.pages=layout(self.current); self.data=pdf_bytes(self.current); self.index=min(self.index,len(self.pages)-1); self.show_page(); self.summary.setText(f'{self.current.questions} preguntas · {self.current.reserves} reservas · {self.current.letters[0]}–{self.current.letters[-1]} · {self.pages[0]["columns"]} columnas · {len(self.pages)} página(s)')
            for b in (self.export_button,self.print_button,getattr(self,'save_button',None)):
                if b: b.setEnabled(True)
        except Exception as e:
            self.data=None; self.paper.clear(); self.summary.setText(str(e)); self.counter.clear(); self.prev.setEnabled(False); self.next.setEnabled(False)
            for b in (self.export_button,self.print_button,getattr(self,'save_button',None)):
                if b: b.setEnabled(False)
    def show_page(self):
        self.image=render_page(self.data,self.index); self.fit(); self.counter.setText(f'{self.index+1} / {len(self.pages)}'); self.prev.setEnabled(self.index>0); self.next.setEnabled(self.index+1<len(self.pages))
    def fit(self):
        if self.data and hasattr(self,'image'): self.paper.setPixmap(QPixmap.fromImage(self.image).scaled(self.paper.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'paper'): self.fit()
    def change_page(self,delta):
        if self.data and 0<=self.index+delta<len(self.pages): self.index+=delta; self.show_page()
    def export(self):
        self.refresh()
        if not self.data: return
        name=''.join(c if c not in '<>:"/\\|?*' else '_' for c in self.current.name)+'.pdf'; path,_=QFileDialog.getSaveFileName(self,'Exportar modelo PDF',name,'PDF (*.pdf)')
        if path:
            try: Path(path if path.lower().endswith('.pdf') else path+'.pdf').write_bytes(self.data)
            except OSError as e: QMessageBox.warning(self,'No se pudo exportar',str(e))
    def save(self):
        self.refresh()
        if self.data:
            try: self.save_callback(self.current); self.accept()
            except Exception as e: QMessageBox.warning(self,'No se pudo guardar',str(e))
    def print_pdf(self):
        self.refresh()
        if not self.data: return
        from PySide6.QtPrintSupport import QPrinter,QPrintDialog
        from PySide6.QtGui import QPageSize,QPageLayout
        printer=QPrinter(QPrinter.PrinterMode.HighResolution); printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4)); printer.setPageOrientation(QPageLayout.Orientation.Portrait if self.current.orientation=='portrait' else QPageLayout.Orientation.Landscape); printer.setFullPage(True)
        dlg=QPrintDialog(printer,self); dlg.setMinMax(1,len(self.pages)); dlg.setFromTo(1,len(self.pages))
        if dlg.exec()!=QDialog.DialogCode.Accepted: return
        painter=QPainter()
        if not painter.begin(printer): QMessageBox.warning(self,'Impresión','No se pudo iniciar la impresión.'); return
        try:
            for offset,i in enumerate(range(max(0,printer.fromPage()-1),min(len(self.pages),printer.toPage() or len(self.pages)))):
                if offset and not printer.newPage(): raise RuntimeError('No se pudo crear una página de impresión.')
                img=render_page(self.data,i,3); area=painter.viewport(); scaled=img.size(); scaled.scale(area.size(),Qt.AspectRatioMode.KeepAspectRatio); from PySide6.QtCore import QRect
                painter.drawImage(QRect(area.x()+(area.width()-scaled.width())//2,area.y()+(area.height()-scaled.height())//2,scaled.width(),scaled.height()),img)
        except Exception as e: QMessageBox.warning(self,'Impresión',str(e))
        finally: painter.end()

class ModelsPage(QWidget):
    def __init__(self,window):
        super().__init__(); self.window=window; self.library=None; self.thumbnails={}; l=vertical(self,spacing=16); back=button('Volver a Mi temario','book'); back.clicked.connect(lambda:window.library_stack.setCurrentIndex(0)); l.addWidget(back,0,Qt.AlignmentFlag.AlignLeft); l.addWidget(label('Mis modelos','heading'))
        row=QHBoxLayout(); create=button('Crear modelo',role='primary'); create.clicked.connect(lambda:self.edit(Model())); row.addWidget(create); row.addStretch(); l.addLayout(row)
        l.addWidget(label('Modelos de Ágora','tileTitle')); self.presets=QGridLayout(); l.addLayout(self.presets); l.addWidget(label('Mis modelos personalizados','tileTitle')); self.custom=QGridLayout(); l.addLayout(self.custom); l.addStretch()
        for m in PRESETS: self.add_card(self.presets,m)
    def refresh(self):
        while self.custom.count():
            item=self.custom.takeAt(0); w=item.widget()
            if w: w.hide(); w.deleteLater()
        self.thumbnails={m:p for m,p in self.thumbnails.items() if m in PRESETS}
        try:
            if self.library is None: self.library=ModelLibrary(self.window.storage.directory)
            entries=self.library.entries()
            if not entries: self.custom.addWidget(label('Todavía no hay modelos personalizados.','muted'),0,0,1,2)
            for mid,m,date in entries: self.add_card(self.custom,m,mid,date)
        except Exception as e: self.custom.addWidget(label(str(e),wrap=True),0,0,1,2)
    def add_card(self,l,m,mid=None,date=None):
        card=frame('tile'); h=QHBoxLayout(card); h.setContentsMargins(12,12,12,12); h.setSpacing(12)
        thumbnail=QLabel(); thumbnail.setFixedSize(88,118); thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter); thumbnail.setStyleSheet('background:#F7EDF2;border:1px solid #E8CEDB;border-radius:6px;')
        if m not in self.thumbnails:
            try: self.thumbnails[m]=QPixmap.fromImage(render_page(pdf_bytes(m),0,.7)).scaled(80,110,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            except Exception: pass
        if m in self.thumbnails: thumbnail.setPixmap(self.thumbnails[m])
        else: thumbnail.setText('PDF')
        h.addWidget(thumbnail,0,Qt.AlignmentFlag.AlignVCenter)
        info=QVBoxLayout(); info.setSpacing(5); info.addWidget(label(m.name,'tileTitle',True)); info.addWidget(label(f'{m.questions} preguntas · {m.reserves} reservas · A–{m.letters[-1]}'+(f' · {date.replace("T"," ")}' if date else ''),'muted',True)); h.addLayout(info,1)
        actions=QGridLayout(); actions.setHorizontalSpacing(5); actions.setVerticalSpacing(5); info.addLayout(actions); idx=0
        items=[('Consultar',lambda:self.consult(m)),('Descargar PDF',lambda:self.download(m)),('Personalizar' if mid is None else 'Editar',lambda:self.edit(m,mid))]
        if mid: items.extend([('Renombrar',lambda:self.rename(mid,m)),('Eliminar',lambda:self.remove(mid,m))])
        for text,fn in items:
            b=button(text,role='softAction'); b.setStyleSheet('text-align:center;padding:6px 8px;'); b.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed); b.clicked.connect(fn); actions.addWidget(b,idx//2,idx%2,Qt.AlignmentFlag.AlignLeft); idx+=1
        actions.setColumnStretch(2,1); info.addStretch(); n=l.count(); l.addWidget(card,n//2,n%2); l.setColumnStretch(0,1); l.setColumnStretch(1,1)
    def consult(self,m): ModelEditor(self,m,read_only=True).exec()
    def edit(self,m,mid=None):
        if self.library is None: self.library=ModelLibrary(self.window.storage.directory)
        if mid is None and m in PRESETS: m=replace(m,name=m.name+' personalizado')
        dlg=ModelEditor(self,m,lambda value:self.library.save(value,mid)); dlg.exec(); self.refresh()
    def download(self,m):
        name=''.join(c if c not in '<>:"/\\|?*' else '_' for c in m.name)+'.pdf'; path,_=QFileDialog.getSaveFileName(self,'Descargar modelo',name,'PDF (*.pdf)')
        if path:
            try: Path(path if path.lower().endswith('.pdf') else path+'.pdf').write_bytes(pdf_bytes(m))
            except Exception as e: QMessageBox.warning(self,'No se pudo exportar',str(e))
    def rename(self,mid,m):
        name,ok=QInputDialog.getText(self,'Renombrar modelo','Nombre del modelo',text=m.name)
        if ok:
            try: self.library.save(replace(m,name=name.strip()),mid); self.refresh()
            except Exception as e: QMessageBox.warning(self,'No se pudo renombrar',str(e))
    def remove(self,mid,m):
        if confirm(self,'Eliminar modelo',f'Se eliminará «{m.name}». No se puede deshacer. ¿Continuar?'): self.library.delete(mid); self.refresh()
