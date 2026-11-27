"""Optical reader validation workspace; scoring integration belongs to block 06."""
from PySide6.QtCore import Qt,QThread,Signal,QEventLoop,QTimer
from time import monotonic
from PySide6.QtGui import QImage,QPixmap,QPainter,QPen,QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QDialog,QMessageBox,QScrollArea,QLineEdit,QSizePolicy,QProgressBar)
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

def compact_btn(s,fn,primary=False):
    b=btn(s,fn,primary)
    if not primary: b.setObjectName('opticalAction')
    b.setStyleSheet('text-align:center; padding:7px 14px; min-width:100px;')
    b.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed)
    return b

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

class RestoreAutomatic(Exception):
    """Return from a manual editor to the automatic preview."""

class ReadWorker(QThread):
    progress=Signal(int,str)
    def __init__(self,items,config,parent=None):
        super().__init__(parent); self.items=items; self.config=config; self.results=[]; self.errors=[]; self.failure=None
    def run(self):
        try:
            pages=[]
            for j,(name,data) in enumerate(self.items):
                self.progress.emit(round(20*j/len(self.items)),f'Abriendo archivo {j+1} de {len(self.items)}')
                try: decoded=omr.decode(name,data)
                except Exception as e:
                    self.errors.append(f'{name}: {e}'); continue
                if len(pages)+len(decoded)>20: raise ValueError('Selecciona un máximo de 20 páginas en total.')
                pages.extend((name,k+1,im) for k,im in enumerate(decoded))
            for j,(name,k,im) in enumerate(pages):
                self.progress.emit(20+round(75*j/len(pages)),f'Leyendo hoja {j+1} de {len(pages)}')
                try:
                    def stage(fraction,label):
                        self.progress.emit(20+round(75*(j+fraction)/len(pages)),f'Hoja {j+1} de {len(pages)} · {label}')
                    aligned,marks=omr.automatic_page(im,self.config.questions,self.config.reserves,self.config.options,progress=stage,verify_ocr=True)
                    stage(.90,'Conservando imagen')
                    self.results.append((im,aligned,marks,record(im,aligned,marks)))
                except Exception as e: self.errors.append(f'{name} · página {k}: {e}')
            self.progress.emit(95,'Comprobando páginas')
        except Exception as e: self.failure=str(e)

class OpticalPage(QWidget):
    def __init__(self,config,answers,cache,changed):
        super().__init__(); self.config=config; self.answers=answers; self.changed=changed
        self.images=cache.setdefault('images',{}); self.aligned=cache.setdefault('aligned',{}); self.marks=cache.setdefault('marks',{}); self.records=cache.setdefault('records',{})
        l=QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(7)
        l.addWidget(btn('Importar hojas de respuestas (PDF o fotos)',self.load,True))
        row=QHBoxLayout(); self.page=SafeComboBox(); self.page.addItems(['Preguntas ordinarias','Reservas']); self.page.currentIndexChanged.connect(self.refresh); row.addWidget(self.page); self.filter=SafeComboBox(); self.filter.addItems(['Solo pendientes','Todas las preguntas']); self.filter.currentIndexChanged.connect(self.refresh); row.addWidget(self.filter); row.addWidget(btn('Ver hoja y casillas',self.preview)); row.addWidget(btn('Releer hoja',self.adjust)); l.addLayout(row)
        self.count=text(''); self.count.setToolTip('Las lecturas claras se rellenan automáticamente; revisa las dudosas y las posibles anuladas.'); l.addWidget(self.count)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(['Pregunta','Recorte original','Estado de lectura','Respuesta']); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.verticalHeader().hide(); self.table.setMinimumHeight(260); l.addWidget(self.table)
        self.progress_info=text(''); self.progress_bar=QProgressBar(); self.progress_bar.setRange(0,100); self.progress_bar.setFixedHeight(12); self.progress_bar.setTextVisible(False); self.progress_bar.setAlignment(A.AlignCenter)
        self.progress_bar.setStyleSheet('QProgressBar {background:#F4D6E3;border:1px solid #E8CEDB;border-radius:8px;text-align:center;color:#75405B;} QProgressBar::chunk {background:#A55379;border-radius:7px;}')
        l.addWidget(self.progress_info); l.addWidget(self.progress_bar); self.progress_info.hide(); self.progress_bar.hide()
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
        import numpy as np
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
        row=QHBoxLayout(); row.addWidget(compact_btn('Cancelar',d.reject)); row.addWidget(compact_btn('Restablecer',lambda:field.setText(', '.join(defaults)))); row.addWidget(compact_btn('Ajuste por bloques',lambda:d.done(2))); row.addWidget(compact_btn('Confirmar',d.accept,True)); l.addLayout(row)
        while True:
            outcome=d.exec()
            if outcome==2:
                marks=self.guided_dialog(aligned)
                if marks is not None: return marks
                continue
            if outcome!=QDialog.DialogCode.Accepted: return None
            try: return omr.number_blocks(blocks,field.text().split(','))
            except ValueError as e: QMessageBox.warning(d,'Numeración incorrecta',str(e))
    def guided_dialog(self,aligned,can_restore=False,printed_options=None):
        allmarks=[]
        while True:
            form=QDialog(self); form.setWindowTitle('Bloque de respuestas'); fl=QVBoxLayout(form)
            fl.addWidget(text('Primera pregunta del bloque (1, 31, R1…)')); number=QLineEdit('1' if not allmarks else ''); fl.addWidget(number)
            fl.addWidget(text('Número de filas del bloque')); rows_box=SafeSpinBox(); rows_box.setRange(2,120); rows_box.setValue(30); fl.addWidget(rows_box)
            fl.addWidget(text('Casillas impresas por fila')); options_box=SafeSpinBox(); options_box.setRange(2,5); options_box.setValue(printed_options or self.config.options); fl.addWidget(options_box)
            buttons=QHBoxLayout(); buttons.addWidget(compact_btn('Cancelar',form.reject)); buttons.addWidget(compact_btn('Continuar',form.accept,True)); fl.addLayout(buttons)
            if form.exec()!=QDialog.DialogCode.Accepted: return None
            start=number.text(); rows=rows_box.value(); options=options_box.value()
            d=QDialog(self); d.setWindowTitle('Ajustar bloque'); d.resize(720,min(800,self.screen().availableGeometry().height()-80)); l=QVBoxLayout(d)
            l.addWidget(text('Marca los centros de las cuatro casillas exteriores de UNA columna, no de toda la hoja ni los números.'))
            status=text('','tileTitle'); l.addWidget(status); apply=compact_btn('Vista previa',lambda:None,True)
            refs=['Primera fila · A','Primera fila · última opción','Última fila · última opción','Última fila · A']
            def update(n):
                status.setText(f'{n}/4 · {refs[n]}' if n<4 else '4/4 · Referencias seleccionadas'); apply.setEnabled(n==4)
            im=CornerImage(aligned,update); sc=QScrollArea(); sc.setWidget(im); sc.setAlignment(A.AlignCenter); l.addWidget(sc,1)
            tools=QHBoxLayout(); tools.addWidget(compact_btn('Deshacer',im.undo)); tools.addWidget(compact_btn('Reiniciar',im.reset)); zoom=SafeComboBox(); zoom.addItems(['Ajustar a ventana','Ampliar ×2','Ampliar ×3']); zoom.currentIndexChanged.connect(lambda j:im.set_zoom(j+1)); tools.addWidget(zoom); l.addLayout(tools)
            row=QHBoxLayout(); row.addWidget(compact_btn('Cancelar',d.reject));
            if can_restore: row.addWidget(compact_btn('Restablecer automática',lambda:d.done(2)))
            apply.setText('Vista previa' if can_restore else 'Aplicar'); apply.clicked.connect(d.accept); row.addWidget(apply); l.addLayout(row)
            outcome=d.exec()
            if can_restore and outcome==2: raise RestoreAutomatic()
            if outcome!=QDialog.DialogCode.Accepted: return None
            marks=omr.guided_block(aligned,im.corners(),rows,options,start)
            if {m.number for m in marks}&{m.number for m in allmarks}: raise ValueError('Los bloques se solapan en numeración.')
            allmarks.extend(marks)
            if not confirm(self,'Añadir bloque','¿Hay otro bloque de preguntas o reservas en esta misma página?'): return allmarks
    def read_page(self,im):
        try:
            return self.automatic_candidate(im)
        except ValueError as e:
            QMessageBox.warning(self,'Lectura no verificada',str(e))
            return None
    def run_import(self,items):
        # Worker touches only arrays and files. All widget and storage changes stay on GUI thread.
        worker=ReadWorker(items,self.config,self); loop=QEventLoop(); timer=QTimer(self); timer.setInterval(250)
        state=[0,'Preparando archivos']; reading=[None,None]
        def update():
            value,phase=state
            eta='Calculando tiempo restante…'
            if reading[1] is not None and 20<value<95:
                eta=f'Quedan aprox. {max(1,round(reading[1]-monotonic()))} s'
            if value>=95: eta='Finalizando…'
            self.progress_info.setText(f'{value} % · {phase} · {eta}'); self.progress_bar.setValue(value)
        def advance(value,phase):
            if value>=20 and reading[0] is None: reading[0]=monotonic()
            value=max(state[0],value)
            if reading[0] is not None and 20<value<95:
                now=monotonic(); reading[1]=now+(now-reading[0])*(95-value)/(value-20)
            state[:]=[value,phase]; update()
        worker.progress.connect(advance,Qt.ConnectionType.QueuedConnection); worker.finished.connect(loop.quit,Qt.ConnectionType.QueuedConnection); timer.timeout.connect(update)
        self.progress_info.show(); self.progress_bar.show(); update()
        window=self.window(); window.setEnabled(False); timer.start()
        try:
            worker.start(); loop.exec(); worker.wait()
            if worker.failure: raise ValueError(worker.failure)
            return worker.results,worker.errors
        finally:
            timer.stop(); timer.deleteLater(); window.setEnabled(True); worker.deleteLater()
    def page_numbers(self,marks):
        # Keep physical reserve sheets even if the key has no reserve solutions.
        return {m.number for m in marks if self.target_index(m.number) is not None or m.number.startswith('R')}
    def load(self,checked=False,force_guided=False):
        d=ImportDialog(self,omr.EXTENSIONS,multiple=True,max_files=20)
        if d.exec()!=QDialog.DialogCode.Accepted or not d.items: return
        self.import_items(d.items)

    def import_items(self,items):
        if not items: return
        try:
            results,errors=self.run_import(items)
            pending={}; occupied=set(self.marks)
            for im,aligned,marks,snapshot in results:
                nums=self.page_numbers(marks)
                if not nums:
                    errors.append('Una página no contiene preguntas del examen.'); continue
                if any(nums&self.page_numbers(p[2]) for p in pending.values()):
                    raise ValueError('Hay páginas con numeraciones repetidas. Comprueba las hojas seleccionadas.')
                overlaps=[slot for slot,old in self.marks.items() if nums&self.page_numbers(old)]
                if len(overlaps)>1: raise ValueError('La página se solapa con varias lecturas guardadas. Reinicia la lectura para sustituirlas.')
                if overlaps:
                    slot=overlaps[0]
                    if not self.page_numbers(self.marks[slot])<=nums: raise ValueError('La página solo sustituye parte de una lectura previa. Reinicia la lectura para cambiar la distribución.')
                else:
                    preferred=1 if all(n.startswith('R') for n in nums) else 0
                    slot=preferred if preferred not in occupied else next((i for i in range(2,100) if i not in occupied),None)
                    if slot is None: raise ValueError('Demasiadas páginas guardadas.')
                occupied.add(slot); pending[slot]=(im,aligned,marks,snapshot)
            if not pending: raise ValueError('No se han localizado preguntas en las hojas importadas.\n'+'\n'.join(errors))
            if errors and not confirm(self,'Importación parcial','No se pudieron leer todas las páginas:\n'+'\n'.join(errors)+'\n¿Conservar las hojas reconocidas?'): return
            if any(slot in self.marks for slot in pending) or any(self.answers[i] for p in pending.values() for m in p[2] if (i:=self.target_index(m.number)) is not None):
                if not confirm(self,'Sustituir lectura','Ya hay respuestas cargadas en estas páginas. Se sobreescribirán. ¿Seguro que quieres continuar?'): return
            for slot,(im,aligned,marks,snapshot) in pending.items(): self.install(slot,im,aligned,marks,snapshot)
            self.page.setCurrentIndex(1 if '' not in self.answers[:self.config.questions] and '' in self.answers[self.config.questions:] else 0 if any(not m.number.startswith('R') for p in pending.values() for m in p[2]) else 1); self.filter.setCurrentIndex(1 if all(self.answers) else 0); self.changed(); self.refresh()
            self.progress_bar.setValue(100); self.progress_info.setText('100 % · Lectura completada'); self.progress_bar.repaint()
            if any(m.number.startswith('R') and self.target_index(m.number) is None for p in pending.values() for m in p[2]):
                QMessageBox.information(self,'Reservas sin solucionario','Se ha conservado la hoja de reservas. Las preguntas que no tienen solución en el solucionario se pueden consultar, pero no puntúan.');
        except Exception as e: QMessageBox.warning(self,'No se pudo leer',str(e))
        finally:
            self.progress_bar.hide(); self.progress_info.hide()
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
        if i is None: QMessageBox.information(self,'Ver hoja','No hay hoja reconocida de este tipo en el simulacro.'); return
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
    def automatic_candidate(self,original):
        return omr.automatic_page(original,self.config.questions,self.config.reserves,self.config.options,verify_ocr=True)

    def adjust_existing_block(self,canvas,marks):
        """One common editor for circles and squares, starting from the detected columns."""
        blocks=omr.reading_blocks(marks)
        d=QDialog(self); d.setWindowTitle('Elegir bloque'); l=QVBoxLayout(d)
        l.addWidget(text('Selecciona la columna que quieres ajustar. Las demás se conservarán.'))
        combo=SafeComboBox()
        combo.addItems([f'{ms[0].number} – {ms[-1].number} · {len(ms)} filas · {len(ms[0].scores)} opciones' for ms in blocks]); l.addWidget(combo)
        row=QHBoxLayout(); row.addWidget(compact_btn('Cancelar',d.reject)); row.addWidget(compact_btn('Restablecer automática',lambda:d.done(2))); row.addWidget(compact_btn('Continuar',d.accept,True)); l.addLayout(row)
        outcome=d.exec()
        if outcome==2: raise RestoreAutomatic()
        if outcome!=QDialog.DialogCode.Accepted: return None
        block=blocks[combo.currentIndex()]
        if len(block)<2: raise ValueError('Este bloque solo tiene una fila. Usa la detección automática.')
        # Show the existing block boundaries as a visual guide, without painting on the data read.
        import cv2 as cv
        shown=canvas.copy()
        for m in block: omr.draw_mark(shown,m)
        d=QDialog(self); d.setWindowTitle('Ajustar bloque'); d.resize(720,min(800,self.screen().availableGeometry().height()-80)); l=QVBoxLayout(d)
        l.addWidget(text(f'Preguntas {block[0].number}–{block[-1].number}. Marca los centros de las cuatro casillas exteriores de esta columna, no los bordes del papel.'))
        status=text('','tileTitle'); l.addWidget(status); apply=compact_btn('Vista previa',lambda:None,True)
        last='ABCDE'[len(block[0].scores)-1]
        refs=[f'{block[0].number} · A',f'{block[0].number} · {last}',f'{block[-1].number} · {last}',f'{block[-1].number} · A']
        def update(n):
            status.setText(f'{n}/4 · Ahora: {refs[n]}' if n<4 else '4/4 · Referencias seleccionadas'); apply.setEnabled(n==4)
        im=CornerImage(shown,update); sc=QScrollArea(); sc.setWidget(im); sc.setAlignment(A.AlignCenter); l.addWidget(sc,1)
        tools=QHBoxLayout(); tools.addWidget(compact_btn('Deshacer',im.undo)); tools.addWidget(compact_btn('Reiniciar',im.reset)); zoom=SafeComboBox(); zoom.addItems(['Ajustar a ventana','Ampliar ×2','Ampliar ×3']); zoom.currentIndexChanged.connect(lambda j:im.set_zoom(j+1)); tools.addWidget(zoom); l.addLayout(tools)
        row=QHBoxLayout(); row.addWidget(compact_btn('Cancelar',d.reject)); row.addWidget(compact_btn('Restablecer automática',lambda:d.done(2))); apply.clicked.connect(d.accept); row.addWidget(apply); l.addLayout(row)
        outcome=d.exec()
        if outcome==2: raise RestoreAutomatic()
        if outcome!=QDialog.DialogCode.Accepted: return None
        replacement=omr.guided_block(canvas,im.corners(),len(block),len(block[0].scores),block[0].number)
        return omr.replace_reading_block(marks,block,replacement)

    def alignment_workspace(self,i,original=None,initial=None,error=None):
        """All changes stay local to this dialog until Apply is pressed."""
        if initial is None:
            original=self.images[i]; initial=(self.aligned[i],self.marks[i])
        current=initial; candidate=current
        d=QDialog(self); d.setWindowTitle('Releer hoja'); d.resize(760,min(820,self.screen().availableGeometry().height()-80)); l=QVBoxLayout(d)
        message=text(error or 'Vista previa de la lectura guardada.'); l.addWidget(message)
        preview=QLabel(); preview.setAlignment(A.AlignCenter); l.addWidget(preview,1)
        def show():
            aligned,marks=candidate; canvas=aligned.copy()
            for m in marks: omr.draw_mark(canvas,m)
            preview.setPixmap(pix(canvas).scaled(680,max(200,min(640,self.screen().availableGeometry().height()-300)),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
            apply.setEnabled(bool(marks))
        def automatic():
            nonlocal candidate
            result=self.automatic_candidate(original)
            if result is not None:
                candidate=result; message.setText('Vista previa automática. Aplica para conservarla.'); show()
        def retry():
            try: automatic()
            except ValueError as e: QMessageBox.warning(d,'Lectura no verificada',str(e))
        row=QHBoxLayout(); row.addStretch(1)
        row.addWidget(compact_btn('Restablecer automática',retry))
        row.addStretch(1)
        l.addLayout(row)
        bottom=QHBoxLayout(); bottom.addStretch(1); bottom.addWidget(compact_btn('Cancelar',d.reject)); apply=compact_btn('Aplicar',d.accept,True); bottom.addWidget(apply); bottom.addStretch(1); l.addLayout(bottom)
        show()
        if d.exec()!=QDialog.DialogCode.Accepted or candidate is current or not candidate[1]: return None
        return candidate

    def adjust(self):
        i=self.choose_page()
        if i==-1: return
        if i is None:
            if confirm(self,'Releer hoja','No hay imagen para este tipo de preguntas. ¿Importar una hoja?'): self.load()
            return
        try:
            old=self.marks[i]; adjusted=self.alignment_workspace(i)
            if adjusted is None: return
            aligned,marks=adjusted
            newnums=self.page_numbers(marks)
            if not newnums or any(newnums&{m.number for m in ms} for slot,ms in self.marks.items() if slot!=i): raise ValueError('El ajuste se solapa con otra hoja o no contiene preguntas del examen.')
            if not confirm(self,'Aplicar lectura','Se volverán a interpretar las respuestas de esta página. Se conservarán las anuladas y las respuestas modificadas manualmente que sigan en ella. ¿Continuar?'): return
            snapshot=record(self.images[i],aligned,marks)
            reviewed={}
            for m in old:
                idx=self.target_index(m.number)
                if idx is None: continue
                if m.number not in newnums and self.answers[idx]!='X': self.answers[idx]=''
                elif self.answers[idx] and self.answers[idx]!=self.proposal(m): reviewed[idx]=self.answers[idx]
            self.install(i,self.images[i],aligned,marks,snapshot)
            for idx,value in reviewed.items(): self.answers[idx]=value
            self.changed(); self.refresh()
        except Exception as e: QMessageBox.warning(self,'No se pudo alinear',str(e)+'\n\nSe conserva la lectura anterior.')
    def refresh(self,*_):
        slot=self.page.currentIndex(); lookup={m.number:(page,m) for page,marks in self.marks.items() for m in marks}; indices=list(self.indices(slot)); shown=[(j,i) for j,i in enumerate(indices) if self.filter.currentIndex()==1 or not self.answers[i]]
        extra=sorted((n for n in lookup if slot==1 and n.startswith('R') and self.target_index(n) is None),key=lambda n:int(n[1:])) if self.filter.currentIndex()==1 else []
        self.table.setRowCount(0); self.table.setRowCount(len(shown)+len(extra))
        for row,(j,i) in enumerate(shown):
            self.table.setRowHeight(row,48); page,m=lookup.get(self.config.number(i),(None,None))
            status=m.status if m else ('Respuesta conservada · sin recorte' if self.answers[i] else 'Hoja no cargada')
            if self.answers[i]=='X': status='Anulada manualmente'
            elif m and len(m.scores)<self.config.options: status='Faltan opciones impresas · revisar'
            elif m and 'Posible anulada' in m.status: status=m.status
            elif m and self.proposal(m)=='-': status='Sin azul · blanco propuesto'
            elif m and m.suggestion and m.suggestion not in self.config.letters: status=f'Opción {m.suggestion} no válida · revisar'
            elif m and m.suggestion and not self.proposal(m): status+=f' · posible {m.suggestion}'
            for col,s in [(0,self.config.number(i)),(2,status)]:
                t=QTableWidgetItem(s); t.setTextAlignment(A.AlignCenter)
                self.table.setItem(row,col,t)
            if m:
                crop=QLabel(); crop.setAlignment(A.AlignCenter); crop.setPixmap(pix(omr.crop_image(self.aligned[page],m)).scaled(155,43,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); self.table.setCellWidget(row,1,crop)
            combo=SafeComboBox(); vals=['',*self.config.letters,'-','X']; combo.addItems(['Pendiente',*self.config.letters,'En blanco','Anulada']); combo.setCurrentIndex(vals.index(self.answers[i])); combo.currentIndexChanged.connect(lambda k,n=i,v=vals:self.set_choice(n,v[k])); self.table.setCellWidget(row,3,combo)
        for row,n in enumerate(extra,start=len(shown)):
            page,m=lookup[n]; self.table.setRowHeight(row,48)
            for col,value in ((0,n),(2,m.status+' · Sin solución'),(3,self.proposal(m) or 'Pendiente')):
                item=QTableWidgetItem(value); item.setTextAlignment(A.AlignCenter); self.table.setItem(row,col,item)
            crop=QLabel(); crop.setAlignment(A.AlignCenter); crop.setPixmap(pix(omr.crop_image(self.aligned[page],m)).scaled(155,43,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); self.table.setCellWidget(row,1,crop)
        self.update_count()
    def set_choice(self,i,value):
        self.answers[i]=value; self.changed(); self.update_count()
        # Keep the visual state synchronized without rebuilding the active dropdown.
        for row in range(self.table.rowCount()):
            item=self.table.item(row,0)
            if item and item.text()==self.config.number(i):
                mark=next((m for ms in self.marks.values() for m in ms if m.number==item.text()),None)
                if value=='X': self.table.item(row,2).setText('Anulada manualmente')
                elif self.table.item(row,2).text()=='Anulada manualmente': self.table.item(row,2).setText(mark.status if mark else 'Respuesta revisada')
                break
    def update_count(self):
        n=self.answers.count(''); suffix=' · Sin imagen guardada' if not self.images and any(self.answers[i] for i in self.indices(self.page.currentIndex())) else ''; extra=sum(m.number.startswith('R') and self.target_index(m.number) is None for ms in self.marks.values() for m in ms); self.count.setText(f'{len(self.answers)-n}/{len(self.answers)} respuestas · {n} pendientes'+suffix+(f' · {extra} reservas sin solución (no puntúan)' if extra else ''))
    def reset(self):
        if any(self.answers) and not confirm(self,'Reiniciar lectura','Se descartarán las respuestas y revisiones actuales. ¿Continuar?'): return
        self.images.clear(); self.aligned.clear(); self.marks.clear(); self.records.clear(); self.answers[:]=['']*len(self.answers); self.changed(); self.refresh()
