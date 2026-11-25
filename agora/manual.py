"""Manual correction wizard; import a solution key, then enter personal answers."""
from dataclasses import asdict, replace
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (QWidget,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,QFrame,
 QLineEdit,QCheckBox,QMessageBox,QInputDialog,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QApplication,QDialog)
from .grading import ExamConfig, evaluate, format_number
from .controls import SafeComboBox, SafeSpinBox
from .answer_import import extract_key
from .import_ui import ImportDialog

ALIGN=Qt.AlignmentFlag

def label(text,role='',wrap=False):
    x=QLabel(text); x.setTextFormat(Qt.TextFormat.PlainText); x.setWordWrap(wrap)
    if role: x.setObjectName(role)
    return x

def btn(text,fn,role=''):
    x=QPushButton(text); x.setCursor(Qt.CursorShape.PointingHandCursor)
    if role: x.setObjectName(role)
    x.clicked.connect(fn); return x

def panel(parent, margins=18):
    f=QFrame(); f.setObjectName('panel'); l=QVBoxLayout(f); l.setContentsMargins(*([margins]*4)); l.setSpacing(10); parent.addWidget(f); return l

def confirm(parent,title,text):
    box=QMessageBox(parent); box.setWindowTitle(title); box.setText(text); box.setTextFormat(Qt.TextFormat.PlainText); box.setIcon(QMessageBox.Icon.Question)
    yes=box.addButton('Sí',QMessageBox.ButtonRole.YesRole); no=box.addButton('No',QMessageBox.ButtonRole.NoRole); box.setDefaultButton(no); box.setEscapeButton(no); box.exec(); return box.clickedButton() is yes

class ManualPage(QWidget):
    def __init__(self, storage, go_home):
        super().__init__(); self.storage=storage; self.config=ExamConfig(); self.key=['']*self.config.size; self.answers=['']*self.config.size
        self.key_source=''; self.stage=0; self.cursor=0; self.result=None; self._template_items=[]; self.persist_failed=False; self.attempt_id=None; self.saved_snapshot=None; self.form_override=None
        self.root=QVBoxLayout(self); self.root.setContentsMargins(0,0,0,0); self.root.setSpacing(14)
        top=QHBoxLayout(); top.addWidget(btn('‹  Volver al inicio',go_home)); top.addWidget(btn('Guardar progreso',self.save_progress,'primary')); top.addStretch(); self.root.addLayout(top)
        self.root.addWidget(label('Corrector manual','heading')); self.root.addWidget(label('Importa las soluciones correctas e introduce tus respuestas. Ágora calcula el resultado.','muted',True))
        self.steps=QHBoxLayout(); self.step_labels=[]
        for i,s in enumerate(('1 · Configuración','2 · Soluciones','3 · Respuestas','4 · Resultado')):
            x=btn(s,lambda checked=False,j=i:self.navigate(j),'manualStep'); x.setAccessibleName(s); self.steps.addWidget(x,1); self.step_labels.append(x)
        self.root.addLayout(self.steps)
        self.notice=label('','muted',True); self.root.addWidget(self.notice)
        self.content=QWidget(); self.body=QVBoxLayout(self.content); self.body.setContentsMargins(0,0,0,0); self.body.setSpacing(10); self.root.addWidget(self.content); self.root.addStretch()
        try:
            d=storage.load_draft()
            if d: self.restore(d)
        except Exception as e:
            self.notice.setText('No se pudo recuperar el borrador: '+str(e))
        self.render()

    def restore(self,d):
        c=ExamConfig(**d['config']); k=list(d['key']); a=list(d['answers']); stage=d.get('stage',0); cursor=d.get('cursor',0)
        if len(k)!=c.size or len(a)!=c.size or any(v not in (*c.letters,'X','') for v in k) or any(v not in (*c.letters,'-','') for v in a): raise ValueError('Borrador no válido')
        self.config=c; self.key=k; self.answers=a; self.key_source=d.get('key_source') or ('Plantilla anterior' if all(k) else ''); self.stage=stage if stage in (0,1,2,3) else 0; self.cursor=max(0,min(int(cursor),c.size-1)); self.result=None
        self.attempt_id=d.get('attempt_id'); self.saved_snapshot=self.storage.load_attempt(self.attempt_id) if self.attempt_id is not None else None
        self.form_override=d.get('form') if self.stage==0 else None
        if self.form_override is not None:
            self.form_override=dict(self.form_override,questions=c.questions,reserves=c.reserves,options=c.options)
            if self.form_override==asdict(c): self.form_override=None
        if self.stage>=2 and (not self.key_source or '' in self.key): self.stage=1
        if self.stage==3 and '' in self.answers: self.stage=2
        if (self.stage==3 or d.get('corrected')) and self.key_source and all(k) and all(a): self.result=evaluate(c,k,a)

    def form_data(self):
        return {'name':self.name.text(),'questions':self.config.questions,'reserves':self.config.reserves,'options':self.config.options,'penalty':self.penalty.currentText(),'maximum':self.maximum.text(),'floor_zero':self.floor.isChecked()}

    def payload(self,read_form=False):
        d={'config':asdict(self.config),'key':list(self.key),'answers':list(self.answers),'stage':self.stage,'cursor':self.cursor,'key_source':self.key_source,'attempt_id':self.attempt_id,'corrected':self.result is not None}
        form=self.form_data() if read_form and self.stage==0 and hasattr(self,'name') else self.form_override if self.stage==0 else None
        if form is not None and form!=d['config']: d['form']=dict(form)
        return d

    @staticmethod
    def comparable(d):
        if not d: return None
        return {**{k:d.get(k) for k in ('config','key','answers','key_source','form')},'corrected':bool(d.get('corrected',d.get('stage')==3))}

    def active(self):
        d=self.payload(True)
        return self.attempt_id is not None or any(self.key) or any(self.answers) or self.config!=ExamConfig() or bool(d.get('form'))

    def dirty(self):
        return self.active() and self.comparable(self.payload(True))!=self.comparable(self.saved_snapshot)

    def persist(self,read_form=False):
        try:
            self.storage.save_draft(self.payload(read_form)); self.persist_failed=False
            self.notice.setText('Borrador de recuperación automático · '+('Cambios sin guardar en Mis simulacros.' if self.dirty() else 'Sin cambios pendientes.'))
            return True
        except Exception as e:
            self.persist_failed=True; self.notice.setText('No se pudo guardar el borrador: '+str(e)); return False

    def save_progress(self, *_):
        if not self.active():
            QMessageBox.information(self,'Guardar progreso','Configura un simulacro antes de guardarlo.'); return False
        try:
            d=self.payload(True); self.attempt_id=self.storage.save_attempt(d,self.attempt_id); self.saved_snapshot=dict(d,attempt_id=self.attempt_id)
            self.persist_failed=False; self.notice.setText('Progreso guardado en Mis simulacros.'); return True
        except Exception as e:
            QMessageBox.warning(self,'No se pudo guardar',str(e)); return False

    def allow_leave(self):
        if not self.dirty(): return not self.active() or self.persist(True)
        box=QMessageBox(self); box.setWindowTitle('Cambios sin guardar'); box.setText('No has guardado el progreso en Mis simulacros. ¿Qué quieres hacer?'); box.setInformativeText('Si sales sin guardar, se conserva solo el borrador de recuperación automático.'); box.setIcon(QMessageBox.Icon.Question)
        save=box.addButton('Guardar y salir',QMessageBox.ButtonRole.AcceptRole); leave=box.addButton('Salir sin guardar',QMessageBox.ButtonRole.DestructiveRole); cancel=box.addButton('Cancelar',QMessageBox.ButtonRole.RejectRole); box.setDefaultButton(save); box.setEscapeButton(cancel); box.exec()
        if box.clickedButton() is save: return self.save_progress()
        if box.clickedButton() is leave: return self.persist(True)
        return False

    def allow_enter(self):
        if not self.active(): return True
        box=QMessageBox(self); box.setWindowTitle('Simulacro en curso'); box.setText('Hay un simulacro abierto. ¿Quieres continuar o iniciar uno nuevo?' if self.result is not None else 'Hay un test en curso. ¿Quieres continuar o iniciar uno nuevo?'); box.setInformativeText('Si inicias uno nuevo, el progreso no guardado en Mis simulacros se perderá.'); box.setIcon(QMessageBox.Icon.Question)
        resume=box.addButton('Continuar',QMessageBox.ButtonRole.AcceptRole); new=box.addButton('Iniciar uno nuevo',QMessageBox.ButtonRole.DestructiveRole); cancel=box.addButton('Cancelar',QMessageBox.ButtonRole.RejectRole); box.setDefaultButton(resume); box.setEscapeButton(cancel); box.exec()
        if box.clickedButton() is new: return self.start_new()
        return box.clickedButton() is resume

    def start_new(self):
        try: self.storage.clear_draft()
        except Exception as e: QMessageBox.warning(self,'No se pudo iniciar',str(e)); return False
        self.reset_state(); return True

    def reset_state(self):
        # In-memory reset only: caller handles database changes atomically.
        self.config=ExamConfig(); self.key=['']*self.config.size; self.answers=['']*self.config.size; self.key_source=''; self.result=None; self.stage=0; self.cursor=0; self.attempt_id=None; self.saved_snapshot=None; self.form_override=None; self.persist_failed=False; self.notice.setText(''); self.render()

    def open_saved(self,attempt_id):
        if self.active() and not confirm(self,'Abrir simulacro','Se sustituirá el borrador actual. El progreso no guardado en Mis simulacros se perderá. ¿Continuar?'): return False
        try:
            d=self.storage.load_attempt(attempt_id)
            if not d: raise ValueError('Simulacro no encontrado.')
            self.restore(d); self.storage.save_draft(d); self.render(); self.notice.setText('Simulacro guardado recuperado.'); return True
        except Exception as e: QMessageBox.warning(self,'No se pudo abrir',str(e)); return False

    def render(self):
        # Disable shortcuts immediately, including until deleteLater is processed.
        for sc in getattr(self,'shortcuts',[]): sc.setEnabled(False); sc.deleteLater()
        self.shortcuts=[]
        while self.body.count():
            it=self.body.takeAt(0); w=it.widget()
            if w: w.hide(); w.deleteLater()
        for i,x in enumerate(self.step_labels):
            x.setProperty('active',i==self.stage); x.setToolTip('Paso actual' if i==self.stage else 'Ir a '+x.text()); x.style().unpolish(x); x.style().polish(x)
        (self.show_config,self.show_key,self.show_answers,self.show_result)[self.stage]()

    def move_stage(self,stage):
        self.stage=stage; self.cursor=0; self.form_override=None; self.render(); self.persist()

    def navigate(self,target):
        if target==self.stage: return
        if self.stage==0:
            self.apply_config(target=target)
            return
        self.open_stage(target)

    def open_stage(self,target):
        if target>=2 and (not self.key_source or '' in self.key):
            self.move_stage(1)
            self.complete_key()
            return
        if target==3:
            if '' in self.answers:
                self.move_stage(2)
                self.notice.setText('Completa las respuestas o pulsa Corregir examen para confirmar las pendientes como blancas.')
                return
            try: self.result=evaluate(self.config,self.key,self.answers)
            except ValueError as e:
                QMessageBox.warning(self,'No se pudo corregir',str(e)); return
        self.move_stage(target)

    def show_config(self):
        p=panel(self.body); p.addWidget(label('Datos del examen','tileTitle'))
        p.addWidget(label('Nombre del simulacro')); self.name=QLineEdit(self.config.name); self.name.setMaxLength(120); p.addWidget(self.name)
        grid=QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(7)
        self.penalty=SafeComboBox(); self.penalty.setEditable(True)
        self.penalty.addItems(['0','1/4','1/3','1/2','1']); self.penalty.setCurrentText(self.config.penalty)
        self.maximum=QLineEdit(self.config.maximum); self.maximum.setMaxLength(24)
        for i,(title,widget) in enumerate((('Penalización por error',self.penalty),('Nota máxima',self.maximum))):
            col=i%2; row=(i//2)*2; grid.addWidget(label(title),row,col); grid.addWidget(widget,row+1,col)
        grid.setColumnStretch(0,1); grid.setColumnStretch(1,1); p.addLayout(grid)
        self.floor=QCheckBox('Limitar la nota mínima a 0'); self.floor.setChecked(self.config.floor_zero); p.addWidget(self.floor)
        if self.form_override:
            f=self.form_override; self.name.setText(f['name']); self.penalty.setCurrentText(f['penalty']); self.maximum.setText(f['maximum']); self.floor.setChecked(f['floor_zero'])
        if self.key_source:
            p.addWidget(label(f'Solucionario importado: {self.config.questions} preguntas · {self.config.reserves} reservas · {self.config.options} opciones por pregunta.','tileTitle',True))
        p.addWidget(label('Ágora detecta las preguntas y reservas al importar las soluciones. Confirma el número de opciones en la revisión del documento.','muted',True))
        p.addWidget(label('Cada acierto vale 1; cada error resta la penalización indicada; los blancos valen 0. Puedes usar una fracción (1/3) o un decimal (0,5). La penalización inicial es provisional: comprueba las reglas de tu examen.','muted',True))
        p.addWidget(label('Las anuladas se sustituyen por las reservas válidas en orden. Si no hay suficientes, se excluyen del total evaluable.','muted',True))
        t=panel(self.body); t.addWidget(label('Plantillas guardadas','tileTitle')); self.templates_combo=SafeComboBox(); t.addWidget(self.templates_combo)
        row=QHBoxLayout(); row.addWidget(btn('Consultar plantilla',self.view_template)); row.addWidget(btn('Cargar plantilla',self.load_template)); row.addWidget(btn('Eliminar plantilla',self.remove_template)); row.addStretch(); t.addLayout(row); self.refresh_templates()
        p2=panel(self.body,12); row=QHBoxLayout(); row.addWidget(btn('Nuevo / limpiar borrador',self.reset)); row.addStretch(); p2.addLayout(row); p2.addWidget(btn('Continuar a soluciones  ›',self.apply_config,'primary'))

    def refresh_templates(self):
        self.templates_combo.clear(); self.templates_combo.addItem('Selecciona una plantilla',None)
        try:
            self._template_items=self.storage.templates()
            for i,name,d in self._template_items: self.templates_combo.addItem(name,i)
        except Exception as e: self.notice.setText('No se pudieron cargar las plantillas: '+str(e))

    def view_template(self):
        tid=self.templates_combo.currentData()
        if tid is None:
            QMessageBox.information(self,'Plantillas guardadas','Selecciona primero una plantilla.'); return
        try:
            name,d=next((n,p) for i,n,p in self._template_items if i==tid)
            c=ExamConfig(**d['config']); k=list(d['key']); evaluate(c,k,['-']*c.size)
        except Exception as e:
            QMessageBox.warning(self,'Plantilla no válida',str(e)); return
        dialog=QDialog(self); dialog.setWindowTitle('Consultar plantilla'); dialog.resize(540,560)
        lay=QVBoxLayout(dialog); lay.addWidget(label(name,'heading',True))
        lay.addWidget(label(f'{c.questions} preguntas · {c.reserves} reservas · {c.options} opciones · Penalización: {c.penalty} · Nota máxima: {c.maximum}', 'muted',True))
        lay.addWidget(label('Solo lectura. Consultar no modifica el simulacro actual.','muted',True))
        table=QTableWidget(c.size,2); table.setHorizontalHeaderLabels(['Pregunta','Respuesta correcta']); table.verticalHeader().hide(); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); table.setAlternatingRowColors(True)
        for i,v in enumerate(k):
            for j,text in enumerate((c.number(i),'Anulada' if v=='X' else v)):
                item=QTableWidgetItem(text); item.setTextAlignment(ALIGN.AlignCenter); table.setItem(i,j,item)
        lay.addWidget(table,1); lay.addWidget(btn('Cerrar',dialog.accept,'primary')); dialog.exec()

    def load_template(self):
        tid=self.templates_combo.currentData()
        if tid is None: return
        if self.active():
            if not confirm(self,'Cargar plantilla','Se reemplazará el borrador actual, incluidas tus respuestas. ¿Continuar?'): return
        try:
            d=next(p for i,n,p in self._template_items if i==tid); c=ExamConfig(**d['config']); k=list(d['key'])
            evaluate(c,k,['-']*c.size)
        except Exception as e: QMessageBox.warning(self,'Plantilla no válida',str(e)); return
        self.attempt_id=None; self.saved_snapshot=None; self.config=c; self.key=k; self.key_source=d.get('key_source') or 'Plantilla guardada'; self.answers=['']*c.size; self.result=None; self.move_stage(1)

    def remove_template(self):
        tid=self.templates_combo.currentData()
        if tid is not None and confirm(self,'Eliminar plantilla','¿Eliminar la plantilla seleccionada? El borrador actual no se modifica.'):
            try: self.storage.delete_template(tid); self.refresh_templates()
            except Exception as e: QMessageBox.warning(self,'No se pudo eliminar',str(e))

    def reset(self):
        if not confirm(self,'Nuevo simulacro','Se borrará el borrador actual y sus cambios no guardados. Las plantillas y los simulacros guardados se conservarán. ¿Continuar?'): return
        self.start_new()

    def apply_config(self,checked=False,*,target=1):
        try: c=replace(self.config,name=self.name.text().strip(),penalty=self.penalty.currentText().strip().replace(',','.'),maximum=self.maximum.text().strip().replace(',','.'),floor_zero=self.floor.isChecked())
        except ValueError as e: QMessageBox.warning(self,'Revisa la configuración',str(e)); return
        if c!=self.config: self.result=None
        self.config=c; self.form_override=None; self.open_stage(target)

    def show_key(self):
        p=panel(self.body); p.addWidget(label('Soluciones correctas','tileTitle'))
        p.addWidget(label('Carga el solucionario en PDF o Word (.docx). Ágora extrae la numeración y las letras automáticamente.','muted',True))
        p.addWidget(btn('Importar documento de soluciones',self.import_key,'primary'))
        if self.key_source:
            p.addWidget(label('Origen: '+self.key_source,'muted',True)); self.show_entry(True)
        else:
            p.addWidget(label('Todavía no hay un solucionario importado. No necesitas escribirlo a mano.','muted',True))
    def import_key(self):
        dialog=ImportDialog(self)
        if dialog.exec()!=QDialog.DialogCode.Accepted or not dialog.item: return
        name,data=dialog.item
        try: imported=extract_key(data,name)
        except Exception as e:
            QMessageBox.warning(self,'No se pudo leer el solucionario',str(e)); return
        self.review_import(imported,name)
    def review_import(self,imported,name):
        # Do not infer an exact option count from the highest letter alone.
        dlg=QDialog(self); dlg.setWindowTitle('Revisar soluciones detectadas'); dlg.resize(640,620); lay=QVBoxLayout(dlg)
        lay.addWidget(label(name,'heading',True)); lay.addWidget(label(f'{len(imported.ordinary)} preguntas · {len(imported.reserves)} reservas · {len(imported.key)} soluciones detectadas.','tileTitle',True))
        lay.addWidget(label('Comprueba el total y las letras con el documento original. Si el archivo está incompleto al final, Ágora no puede deducir cuántas preguntas faltan.','muted',True))
        options=SafeSpinBox(); options.setRange(imported.options,5); options.setValue(max(self.config.options,imported.options)); row=QHBoxLayout(); row.addWidget(label('Opciones por pregunta')); row.addWidget(options); lay.addLayout(row)
        lay.addWidget(label('Confirma cuántas opciones tenía el examen. La letra más alta detectada solo indica el mínimo; puede haber opciones que nunca sean correctas.','muted',True))
        table=QTableWidget(len(imported.key),2); table.setHorizontalHeaderLabels(['Pregunta','Solución detectada']); table.verticalHeader().hide(); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); table.setAlternatingRowColors(True)
        for i,v in enumerate(imported.key):
            number=str(i+1) if i<len(imported.ordinary) else 'R'+str(i-len(imported.ordinary)+1)
            for j,value in enumerate((number,'Anulada' if v=='X' else v)):
                item=QTableWidgetItem(value); item.setTextAlignment(ALIGN.AlignCenter); table.setItem(i,j,item)
        lay.addWidget(table,1); row=QHBoxLayout(); row.addWidget(btn('Cancelar',dlg.reject)); row.addWidget(btn('Confirmar e importar',dlg.accept,'primary')); lay.addLayout(row)
        if dlg.exec()!=QDialog.DialogCode.Accepted: return
        c=replace(self.config,questions=len(imported.ordinary),reserves=len(imported.reserves),options=options.value())
        changed=(c.questions,c.reserves,c.options)!=(self.config.questions,self.config.reserves,self.config.options)
        if any(self.answers) and (changed or imported.key!=self.key):
            if not confirm(self,'Sustituir solucionario','Se borrarán tus respuestas actuales para evitar mezclarlas con otro examen. ¿Continuar?'): return
            self.answers=['']*c.size
        elif changed: self.answers=['']*c.size
        self.install_key(imported,name,c.options)
    def install_key(self,imported,name,options):
        # Internal operation, after preview/confirmation.
        c=replace(self.config,questions=len(imported.ordinary),reserves=len(imported.reserves),options=options)
        if c.size!=len(self.answers): self.answers=['']*c.size
        self.config=c; self.key=imported.key; self.key_source=name; self.result=None; self.move_stage(1)
    def show_answers(self): self.show_entry(False)
    def show_entry(self,is_key):
        self.is_key=is_key; self.values=self.key if is_key else self.answers
        p=panel(self.body); p.addWidget(label(self.config.name,'tileTitle',True)); p.addWidget(label(('Revisa las soluciones detectadas; puedes corregir una incidencia puntual.' if is_key else 'Marca tu respuesta original o «—» si la dejaste en blanco.')+' Puedes escribir con el teclado; Ágora avanza a la siguiente pregunta.','muted',True))
        self.progress=label('','tileTitle'); p.addWidget(self.progress)
        nav=QHBoxLayout(); nav.addWidget(btn('‹ Anterior',lambda:self.change_page(-1))); self.range_label=label(''); nav.addWidget(self.range_label,1); nav.addWidget(btn('Siguiente ›',lambda:self.change_page(1))); p.addLayout(nav)
        self.entries=QWidget(); self.entries_grid=QGridLayout(self.entries); self.entries_grid.setContentsMargins(0,0,0,0); self.entries_grid.setHorizontalSpacing(10); self.entries_grid.setVerticalSpacing(5); p.addWidget(self.entries)
        self.grid_rows=[]
        # Two columns of eight rows; compact enough at common desktop resolutions.
        for i in range(16):
            holder=QWidget(); h=QHBoxLayout(holder); h.setContentsMargins(1,1,1,1); h.setSpacing(2)
            num=btn('',lambda checked=False,j=i:self.select_slot(j)); num.setObjectName('manualNumber'); num.setFixedWidth(42); h.addWidget(num)
            choices=[]
            for val in (*self.config.letters,('X' if is_key else '-')):
                b=btn('—' if val=='-' else val,lambda checked=False,j=i,v=val:self.choose_slot(j,v)); b.setObjectName('manualChoice'); b.setCheckable(True); b.setMinimumWidth(24); b.setToolTip('Anulada' if val=='X' else 'En blanco' if val=='-' else 'Opción '+val); h.addWidget(b,1); choices.append((val,b))
            clear=btn('×',lambda checked=False,j=i:self.clear_slot(j)); clear.setObjectName('manualClear'); clear.setFixedWidth(24); clear.setToolTip('Borrar (dejar pendiente)'); h.addWidget(clear)
            self.entries_grid.addWidget(holder,i%8,i//8); self.grid_rows.append((holder,num,choices,clear))
        self.entries_grid.setColumnStretch(0,1); self.entries_grid.setColumnStretch(1,1)
        row=QHBoxLayout(); row.addWidget(btn('‹ Configuración' if is_key else '‹ Soluciones',lambda:self.move_stage(0 if is_key else 1))); row.addStretch()
        if is_key: row.addWidget(btn('Guardar plantilla de respuestas',self.save_template))
        else: row.addWidget(btn('Pendientes → blanco',self.fill_blanks))
        p.addLayout(row); p.addWidget(btn('Continuar a respuestas ›' if is_key else 'Corregir examen',self.next_entry,'primary'))
        p.addWidget(label('Teclado: '+self.config.letters+' · '+('X: anulada' if is_key else 'Guion (-): en blanco')+' · Retroceso: borrar · ↑/↓: cambiar pregunta. R = reserva.','muted',True))
        for char in (*self.config.letters,('X' if is_key else '-')): self.shortcut(char,lambda v=char:self.choose(self.cursor,v))
        self.shortcut('Backspace',lambda:self.clear(self.cursor)); self.shortcut('Up',lambda:self.select(self.cursor-1)); self.shortcut('Down',lambda:self.select(self.cursor+1)); self.refresh_entries()

    def shortcut(self,key,fn):
        sc=QShortcut(QKeySequence(key),self); sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); sc.activated.connect(fn); self.shortcuts.append(sc)

    def refresh_entries(self):
        start=(self.cursor//16)*16; end=min(start+16,self.config.size); count=sum(v!='' for v in self.values)
        self.progress.setText(f'{count} de {self.config.size} '+('soluciones registradas' if self.is_key else 'respuestas registradas')+f'  ·  {self.config.size-count} pendientes')
        self.range_label.setText(f'{self.config.number(start)} – {self.config.number(end-1)}  ·  Selección: {self.config.number(self.cursor)}')
        for j,(holder,num,choices,clear) in enumerate(self.grid_rows):
            i=start+j; holder.setVisible(i<end)
            if i>=end: continue
            num.setText(self.config.number(i)); num.setProperty('selected',i==self.cursor); num.style().unpolish(num); num.style().polish(num)
            for value,b in choices: b.setChecked(self.values[i]==value)
            clear.setEnabled(bool(self.values[i]))
        # Set focus inside page when coming from a navigation button, enabling keyboard entry.
        focused=QApplication.focusWidget()
        if focused is None or not self.isAncestorOf(focused) or not focused.isVisible(): self.focus_entry()

    def focus_entry(self):
        if self.stage in (1,2) and (self.stage==2 or self.key_source) and self.isVisible(): self.grid_rows[self.cursor%16][1].setFocus()

    def select(self,i): self.cursor=max(0,min(i,self.config.size-1)); self.refresh_entries()
    def select_slot(self,j): self.select((self.cursor//16)*16+j)
    def change_page(self,d):
        target=((self.cursor//16)+d)*16
        if 0<=target<self.config.size: self.select(target)
    def choose_slot(self,j,v): self.choose((self.cursor//16)*16+j,v)
    def clear_slot(self,j): self.clear((self.cursor//16)*16+j)
    def choose(self,i,v):
        if not 0<=i<self.config.size: return
        self.result=None; self.values[i]=v; self.cursor=min(i+1,self.config.size-1); self.persist(); self.refresh_entries()
    def clear(self,i):
        if not 0<=i<self.config.size: return
        self.result=None; self.values[i]=''; self.cursor=i; self.persist(); self.refresh_entries()
    def complete_key(self):
        if not self.key_source:
            self.notice.setText('Importa primero el documento de soluciones desde ordenador o móvil.'); return False
        if '' in self.key:
            QMessageBox.warning(self,'Soluciones pendientes','Completa todas las soluciones, incluidas las reservas configuradas, o marca X si están anuladas.'); self.select(self.key.index('')); return False
        return True
    def save_template(self):
        if not self.complete_key(): return
        dialog=QInputDialog(self); dialog.setWindowTitle('Guardar plantilla de respuestas'); dialog.setLabelText('Nombre de la plantilla:'); dialog.setTextValue(self.config.name); dialog.setOkButtonText('Guardar'); dialog.setCancelButtonText('Cancelar'); ok=dialog.exec()==QDialog.DialogCode.Accepted; name=dialog.textValue()
        if not ok or not name.strip(): return
        if len(name.strip())>120: QMessageBox.warning(self,'Nombre demasiado largo','Usa como máximo 120 caracteres.'); return
        try: self.storage.save_template(name.strip(),{'config':asdict(self.config),'key':self.key,'key_source':self.key_source}); self.notice.setText('Plantilla guardada: '+name.strip())
        except Exception as e: QMessageBox.warning(self,'No se pudo guardar',str(e))
    def fill_blanks(self):
        n=self.answers.count('')
        if n and confirm(self,'Respuestas pendientes',f'¿Marcar las {n} respuestas pendientes como en blanco?'):
            self.result=None; self.answers[:]=[v or '-' for v in self.answers]; self.persist(); self.refresh_entries()
    def next_entry(self):
        if self.is_key:
            if self.complete_key(): self.move_stage(2)
        else:
            if '' in self.answers:
                n=self.answers.count('')
                if not confirm(self,'Respuestas pendientes',f'Quedan {n} sin registrar. ¿Contarlas como respuestas en blanco?'): return
                self.answers[:]=[v or '-' for v in self.answers]
            try: self.result=evaluate(self.config,self.key,self.answers)
            except ValueError as e: QMessageBox.warning(self,'No se pudo corregir',str(e)); return
            self.move_stage(3)

    def show_result(self):
        r=self.result or evaluate(self.config,self.key,self.answers); self.result=r
        p=panel(self.body); p.addWidget(label(self.config.name,'tileTitle',True)); p.addWidget(label(f'{format_number(r.grade)} / {format_number(self.config.maximum)}','headline'))
        if r.grade is None: p.addWidget(label('No hay preguntas evaluables. No se puede calcular una nota.','muted',True))
        grid=QGridLayout()
        for i,(name,value,role) in enumerate((('Aciertos',r.correct,'correct'),('Errores',r.wrong,'wrong'),('En blanco',r.blank,'neutral'),('Anuladas ordinarias',r.annulled,'neutral'),('Reservas utilizadas',r.reserve_used,'neutral'),('Evaluables',r.effective,'neutral'))):
            box=QFrame(); box.setObjectName('manualMetric'); l=QVBoxLayout(box); l.addWidget(label(str(value),role)); l.addWidget(label(name,'muted',True)); grid.addWidget(box,i//3,i%3)
        p.addLayout(grid)
        p.addWidget(label(f'Puntuación neta: {format_number(r.net)} · Penalización: {self.config.penalty} por error. Nota = puntuación neta × nota máxima / preguntas evaluables.','muted',True))
        if r.raw_grade!=r.grade: p.addWidget(label('Nota sin límite mínimo: '+format_number(r.raw_grade),'muted'))
        if r.annulled>r.reserve_used: p.addWidget(label(f'{r.annulled-r.reserve_used} anuladas sin reserva válida: excluidas del denominador.','muted',True))
        t=panel(self.body); t.addWidget(label('Detalle de preguntas','tileTitle')); self.filter=SafeComboBox(); self.filter.addItems(['Todas','Aciertos','Errores','En blanco','Anuladas','Reservas']); t.addWidget(self.filter)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(['Pregunta','Solución','Tu respuesta','Resultado','Sustituye a']); self.table.verticalHeader().hide(); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); self.table.setMinimumHeight(270); self.table.setAlternatingRowColors(True); t.addWidget(self.table); self.filter.currentIndexChanged.connect(self.populate_table); self.populate_table()
        row=QHBoxLayout(); row.addWidget(btn('‹ Editar respuestas',lambda:self.move_stage(2))); row.addWidget(btn('Editar soluciones',lambda:self.move_stage(1))); row.addStretch(); row.addWidget(btn('Nuevo simulacro',self.reset,'primary')); t.addLayout(row)
        t.addWidget(label('Pulsa Guardar progreso para conservar este resultado en Mis simulacros.','muted',True))

    def populate_table(self,*_):
        idx=self.filter.currentIndex(); rows=[r for r in self.result.rows if idx==0 or idx==1 and r.status=='Acierto' or idx==2 and r.status=='Error' or idx==3 and r.status=='En blanco' or idx==4 and 'anulada' in r.status.lower() or idx==5 and r.number.startswith('R')]
        self.table.setRowCount(len(rows))
        from PySide6.QtGui import QColor,QBrush
        for i,r in enumerate(rows):
            for j,v in enumerate((r.number,'—' if r.solution=='X' else r.solution,'—' if r.answer=='-' else r.answer,r.status,r.replaces or '—')):
                x=QTableWidgetItem(v); x.setTextAlignment(ALIGN.AlignCenter)
                if j==3 and r.status in ('Acierto','Error'): x.setForeground(QBrush(QColor('#30764D' if r.status=='Acierto' else '#A13952')))
                self.table.setItem(i,j,x)
