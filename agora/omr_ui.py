"""Optical reader validation workspace; scoring integration belongs to block 06."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPixmap,QPainter,QPen,QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QDialog,QMessageBox,QScrollArea)
from .controls import SafeComboBox
from .import_ui import ImportDialog
from .manual import confirm
from . import omr
from .optical_archive import record
A=Qt.AlignmentFlag

def pix(im):
    h,w=im.shape[:2]; return QPixmap.fromImage(QImage(im.tobytes(),w,h,w*3,QImage.Format.Format_RGB888).copy())
def text(s,role='muted'):
    l=QLabel(s); l.setObjectName(role); l.setWordWrap(True); l.setTextFormat(Qt.TextFormat.PlainText); return l

def btn(s,fn,primary=False):
    b=QPushButton(s); b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary: b.setObjectName('primary')
    b.clicked.connect(fn); return b

class CornerImage(QLabel):
    def __init__(self,im,changed):
        super().__init__(); self.im=im; self.points=[]; self.changed=changed; self.source=pix(im); self.zoom=1; self.set_zoom(1)
    def set_zoom(self,zoom):
        self.zoom=zoom; self.base=self.source.scaled(620*zoom,670*zoom,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation); self.setFixedSize(self.base.size()); self.draw()
    def draw(self):
        p=self.base.copy(); painter=QPainter(p); painter.setPen(QPen(QColor('#A55379'),2)); h,w=self.im.shape[:2]
        for i,(x,y) in enumerate(self.points):
            x=round(x*self.base.width()/w); y=round(y*self.base.height()/h)
            painter.drawEllipse(x-7,y-7,14,14); painter.drawLine(x-10,y,x+10,y); painter.drawLine(x,y-10,x,y+10); painter.drawText(x+10,y-9,str(i+1))
        painter.end(); self.setPixmap(p); self.changed(len(self.points))
    def mousePressEvent(self,e):
        if e.button()!=Qt.MouseButton.LeftButton: return
        if len(self.points)==4: return
        p=e.position(); h,w=self.im.shape[:2]; self.points.append((p.x()*w/self.base.width(),p.y()*h/self.base.height())); self.draw()
    def undo(self):
        if self.points: self.points.pop(); self.draw()
    def reset(self): self.points.clear(); self.draw()
    def corners(self): return list(self.points)

class OpticalPage(QWidget):
    def __init__(self,config,answers,cache,changed):
        super().__init__(); self.config=config; self.answers=answers; self.changed=changed
        self.images=cache.setdefault('images',{}); self.aligned=cache.setdefault('aligned',{}); self.marks=cache.setdefault('marks',{}); self.records=cache.setdefault('records',{})
        l=QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(7)
        l.addWidget(btn('Importar hojas de respuestas (PDF o fotos)',self.load,True))
        row=QHBoxLayout(); self.page=SafeComboBox(); self.page.addItems(['Preguntas ordinarias','Reservas']); self.page.currentIndexChanged.connect(self.refresh); row.addWidget(self.page); self.filter=SafeComboBox(); self.filter.addItems(['Solo pendientes','Todas las preguntas']); self.filter.currentIndexChanged.connect(self.refresh); row.addWidget(self.filter); row.addWidget(btn('Ver hoja y casillas',self.preview)); row.addWidget(btn('Ajustar alineación',self.adjust)); l.addLayout(row)
        self.count=text(''); self.count.setToolTip('Las lecturas claras se rellenan automáticamente; revisa las dudosas. La tinta roja solo es informativa.'); l.addWidget(self.count)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['Pregunta','Recorte original','Estado de lectura','Respuesta']); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.verticalHeader().hide(); self.table.setMinimumHeight(260); l.addWidget(self.table)
        if self.images:
            self.page.setCurrentIndex(0 if 0 in self.images else 1)
            if all(self.answers): self.filter.setCurrentIndex(1)
        self.refresh()
    def indices(self,slot):
        return range(0,self.config.questions) if slot==0 else range(self.config.questions,self.config.size)
    def compatible(self):
        if self.config.questions>120 or self.config.reserves>9 or self.config.options!=3: raise ValueError('Este lector solo es compatible con la plantilla A/B/C de hasta 120 preguntas y 9 reservas. Para otro modelo utiliza el corrector manual.')
    def load(self):
        try: self.compatible()
        except ValueError as e: QMessageBox.warning(self,'Plantilla no compatible',str(e)); return
        d=ImportDialog(self,omr.EXTENSIONS,multiple=True)
        if d.exec()!=QDialog.DialogCode.Accepted or not d.items: return
        try:
            pending={}; count=0
            for name,data in d.items:
                for im in omr.decode(name,data):
                    count+=1
                    if count>2: raise ValueError('Selecciona un máximo de dos páginas en total.')
                    try:
                        aligned=omr.align(im); slot=omr.identify(aligned); marks=omr.scan(aligned,slot)
                    except ValueError as e:
                        box=QMessageBox(self); box.setWindowTitle('Alinear hoja'); box.setText(str(e)+'\n\nPuedes indicar manualmente el tipo de hoja para ajustar sus círculos.'); box.setIcon(QMessageBox.Icon.Question)
                        ordinary=box.addButton('Ordinarias',QMessageBox.ButtonRole.ActionRole); reserve=box.addButton('Reservas',QMessageBox.ButtonRole.ActionRole); cancel=box.addButton('Cancelar',QMessageBox.ButtonRole.RejectRole); box.setEscapeButton(cancel); box.exec()
                        if box.clickedButton() not in (ordinary,reserve): return
                        slot=0 if box.clickedButton() is ordinary else 1
                        adjusted=self.alignment_dialog(im,slot)
                        if adjusted is None: return
                        aligned,marks=adjusted
                    if slot in pending: raise ValueError('Hay dos páginas del mismo tipo. Selecciona una de cada tipo.')
                    pending[slot]=(im,aligned,marks)
            if any(any(self.answers[i] for i in self.indices(slot)) for slot in pending) and not confirm(self,'Sustituir lectura','Se sustituirán las respuestas de las páginas importadas. ¿Continuar?'): return
            for slot,(im,aligned,marks) in pending.items(): self.install(slot,im,aligned,marks)
            self.page.setCurrentIndex(0 if 0 in pending else 1); self.filter.setCurrentIndex(1 if all(self.answers) else 0); self.changed(); self.refresh()
        except Exception as e: QMessageBox.warning(self,'No se pudo leer',str(e))
    def install(self,slot,im,aligned,marks):
        snapshot=record(im,aligned,marks)
        self.images[slot]=im; self.aligned[slot]=aligned; self.marks[slot]=marks; self.records[slot]=snapshot
        for i,m in zip(self.indices(slot),marks): self.answers[i]=omr.proposed(m)
    def preview(self):
        i=self.page.currentIndex()
        if i not in self.aligned: QMessageBox.information(self,'Ver hoja','No hay imagen conservada para esta página. Los simulacros antiguos pueden contener solo las respuestas.'); return
        import cv2 as cv
        d=QDialog(self); d.setWindowTitle('Hoja de respuestas'); d.resize(690,780); l=QVBoxLayout(d)
        row=QHBoxLayout(); im=QLabel(); im.setAlignment(A.AlignCenter)
        def show(original):
            img=self.images[i] if original else self.aligned[i].copy()
            if not original:
                for m in self.marks[i]:
                    x,y,x2,y2=m.crop; cv.rectangle(img,(x,y),(x2-1,y2-1),(28,167,112),2)
            im.setPixmap(pix(img).scaled(600,690,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        row.addWidget(btn('Hoja original',lambda:show(True))); row.addWidget(btn('Casillas leídas',lambda:show(False))); l.addLayout(row)
        sc=QScrollArea(); sc.setWidget(im); sc.setWidgetResizable(True); l.addWidget(sc,1); l.addWidget(btn('Cerrar',d.accept),0,A.AlignCenter); show(True); d.exec()
    def adjust(self):
        i=self.page.currentIndex()
        if i not in self.images: QMessageBox.information(self,'Ajustar alineación','No hay imagen conservada para esta página.'); return
        try:
            adjusted=self.alignment_dialog(self.images[i],i)
            if adjusted is None: return
            aligned,marks=adjusted
            if not confirm(self,'Aplicar alineación','Se volverán a interpretar las respuestas de esta página. ¿Continuar?'): return
            self.install(i,self.images[i],aligned,marks); self.changed(); self.refresh()
        except Exception as e: QMessageBox.warning(self,'No se pudo alinear',str(e)+'\n\nSe conserva la lectura anterior. Usa los centros de los círculos indicados o la alineación automática.')
    def alignment_dialog(self,original,i):
        d=QDialog(self); d.setWindowTitle('Ajustar alineación'); d.resize(720,800); l=QVBoxLayout(d)
        refs=['1 · A','91 · C','120 · C','30 · A'] if i==0 else ['R1 · A','R7 · C','R9 · C','R3 · A']
        guide=text('Marca el CENTRO de los círculos indicados, no los bordes del papel.'); l.addWidget(guide)
        status=text('','tileTitle'); l.addWidget(status); apply=btn('Aplicar',lambda:None,True)
        def update(n):
            status.setText(f'{n}/4 · Ahora: {refs[n]}' if n<4 else '4/4 · Referencias seleccionadas'); apply.setEnabled(n==4)
        im=CornerImage(original,update); sc=QScrollArea(); sc.setWidget(im); sc.setAlignment(A.AlignCenter); l.addWidget(sc,1)
        tools=QHBoxLayout(); tools.addWidget(btn('Deshacer punto',im.undo)); tools.addWidget(btn('Reiniciar puntos',im.reset)); zoom=SafeComboBox(); zoom.addItems(['Ajustar a ventana','Ampliar ×2','Ampliar ×3']); zoom.currentIndexChanged.connect(lambda j:im.set_zoom(j+1)); tools.addWidget(zoom); l.addLayout(tools)
        row=QHBoxLayout(); row.addWidget(btn('Cancelar',d.reject)); row.addWidget(btn('Alineación automática',lambda:d.done(2))); apply.clicked.connect(d.accept); row.addWidget(apply); l.addLayout(row)
        outcome=d.exec()
        if outcome not in (QDialog.DialogCode.Accepted,2): return None
        aligned=omr.align(original) if outcome==2 else omr.align_grid(original,i,im.corners())
        if omr.identify(aligned)!=i: raise ValueError('El tipo de hoja no coincide con el seleccionado.')
        return aligned,omr.scan(aligned,i)
    def refresh(self,*_):
        slot=self.page.currentIndex(); marks=self.marks.get(slot,[]); indices=list(self.indices(slot)); shown=[(j,i) for j,i in enumerate(indices) if self.filter.currentIndex()==1 or not self.answers[i]]
        self.table.setRowCount(0); self.table.setRowCount(len(shown))
        for row,(j,i) in enumerate(shown):
            self.table.setRowHeight(row,48); m=marks[j] if j<len(marks) else None
            status=m.status if m else ('Respuesta conservada · sin recorte' if self.answers[i] else 'Hoja no cargada')
            if m and omr.proposed(m)=='-': status='Sin azul · blanco propuesto'
            elif m and m.suggestion and not omr.proposed(m): status+=f' · posible {m.suggestion}'
            for col,s in [(0,self.config.number(i)),(2,status)]:
                t=QTableWidgetItem(s); t.setTextAlignment(A.AlignCenter); self.table.setItem(row,col,t)
            if m:
                x,y,x2,y2=m.crop; crop=QLabel(); crop.setAlignment(A.AlignCenter); crop.setPixmap(pix(self.aligned[slot][y:y2,x:x2]).scaled(155,43,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); self.table.setCellWidget(row,1,crop)
            combo=SafeComboBox(); vals=['',*self.config.letters,'-']; combo.addItems(['Pendiente',*self.config.letters,'En blanco']); combo.setCurrentIndex(vals.index(self.answers[i])); combo.currentIndexChanged.connect(lambda k,n=i,v=vals:self.set_choice(n,v[k])); self.table.setCellWidget(row,3,combo)
        self.update_count()
    def set_choice(self,i,value):
        self.answers[i]=value; self.changed(); self.update_count()
    def update_count(self):
        n=self.answers.count(''); suffix=' · Sin imagen guardada' if self.page.currentIndex() not in self.images and any(self.answers[i] for i in self.indices(self.page.currentIndex())) else ''; self.count.setText(f'{len(self.answers)-n}/{len(self.answers)} respuestas · {n} pendientes'+suffix)
    def reset(self):
        if any(self.answers) and not confirm(self,'Reiniciar lectura','Se descartarán las respuestas y revisiones actuales. ¿Continuar?'): return
        self.images.clear(); self.aligned.clear(); self.marks.clear(); self.records.clear(); self.answers[:]=['']*len(self.answers); self.changed(); self.refresh()
