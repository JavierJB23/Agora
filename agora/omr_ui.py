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
    def __init__(self,back):
        super().__init__(); self.images={}; self.aligned={}; self.marks={}; self.choices={}
        l=QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(12)
        l.addWidget(btn('‹ Volver al inicio',back),0,A.AlignLeft); l.addWidget(text('Corrector automático · Lector óptico','heading'))
        l.addWidget(text('BLOCK 05 · Prueba de lectura. Importa la hoja, revisa las marcas azules y comprueba las casillas. Todavía no calcula la nota ni guarda un simulacro.'))
        row=QHBoxLayout(); row.addWidget(btn('Importar hoja principal (PDF o foto)',lambda:self.load(0),True)); row.addWidget(btn('Importar página de reservas',lambda:self.load(1))); l.addLayout(row)
        self.note=text('Plantilla compatible: 120 preguntas, A/B/C y 9 reservas. Las marcas rojas no se usan como respuesta original.'); l.addWidget(self.note)
        row=QHBoxLayout(); self.page=SafeComboBox(); self.page.addItems(['Hoja principal','Reservas']); self.page.currentIndexChanged.connect(self.refresh); row.addWidget(self.page); row.addWidget(btn('Ver hoja y casillas',self.preview)); row.addWidget(btn('Ajustar esquinas',self.adjust)); l.addLayout(row)
        l.addWidget(text('Revisa los recortes. Una sugerencia no es una respuesta confirmada. Sin azul puede significar blanco, tinta negra o mala iluminación.'))
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['Pregunta','Recorte','Lectura azul','Estado','Tu revisión']); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.verticalHeader().hide(); self.table.setMinimumHeight(440); l.addWidget(self.table)
        row=QHBoxLayout(); row.addWidget(btn('Aceptar sugerencias azules revisadas',self.accept_suggestions)); row.addWidget(btn('Marcar sin azul como blanco',self.blanks)); row.addWidget(btn('Reiniciar lectura',self.reset)); l.addLayout(row)
        self.count=text('Sin hoja cargada.'); l.addWidget(self.count)
    def load(self,slot):
        d=ImportDialog(self,omr.EXTENSIONS)
        if d.exec()!=QDialog.DialogCode.Accepted or not d.item: return
        try:
            name,data=d.item; images=omr.decode(name,data)
            if slot==1 and len(images)!=1: raise ValueError('Para reservas selecciona solo la segunda página; un PDF de dos páginas se importa desde Hoja principal.')
            if slot==0 and self.images and not confirm(self,'Nueva hoja','Se sustituirá la lectura anterior, incluidas sus revisiones. ¿Continuar?'): return
            if slot==1 and slot in self.images and not confirm(self,'Sustituir reservas','Se perderá la revisión de reservas actual. ¿Continuar?'): return
            if slot==0: self.images.clear(); self.aligned.clear(); self.marks.clear(); self.choices.clear()
            for j,im in enumerate(images):
                i=slot+j; self.images[i]=im; self.process(i)
            self.page.setCurrentIndex(slot); self.refresh()
        except Exception as e: QMessageBox.warning(self,'No se pudo leer',str(e))
    def process(self,i,corners=None):
        self.marks.pop(i,None); self.aligned.pop(i,None); self.choices.pop(i,None)
        try:
            im=omr.align(self.images[i],corners); self.aligned[i]=im; self.marks[i]=omr.scan(im,i); self.choices[i]=['']*len(self.marks[i]); self.note.setText('Hoja procesada. Revisa la correspondencia de las casillas y todas las respuestas.')
        except Exception as e: self.note.setText(str(e))
    def preview(self):
        i=self.page.currentIndex()
        if i not in self.aligned: return
        d=QDialog(self); d.setWindowTitle('Comprobar alineación'); l=QVBoxLayout(d); l.addWidget(text('Los recuadros verdes deben coincidir con cada círculo. Si no coinciden, ajusta las esquinas.')); im=QLabel(); im.setPixmap(pix(omr.overlay(self.aligned[i],i)).scaled(580,720,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); l.addWidget(im,0,A.AlignCenter); l.addWidget(btn('Cerrar',d.accept),0,A.AlignCenter); d.exec()
    def adjust(self):
        i=self.page.currentIndex()
        if i not in self.images: return
        if any(self.choices.get(i,[])) and not confirm(self,'Ajustar esquinas','Se reiniciará la revisión de esta página. ¿Continuar?'): return
        d=QDialog(self); d.setWindowTitle('Ajustar esquinas'); l=QVBoxLayout(d); l.addWidget(text('Pulsa las cuatro esquinas del papel: superior izquierda, superior derecha, inferior derecha e inferior izquierda. Otro clic reinicia.')); im=CornerImage(self.images[i]); l.addWidget(im,0,A.AlignCenter); row=QHBoxLayout(); row.addWidget(btn('Cancelar',d.reject)); row.addWidget(btn('Aplicar',d.accept,True)); l.addLayout(row)
        if d.exec()==QDialog.DialogCode.Accepted:
            if len(im.points)!=4: QMessageBox.warning(self,'Esquinas','Selecciona cuatro puntos.'); return
            self.process(i,im.corners()); self.refresh()
    def refresh(self,*_):
        i=self.page.currentIndex(); marks=self.marks.get(i,[]); self.table.setRowCount(0); self.table.setRowCount(len(marks))
        for j,m in enumerate(marks):
            self.table.setRowHeight(j,57)
            for col,s in [(0,m.number),(2,m.suggestion or '—'),(3,m.status)]:
                t=QTableWidgetItem(s); t.setTextAlignment(A.AlignCenter); self.table.setItem(j,col,t)
            x,y,x2,y2=m.crop; crop=QLabel(); crop.setAlignment(A.AlignCenter); crop.setPixmap(pix(self.aligned[i][y:y2,x:x2]).scaled(150,50,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); self.table.setCellWidget(j,1,crop)
            combo=SafeComboBox(); combo.addItems(['Pendiente','A','B','C','En blanco']); combo.setCurrentIndex(['','A','B','C','-'].index(self.choices[i][j])); combo.currentIndexChanged.connect(lambda k,p=i,r=j:self.set_choice(p,r,k)); self.table.setCellWidget(j,4,combo)
        self.update_count()
    def set_choice(self,i,j,k): self.choices[i][j]=['','A','B','C','-'][k]; self.update_count()
    def update_count(self):
        total=sum(len(x) for x in self.marks.values()); reviewed=sum(bool(x) for choices in self.choices.values() for x in choices); self.count.setText(f'{reviewed} de {total} casillas revisadas. Las casillas sobrantes aún no se excluyen hasta importar el solucionario en BLOCK 06.' if total else 'Sin lectura válida.')
    def accept_suggestions(self):
        i=self.page.currentIndex()
        if not self.marks.get(i) or not confirm(self,'Confirmar lectura','¿Has comprobado la alineación y las sugerencias azules de esta página? Solo se completarán las pendientes con una sugerencia única.'): return
        for j,m in enumerate(self.marks[i]):
            if not self.choices[i][j] and m.suggestion and 'débil' not in m.status: self.choices[i][j]=m.suggestion
        self.refresh()
    def blanks(self):
        i=self.page.currentIndex()
        if not self.marks.get(i) or not confirm(self,'Confirmar blancos','¿Has verificado que todas las casillas pendientes sin marca azul están realmente en blanco? No se resolverán las marcas dobles.'): return
        for j,m in enumerate(self.marks[i]):
            if not self.choices[i][j] and max(m.scores)<15: self.choices[i][j]='-'
        self.refresh()
    def reset(self):
        if self.images and not confirm(self,'Reiniciar lectura','Se descartarán las hojas y revisiones de esta prueba. ¿Continuar?'): return
        self.images.clear(); self.aligned.clear(); self.marks.clear(); self.choices.clear(); self.note.setText('Importa una nueva hoja.'); self.refresh()
