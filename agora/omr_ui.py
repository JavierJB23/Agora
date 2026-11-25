"""Optical reader validation workspace; scoring integration belongs to block 06."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPixmap,QPainter,QPen,QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QDialog,QMessageBox,QScrollArea)
from .controls import SafeComboBox
from .import_ui import ImportDialog
from .manual import confirm
from . import omr
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
    def __init__(self,im):
        super().__init__(); self.im=im; self.points=[]; self.base=pix(im).scaled(580,660,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation); self.setFixedSize(self.base.size()); self.draw()
    def draw(self):
        p=self.base.copy(); painter=QPainter(p); painter.setPen(QPen(QColor('#A55379'),3));
        for i,(x,y) in enumerate(self.points):
            painter.drawEllipse(int(x)-5,int(y)-5,10,10); painter.drawText(int(x)+8,int(y)+14,str(i+1))
        painter.end(); self.setPixmap(p)
    def mousePressEvent(self,e):
        if len(self.points)==4: self.points=[]
        p=e.position(); self.points.append((p.x(),p.y())); self.draw()
    def corners(self):
        h,w=self.im.shape[:2]; return [(x*w/self.base.width(),y*h/self.base.height()) for x,y in self.points]

class OpticalPage(QWidget):
    def __init__(self,config,answers,cache,changed):
        super().__init__(); self.config=config; self.answers=answers; self.changed=changed
        self.images=cache.setdefault('images',{}); self.aligned=cache.setdefault('aligned',{}); self.marks=cache.setdefault('marks',{})
        l=QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(10)
        l.addWidget(btn('Importar hojas de respuestas (PDF o fotos)',self.load,True))
        self.note=text('Importa las páginas en cualquier orden, juntas o por separado. Plantilla compatible: hasta 120 preguntas y 9 reservas, A/B/C.' + (' Se han recuperado respuestas guardadas; los recortes originales solo se mantienen mientras Ágora está abierto. Puedes volver a importar las hojas.' if any(answers) and not self.marks else '')); l.addWidget(self.note)
        row=QHBoxLayout(); self.page=SafeComboBox(); self.page.addItems(['Preguntas ordinarias','Reservas']); self.page.currentIndexChanged.connect(self.refresh); row.addWidget(self.page); self.filter=SafeComboBox(); self.filter.addItems(['Solo pendientes','Todas las preguntas']); self.filter.currentIndexChanged.connect(self.refresh); row.addWidget(self.filter); row.addWidget(btn('Ver hoja y casillas',self.preview)); row.addWidget(btn('Ajustar esquinas',self.adjust)); l.addLayout(row)
        l.addWidget(text('Las lecturas claras se rellenan automáticamente. Revisa las dudosas y confirma que has usado tinta azul. El rojo es informativo. Puedes modificar cualquier respuesta desde Todas las preguntas.'))
        self.count=text(''); l.addWidget(self.count)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['Pregunta','Recorte original','Estado de lectura','Respuesta']); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.verticalHeader().hide(); self.table.setMinimumHeight(300); l.addWidget(self.table)
        l.addWidget(btn('Reiniciar lectura',self.reset),0,A.AlignLeft)
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
                    aligned=omr.align(im); slot=omr.identify(aligned)
                    if slot in pending: raise ValueError('Hay dos páginas del mismo tipo. Selecciona una de cada tipo.')
                    pending[slot]=(im,aligned,omr.scan(aligned,slot))
            if any(any(self.answers[i] for i in self.indices(slot)) for slot in pending) and not confirm(self,'Sustituir lectura','Se sustituirán las respuestas de las páginas importadas. ¿Continuar?'): return
            for slot,(im,aligned,marks) in pending.items(): self.install(slot,im,aligned,marks)
            self.page.setCurrentIndex(0 if 0 in pending else 1); self.filter.setCurrentIndex(0); self.note.setText('Páginas reconocidas automáticamente. Comprueba la alineación y resuelve las dudas antes de corregir.'); self.changed(); self.refresh()
        except Exception as e: QMessageBox.warning(self,'No se pudo leer',str(e))
    def install(self,slot,im,aligned,marks):
        self.images[slot]=im; self.aligned[slot]=aligned; self.marks[slot]=marks
        for i,m in zip(self.indices(slot),marks): self.answers[i]=omr.proposed(m)
    def preview(self):
        i=self.page.currentIndex()
        if i not in self.aligned: QMessageBox.information(self,'Ver hoja','Importa esta página para verla.'); return
        d=QDialog(self); d.setWindowTitle('Comprobar alineación'); l=QVBoxLayout(d); l.addWidget(text('Los recuadros verdes deben coincidir con cada círculo. Si no coinciden, ajusta las esquinas.')); im=QLabel(); im.setPixmap(pix(omr.overlay(self.aligned[i],i)).scaled(580,720,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); l.addWidget(im,0,A.AlignCenter); l.addWidget(btn('Cerrar',d.accept),0,A.AlignCenter); d.exec()
    def adjust(self):
        i=self.page.currentIndex()
        if i not in self.images: QMessageBox.information(self,'Ajustar esquinas','Importa esta página primero.'); return
        if not confirm(self,'Ajustar esquinas','Se volverán a interpretar todas las respuestas de esta página. ¿Continuar?'): return
        d=QDialog(self); d.setWindowTitle('Ajustar esquinas'); l=QVBoxLayout(d); l.addWidget(text('Pulsa las cuatro esquinas del papel: superior izquierda, superior derecha, inferior derecha e inferior izquierda. Otro clic reinicia.')); im=CornerImage(self.images[i]); l.addWidget(im,0,A.AlignCenter); row=QHBoxLayout(); row.addWidget(btn('Cancelar',d.reject)); row.addWidget(btn('Aplicar',d.accept,True)); l.addLayout(row)
        if d.exec()==QDialog.DialogCode.Accepted:
            if len(im.points)!=4: QMessageBox.warning(self,'Esquinas','Selecciona cuatro puntos.'); return
            try:
                aligned=omr.align(self.images[i],im.corners()); marks=omr.scan(aligned,i); self.install(i,self.images[i],aligned,marks); self.changed(); self.refresh()
            except Exception as e: QMessageBox.warning(self,'No se pudo alinear',str(e))
    def refresh(self,*_):
        slot=self.page.currentIndex(); marks=self.marks.get(slot,[]); indices=list(self.indices(slot)); shown=[(j,i) for j,i in enumerate(indices) if self.filter.currentIndex()==1 or not self.answers[i]]
        self.table.setRowCount(0); self.table.setRowCount(len(shown))
        for row,(j,i) in enumerate(shown):
            self.table.setRowHeight(row,57); m=marks[j] if j<len(marks) else None
            status=m.status if m else ('Respuesta conservada · sin recorte' if self.answers[i] else 'Hoja no cargada')
            if m and omr.proposed(m)=='-': status='Sin azul · blanco propuesto'
            elif m and m.suggestion and not omr.proposed(m): status+=f' · posible {m.suggestion}'
            for col,s in [(0,self.config.number(i)),(2,status)]:
                t=QTableWidgetItem(s); t.setTextAlignment(A.AlignCenter); self.table.setItem(row,col,t)
            if m:
                x,y,x2,y2=m.crop; crop=QLabel(); crop.setAlignment(A.AlignCenter); crop.setPixmap(pix(self.aligned[slot][y:y2,x:x2]).scaled(165,52,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); self.table.setCellWidget(row,1,crop)
            combo=SafeComboBox(); vals=['',*self.config.letters,'-']; combo.addItems(['Pendiente',*self.config.letters,'En blanco']); combo.setCurrentIndex(vals.index(self.answers[i])); combo.currentIndexChanged.connect(lambda k,n=i,v=vals:self.set_choice(n,v[k])); self.table.setCellWidget(row,3,combo)
        self.update_count()
    def set_choice(self,i,value):
        self.answers[i]=value; self.changed(); self.update_count()
    def update_count(self):
        n=self.answers.count(''); self.count.setText(f'{len(self.answers)-n} de {len(self.answers)} respuestas propuestas o revisadas · {n} pendientes. Las casillas fuera del solucionario no cuentan.')
    def reset(self):
        if any(self.answers) and not confirm(self,'Reiniciar lectura','Se descartarán las respuestas y revisiones actuales. ¿Continuar?'): return
        self.images.clear(); self.aligned.clear(); self.marks.clear(); self.answers[:]=['']*len(self.answers); self.changed(); self.refresh()
