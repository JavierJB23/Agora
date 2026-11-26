"""Optical reader validation workspace; scoring integration belongs to block 06."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPixmap,QPainter,QPen,QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QDialog,QMessageBox,QScrollArea,QLineEdit)
from .controls import SafeComboBox, SafeSpinBox
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
            self.page.setCurrentIndex(1 if '' not in self.answers[:self.config.questions] and '' in self.answers[self.config.questions:] else 0 if any(not m.number.startswith('R') for marks in self.marks.values() for m in marks) else 1)
            if all(self.answers): self.filter.setCurrentIndex(1)
        self.refresh()
    def indices(self,slot):
        return range(0,self.config.questions) if slot==0 else range(self.config.questions,self.config.size)
    def target_index(self,number):
        if number.startswith('R'):
            n=int(number[1:]); return self.config.questions+n-1 if 1<=n<=self.config.reserves else None
        n=int(number); return n-1 if 1<=n<=self.config.questions else None
    def proposal(self,m):
        if len(m.scores)<self.config.options: return ''
        v=omr.proposed(m)
        return v if v in (*self.config.letters,'-') else ''
    def choose_numbering(self,aligned,blocks):
        import cv2 as cv
        shown=aligned.copy(); next_number=1; defaults=[]; details=[]
        for i,((x,y,w,h),marks) in enumerate(blocks):
            corners=[pt for m in marks for pt in m.quad]
            if corners:
                hull=cv.convexHull(np.round(corners).astype(np.int32)); cv.polylines(shown,[hull],True,(165,83,121),3)
            else: cv.rectangle(shown,(x,y),(x+w,y+h),(165,83,121),3)
            cv.putText(shown,str(i+1),(x+3,max(22,y-5)),cv.FONT_HERSHEY_SIMPLEX,.9,(165,83,121),3)
            defaults.append(str(next_number)); next_number+=len(marks)
            details.append(f'{i+1}: {len(marks)} filas, {len(marks[0].scores)} opciones')
        d=QDialog(self); d.setWindowTitle('Numeración de la hoja'); d.resize(720,min(820,self.screen().availableGeometry().height()-80)); l=QVBoxLayout(d)
        l.addWidget(text('Confirma el número de la primera pregunta de cada bloque. Usa R1, R4… para reservas.'))
        preview=QLabel(); preview.setAlignment(A.AlignCenter); preview.setPixmap(pix(shown).scaled(640,max(200,min(630,self.screen().availableGeometry().height()-300)),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); l.addWidget(preview,1)
        l.addWidget(text(' · '.join(details))); field=QLineEdit(', '.join(defaults)); l.addWidget(field)
        row=QHBoxLayout(); row.addWidget(btn('Cancelar',d.reject)); row.addWidget(btn('Restablecer',lambda:field.setText(', '.join(defaults)))); row.addWidget(btn('Ajuste por bloques',lambda:d.done(2))); row.addWidget(btn('Confirmar',d.accept,True)); l.addLayout(row)
        while True:
            outcome=d.exec()
            if outcome==2:
                marks=self.guided_dialog(aligned)
                if marks is not None: return marks
                continue
            if outcome!=QDialog.DialogCode.Accepted: return None
            try: return omr.number_blocks(blocks,field.text().split(','))
            except ValueError as e: QMessageBox.warning(d,'Numeración incorrecta',str(e))
    def guided_dialog(self,aligned):
        allmarks=[]
        while True:
            form=QDialog(self); form.setWindowTitle('Bloque de respuestas'); fl=QVBoxLayout(form)
            fl.addWidget(text('Primera pregunta del bloque (1, 31, R1…)')); number=QLineEdit('1' if not allmarks else ''); fl.addWidget(number)
            fl.addWidget(text('Número de filas del bloque')); rows_box=SafeSpinBox(); rows_box.setRange(2,120); rows_box.setValue(30); fl.addWidget(rows_box)
            fl.addWidget(text('Casillas impresas por fila')); options_box=SafeSpinBox(); options_box.setRange(2,5); options_box.setValue(self.config.options); fl.addWidget(options_box)
            buttons=QHBoxLayout(); buttons.addWidget(btn('Cancelar',form.reject)); buttons.addWidget(btn('Continuar',form.accept,True)); fl.addLayout(buttons)
            if form.exec()!=QDialog.DialogCode.Accepted: return None
            start=number.text(); rows=rows_box.value(); options=options_box.value()
            d=QDialog(self); d.setWindowTitle('Ajustar bloque'); d.resize(720,min(800,self.screen().availableGeometry().height()-80)); l=QVBoxLayout(d)
            l.addWidget(text('Señala los centros de las casillas exteriores del bloque, no los números.'))
            status=text('','tileTitle'); l.addWidget(status); apply=btn('Aplicar',lambda:None,True)
            refs=['Primera fila · A','Primera fila · última opción','Última fila · última opción','Última fila · A']
            def update(n):
                status.setText(f'{n}/4 · {refs[n]}' if n<4 else '4/4 · Referencias seleccionadas'); apply.setEnabled(n==4)
            im=CornerImage(aligned,update); sc=QScrollArea(); sc.setWidget(im); sc.setAlignment(A.AlignCenter); l.addWidget(sc,1)
            tools=QHBoxLayout(); tools.addWidget(btn('Deshacer',im.undo)); tools.addWidget(btn('Reiniciar',im.reset)); zoom=SafeComboBox(); zoom.addItems(['Ajustar a ventana','Ampliar ×2','Ampliar ×3']); zoom.currentIndexChanged.connect(lambda j:im.set_zoom(j+1)); tools.addWidget(zoom); l.addLayout(tools)
            row=QHBoxLayout(); row.addWidget(btn('Cancelar',d.reject)); apply.clicked.connect(d.accept); row.addWidget(apply); l.addLayout(row)
            if d.exec()!=QDialog.DialogCode.Accepted: return None
            marks=omr.guided_block(aligned,im.corners(),rows,options,start)
            if {m.number for m in marks}&{m.number for m in allmarks}: raise ValueError('Los bloques se solapan en numeración.')
            allmarks.extend(marks)
            if not confirm(self,'Añadir bloque','¿Hay otro bloque de preguntas o reservas en esta misma página?'): return allmarks
    def read_page(self,im):
        aligned=omr.align(im)
        try:
            slot=omr.identify(aligned); return aligned,omr.scan(aligned,slot)
        except ValueError as e:
            circle_error=str(e)
        try:
            square_view,blocks=omr.square_page(im,aligned)
        except ValueError:
            blocks=None
        if blocks:
            marks=self.choose_numbering(square_view,blocks)
            return (square_view,marks) if marks is not None else None
        else:
            box=QMessageBox(self); box.setWindowTitle('Alinear hoja'); box.setText(circle_error); box.setInformativeText('Puedes ajustar la plantilla de círculos conocida o indicar otros bloques de casillas.'); box.setIcon(QMessageBox.Icon.Question)
            ordinary=box.addButton('Círculos A–C',QMessageBox.ButtonRole.ActionRole); reserve=box.addButton('Reservas A–C',QMessageBox.ButtonRole.ActionRole); generic=box.addButton('Otro diseño',QMessageBox.ButtonRole.ActionRole); cancel=box.addButton('Cancelar',QMessageBox.ButtonRole.RejectRole); box.setEscapeButton(cancel); box.exec()
            if box.clickedButton() is generic:
                marks=self.guided_dialog(aligned); return (aligned,marks) if marks else None
            if box.clickedButton() not in (ordinary,reserve): return None
            return self.alignment_dialog(im,0 if box.clickedButton() is ordinary else 1)
    def load(self,checked=False,force_guided=False):
        d=ImportDialog(self,omr.EXTENSIONS,multiple=True,max_files=20)
        if d.exec()!=QDialog.DialogCode.Accepted or not d.items: return
        try:
            pending={}; count=0; occupied=set(self.marks)
            for name,data in d.items:
                for im in omr.decode(name,data):
                    count+=1
                    if count>20: raise ValueError('Selecciona un máximo de 20 páginas en total.')
                    if force_guided:
                        aligned=omr.align(im); marks=self.guided_dialog(aligned); result=(aligned,marks) if marks else None
                    else: result=self.read_page(im)
                    if result is None: return
                    aligned,marks=result
                    nums={m.number for m in marks if self.target_index(m.number) is not None}
                    if not nums: continue
                    if any(nums&{m.number for m in p[2]} for p in pending.values()):
                        if not confirm(self,'Numeración repetida','Esta página coincide con otra de la misma importación. ¿Indicar su numeración mediante un ajuste por bloques?'): return
                        marks=self.guided_dialog(aligned)
                        if not marks: return
                        nums={m.number for m in marks if self.target_index(m.number) is not None}
                        if not nums or any(nums&{m.number for m in p[2]} for p in pending.values()): raise ValueError('Hay páginas con numeraciones repetidas o fuera del solucionario.')
                    overlaps=[slot for slot,old in self.marks.items() if nums&{m.number for m in old}]
                    if len(overlaps)>1: raise ValueError('La página se solapa con varias lecturas guardadas. Reinicia la lectura para sustituirlas.')
                    if overlaps:
                        slot=overlaps[0]
                        oldnums={m.number for m in self.marks[slot] if self.target_index(m.number) is not None}
                        if not oldnums<=nums: raise ValueError('La página solo sustituye parte de una lectura previa. Reinicia la lectura para cambiar la distribución.')
                    else:
                        preferred=1 if all(n.startswith('R') for n in nums) else 0
                        slot=preferred if preferred not in occupied else next((i for i in range(2,100) if i not in occupied),None)
                        if slot is None: raise ValueError('Demasiadas páginas guardadas.')
                    occupied.add(slot); pending[slot]=(im,aligned,marks)
            if not pending: raise ValueError('No se han localizado preguntas del solucionario en las hojas importadas.')
            if any(self.answers[i] for p in pending.values() for m in p[2] if (i:=self.target_index(m.number)) is not None) and not confirm(self,'Sustituir lectura','Se sustituirán las respuestas de las páginas importadas. ¿Continuar?'): return
            snapshots={slot:record(im,aligned,marks) for slot,(im,aligned,marks) in pending.items()}
            for slot,(im,aligned,marks) in pending.items(): self.install(slot,im,aligned,marks,snapshots[slot])
            self.page.setCurrentIndex(1 if '' not in self.answers[:self.config.questions] and '' in self.answers[self.config.questions:] else 0 if any(not m.number.startswith('R') for p in pending.values() for m in p[2]) else 1); self.filter.setCurrentIndex(1 if all(self.answers) else 0); self.changed(); self.refresh()
        except Exception as e: QMessageBox.warning(self,'No se pudo leer',str(e))
    def install(self,slot,im,aligned,marks,snapshot=None):
        if snapshot is None: snapshot=record(im,aligned,marks)
        self.images[slot]=im; self.aligned[slot]=aligned; self.marks[slot]=marks; self.records[slot]=snapshot
        for m in marks:
            i=self.target_index(m.number)
            if i is not None: self.answers[i]=self.proposal(m)
    def choose_page(self):
        reserve=self.page.currentIndex()==1
        slots=[i for i,marks in self.marks.items() if any(m.number.startswith('R')==reserve for m in marks)]
        if not slots: return None
        if len(slots)==1: return slots[0]
        names=[f'Hoja {j+1} · '+', '.join(m.number for m in self.marks[i][:2])+'…' for j,i in enumerate(slots)]
        d=QDialog(self); d.setWindowTitle('Elegir hoja'); l=QVBoxLayout(d); combo=SafeComboBox(); combo.addItems(names); l.addWidget(combo); row=QHBoxLayout(); row.addWidget(btn('Cancelar',d.reject)); row.addWidget(btn('Abrir',d.accept,True)); l.addLayout(row)
        return slots[combo.currentIndex()] if d.exec()==QDialog.DialogCode.Accepted else -1
    def preview(self):
        i=self.choose_page()
        if i==-1: return
        if i is None: QMessageBox.information(self,'Ver hoja','No hay imagen conservada para esta página. Los simulacros antiguos pueden contener solo las respuestas.'); return
        import cv2 as cv
        d=QDialog(self); d.setWindowTitle('Hoja de respuestas'); d.resize(690,780); l=QVBoxLayout(d)
        row=QHBoxLayout(); im=QLabel(); im.setAlignment(A.AlignCenter)
        def show(original):
            img=self.images[i] if original else self.aligned[i].copy()
            if not original:
                for m in self.marks[i]:
                    omr.draw_mark(img,m)
            im.setPixmap(pix(img).scaled(600,690,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        row.addWidget(btn('Hoja original',lambda:show(True))); row.addWidget(btn('Casillas leídas',lambda:show(False))); l.addLayout(row)
        sc=QScrollArea(); sc.setWidget(im); sc.setWidgetResizable(True); l.addWidget(sc,1); l.addWidget(btn('Cerrar',d.accept),0,A.AlignCenter); show(True); d.exec()
    def adjust(self):
        i=self.choose_page()
        if i==-1: return
        if i is None:
            if confirm(self,'Ajustar alineación','No hay imagen para este tipo de preguntas. ¿Importar una hoja mediante el ajuste por bloques?'): self.load(force_guided=True)
            return
        try:
            aligned0=self.aligned[i]; old=self.marks[i]
            legacy=next((j for j in (0,1) if [m.number for m in old]==[n for n,_,_ in omr.locations(j)] and all(len(m.scores)==3 for m in old)),None)
            if legacy is not None:
                adjusted=self.alignment_dialog(self.images[i],legacy)
            else:
                marks=self.guided_dialog(aligned0); adjusted=(aligned0,marks) if marks else None
            if adjusted is None: return
            aligned,marks=adjusted
            if not confirm(self,'Aplicar alineación','Se volverán a interpretar las respuestas de esta página. ¿Continuar?'): return
            newnums={m.number for m in marks if self.target_index(m.number) is not None}
            if not newnums or any(newnums&{m.number for m in ms} for slot,ms in self.marks.items() if slot!=i): raise ValueError('El ajuste se solapa con otra hoja o no contiene preguntas del examen.')
            snapshot=record(self.images[i],aligned,marks)
            # A changed mapping must invalidate only the old answers no longer covered.
            for m in old:
                idx=self.target_index(m.number)
                if idx is not None and m.number not in newnums: self.answers[idx]=''
            self.install(i,self.images[i],aligned,marks,snapshot); self.changed(); self.refresh()
        except Exception as e: QMessageBox.warning(self,'No se pudo alinear',str(e)+'\n\nSe conserva la lectura anterior. Usa los centros de los círculos indicados o la alineación automática.')
    def alignment_dialog(self,original,i):
        d=QDialog(self); d.setWindowTitle('Ajustar alineación'); d.resize(720,min(800,self.screen().availableGeometry().height()-80)); l=QVBoxLayout(d)
        refs=['1 · A','91 · C','120 · C','30 · A'] if i==0 else ['R1 · A','R7 · C','R9 · C','R3 · A']
        guide=text('Marca el CENTRO de los círculos indicados, no los bordes del papel.'); l.addWidget(guide)
        status=text('','tileTitle'); l.addWidget(status); apply=btn('Aplicar',lambda:None,True)
        def update(n):
            status.setText(f'{n}/4 · Ahora: {refs[n]}' if n<4 else '4/4 · Referencias seleccionadas'); apply.setEnabled(n==4)
        im=CornerImage(original,update); sc=QScrollArea(); sc.setWidget(im); sc.setAlignment(A.AlignCenter); l.addWidget(sc,1)
        tools=QHBoxLayout(); tools.addWidget(btn('Deshacer punto',im.undo)); tools.addWidget(btn('Reiniciar puntos',im.reset)); zoom=SafeComboBox(); zoom.addItems(['Ajustar a ventana','Ampliar ×2','Ampliar ×3']); zoom.currentIndexChanged.connect(lambda j:im.set_zoom(j+1)); tools.addWidget(zoom); l.addLayout(tools)
        row=QHBoxLayout(); row.addWidget(btn('Cancelar',d.reject)); row.addWidget(btn('Alineación automática',lambda:d.done(2))); row.addWidget(btn('Ajuste por bloques',lambda:d.done(3))); apply.clicked.connect(d.accept); row.addWidget(apply); l.addLayout(row)
        outcome=d.exec()
        if outcome==3:
            aligned=omr.align(original); marks=self.guided_dialog(aligned); return (aligned,marks) if marks else None
        if outcome not in (QDialog.DialogCode.Accepted,2): return None
        aligned=omr.align(original) if outcome==2 else omr.align_grid(original,i,im.corners())
        if omr.identify(aligned)!=i: raise ValueError('El tipo de hoja no coincide con el seleccionado.')
        return aligned,omr.scan(aligned,i)
    def refresh(self,*_):
        slot=self.page.currentIndex(); lookup={m.number:(page,m) for page,marks in self.marks.items() for m in marks}; indices=list(self.indices(slot)); shown=[(j,i) for j,i in enumerate(indices) if self.filter.currentIndex()==1 or not self.answers[i]]
        self.table.setRowCount(0); self.table.setRowCount(len(shown))
        for row,(j,i) in enumerate(shown):
            self.table.setRowHeight(row,48); page,m=lookup.get(self.config.number(i),(None,None))
            status=m.status if m else ('Respuesta conservada · sin recorte' if self.answers[i] else 'Hoja no cargada')
            if m and len(m.scores)<self.config.options: status='Faltan opciones impresas · revisar'
            elif m and self.proposal(m)=='-': status='Sin azul · blanco propuesto'
            elif m and m.suggestion and m.suggestion not in self.config.letters: status=f'Opción {m.suggestion} no válida · revisar'
            elif m and m.suggestion and not self.proposal(m): status+=f' · posible {m.suggestion}'
            for col,s in [(0,self.config.number(i)),(2,status)]:
                t=QTableWidgetItem(s); t.setTextAlignment(A.AlignCenter); self.table.setItem(row,col,t)
            if m:
                crop=QLabel(); crop.setAlignment(A.AlignCenter); crop.setPixmap(pix(omr.crop_image(self.aligned[page],m)).scaled(155,43,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); self.table.setCellWidget(row,1,crop)
            combo=SafeComboBox(); vals=['',*self.config.letters,'-']; combo.addItems(['Pendiente',*self.config.letters,'En blanco']); combo.setCurrentIndex(vals.index(self.answers[i])); combo.currentIndexChanged.connect(lambda k,n=i,v=vals:self.set_choice(n,v[k])); self.table.setCellWidget(row,3,combo)
        self.update_count()
    def set_choice(self,i,value):
        self.answers[i]=value; self.changed(); self.update_count()
    def update_count(self):
        n=self.answers.count(''); suffix=' · Sin imagen guardada' if not self.images and any(self.answers[i] for i in self.indices(self.page.currentIndex())) else ''; self.count.setText(f'{len(self.answers)-n}/{len(self.answers)} respuestas · {n} pendientes'+suffix)
    def reset(self):
        if any(self.answers) and not confirm(self,'Reiniciar lectura','Se descartarán las respuestas y revisiones actuales. ¿Continuar?'): return
        self.images.clear(); self.aligned.clear(); self.marks.clear(); self.records.clear(); self.answers[:]=['']*len(self.answers); self.changed(); self.refresh()
