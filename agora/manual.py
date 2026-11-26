"""Manual correction wizard; import a solution key, then enter personal answers."""
from pathlib import Path
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
    def __init__(self, storage, go_home, mode="manual"):
        super().__init__(); self.mode=mode; self.storage=storage; self.optical_cache={}; self.config=ExamConfig(); self.key=['']*self.config.size; self.answers=['']*self.config.size
        self.key_source=''; self.document_ref=None; self.template_id=None; self.stage=0; self.cursor=0; self.result=None; self._template_items=[]; self.persist_failed=False; self.attempt_id=None; self.saved_snapshot=None; self.form_override=None; self.expected_counts=None
        self.root=QVBoxLayout(self); self.root.setContentsMargins(0,0,0,0); self.root.setSpacing(10)
        top=QHBoxLayout(); top.addWidget(btn('‹  Volver al inicio',go_home)); top.addWidget(btn('Guardar progreso',self.save_progress,'primary')); top.addStretch(); self.root.addLayout(top)
        self.root.addWidget(label('Corrector automático' if mode=='automatic' else 'Corrector manual','heading'))
        self.steps=QHBoxLayout(); self.step_labels=[]
        for i,s in enumerate(('1 · Configuración','2 · Soluciones','3 · Respuestas','4 · Resultado')):
            x=btn(s,lambda checked=False,j=i:self.navigate(j),'manualStep'); x.setAccessibleName(s); self.steps.addWidget(x,1); self.step_labels.append(x)
        self.root.addLayout(self.steps)
        self.notice=label('','muted',True); self.root.addWidget(self.notice)
        self.content=QWidget(); self.body=QVBoxLayout(self.content); self.body.setContentsMargins(0,0,0,0); self.body.setSpacing(10); self.root.addWidget(self.content); self.root.addStretch()
        self.render()

    def restore(self,d):
        c=ExamConfig(**d['config']); k=list(d['key']); a=list(d['answers']); stage=d.get('stage',0); cursor=d.get('cursor',0)
        if len(k)!=c.size or len(a)!=c.size or any(v not in (*c.letters,'X','') for v in k) or any(v not in (*c.letters,'-','') for v in a): raise ValueError('Borrador no válido')
        cache={}
        if self.mode=='automatic' and d.get('optical_pages'):
            from .optical_archive import unpack
            for slot,ref in d['optical_pages'].items():
                i=int(slot)
                if not 0<=i<100: raise ValueError('Página guardada no válida.')
                record=self.storage.load_optical_page(ref); original,aligned,marks=unpack(record,i)
                for kind,val in (('images',original),('aligned',aligned),('marks',marks),('records',record)):
                    cache.setdefault(kind,{})[i]=val
        self.optical_cache.clear(); self.optical_cache.update(cache); self.template_id=d.get('template_id'); self.template_id=self.template_id if any(i==self.template_id for i,_,_ in self.storage.templates()) else None; self.document_ref=d.get('document_ref')
        self.expected_counts=tuple(d['expected_counts']) if d.get('expected_counts') else None
        self.config=c; self.key=k; self.answers=a; self.key_source=d.get('key_source') or ('Plantilla anterior' if all(k) else ''); self.stage=stage if stage in (0,1,2,3) else 0; self.cursor=max(0,min(int(cursor),c.size-1)); self.result=None
        self.attempt_id=d.get('attempt_id'); self.saved_snapshot=self.storage.load_attempt(self.attempt_id) if self.attempt_id is not None else None
        self.form_override=d.get('form') if self.stage==0 else None
        if self.form_override is not None:
            self.form_override=dict(self.form_override,options=c.options)
            if self.form_override==dict(asdict(c),questions=(self.expected_counts or (c.questions,c.reserves))[0],reserves=(self.expected_counts or (c.questions,c.reserves))[1]): self.form_override=None
        if self.stage>=2 and (not self.key_source or '' in self.key): self.stage=1
        if self.stage==3 and '' in self.answers: self.stage=2
        if (self.stage==3 or d.get('corrected')) and self.key_source and all(k) and all(a): self.result=evaluate(c,k,a)

    def form_data(self):
        return {'name':self.name.text(),'questions':self.question_count.value(),'reserves':self.reserve_count.value(),'options':self.config.options,'penalty':self.penalty.currentText(),'maximum':self.maximum.text(),'floor_zero':self.floor.isChecked()}

    def payload(self,read_form=False):
        d={'mode':self.mode,'config':asdict(self.config),'key':list(self.key),'answers':list(self.answers),'stage':self.stage,'cursor':self.cursor,'key_source':self.key_source,'attempt_id':self.attempt_id,'corrected':self.result is not None}
        if self.expected_counts is not None: d['expected_counts']=list(self.expected_counts)
        if self.template_id is not None: d['template_id']=self.template_id
        if self.document_ref is not None: d['document_ref']=self.document_ref
        if self.optical_cache.get('records'): d['optical_pages']={str(i):r[0] for i,r in self.optical_cache['records'].items()}
        form=self.form_data() if read_form and self.stage==0 and hasattr(self,'name') else self.form_override if self.stage==0 else None
        if form is not None and form!=dict(d['config'],questions=(self.expected_counts or (self.config.questions,self.config.reserves))[0],reserves=(self.expected_counts or (self.config.questions,self.config.reserves))[1]): d['form']=dict(form)
        return d

    @staticmethod
    def comparable(d):
        if not d: return None
        return {**{k:d.get(k) for k in ('config','key','answers','key_source','form','document_ref','template_id','expected_counts')},'optical_pages':d.get('optical_pages',{}),'corrected':bool(d.get('corrected',d.get('stage')==3))}

    def active(self):
        d=self.payload(True)
        return self.attempt_id is not None or any(self.key) or any(self.answers) or self.config!=ExamConfig() or (self.expected_counts is not None and self.expected_counts!=(ExamConfig().questions,ExamConfig().reserves)) or bool(d.get('form'))

    def dirty(self):
        return self.active() and self.comparable(self.payload(True))!=self.comparable(self.saved_snapshot)

    def persist(self,read_form=False):
        try:
            self.storage.save_draft(self.payload(read_form),self.mode,self.optical_cache.get('records',{}).values()); self.persist_failed=False
            self.notice.setText('Cambios sin guardar' if self.dirty() else 'Sin cambios pendientes')
            return True
        except Exception as e:
            self.persist_failed=True; self.notice.setText('No se pudo guardar el borrador: '+str(e)); return False

    def save_progress(self, *_):
        if not self.active():
            QMessageBox.information(self,'Guardar progreso','Configura un simulacro antes de guardarlo.'); return False
        try:
            d=self.payload(True); self.attempt_id=self.storage.save_attempt(d,self.attempt_id,self.optical_cache.get('records',{}).values()); self.saved_snapshot=dict(d,attempt_id=self.attempt_id)
            self.persist_failed=False; self.notice.setText('Progreso guardado en Mis simulacros.'); return True
        except Exception as e:
            QMessageBox.warning(self,'No se pudo guardar',str(e)); return False

    def allow_leave(self):
        if self.dirty():
            box=QMessageBox(self); box.setWindowTitle('Cambios sin guardar'); box.setText('No has guardado el progreso en Mis simulacros. ¿Qué quieres hacer?'); box.setInformativeText('Si sales sin guardar, perderás los cambios desde el último guardado.'); box.setIcon(QMessageBox.Icon.Question)
            save=box.addButton('Guardar y salir',QMessageBox.ButtonRole.AcceptRole); leave=box.addButton('Salir sin guardar',QMessageBox.ButtonRole.DestructiveRole); cancel=box.addButton('Cancelar',QMessageBox.ButtonRole.RejectRole); box.setDefaultButton(save); box.setEscapeButton(cancel); box.exec()
            if box.clickedButton() is save:
                if not self.save_progress(): return False
            elif box.clickedButton() is not leave: return False
        return self.start_new()

    def allow_enter(self):
        # Only Mis simulacros can reopen archived work. A normal entry is always new.
        return self.start_new()

    def start_new(self):
        try: self.storage.clear_draft(self.mode)
        except Exception as e: QMessageBox.warning(self,'No se pudo iniciar',str(e)); return False
        self.reset_state(); return True

    def reset_state(self):
        # In-memory reset only: caller handles database changes atomically.
        self.optical_cache.clear(); self.config=ExamConfig(); self.key=['']*self.config.size; self.answers=['']*self.config.size; self.key_source=''; self.document_ref=None; self.template_id=None; self.result=None; self.stage=0; self.cursor=0; self.attempt_id=None; self.saved_snapshot=None; self.form_override=None; self.expected_counts=None; self.persist_failed=False; self.notice.setText(''); self.render()

    def open_saved(self,attempt_id):
        if self.active() and not confirm(self,'Abrir simulacro','Se sustituirá el borrador actual. El progreso no guardado en Mis simulacros se perderá. ¿Continuar?'): return False
        try:
            d=self.storage.load_attempt(attempt_id)
            if not d: raise ValueError('Simulacro no encontrado.')
            self.restore(d); self.storage.save_draft(d,self.mode); self.render(); self.notice.setText('Simulacro guardado recuperado.'); return True
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
            if not self.check_counts(): return
            candidate=list(self.answers); confirmed_reserves=False
            if self.mode=='automatic' and '' not in candidate[:self.config.questions] and '' in candidate[self.config.questions:]:
                from .grading import missing_reserves_message
                message=missing_reserves_message(self.config,self.key,candidate)
                if not confirm(self,'Reservas pendientes',message+'\nComprueba también las marcas azules y la alineación.'): return
                candidate=[v or '-' for v in candidate]; confirmed_reserves=True
            if '' in candidate:
                self.move_stage(2)
                self.notice.setText('Hay preguntas ordinarias pendientes. Revisa las lecturas o carga las hojas que falten.' if self.mode=='automatic' else 'Completa las respuestas o pulsa Corregir examen para confirmar las pendientes como blancas.')
                return
            if self.mode=='automatic' and self.result is None and not confirmed_reserves and not confirm(self,'Confirmar lectura','Comprueba que la hoja estaba marcada en azul y que la alineación y las respuestas propuestas son correctas. ¿Calcular la nota?'): return
            try: result=evaluate(self.config,self.key,candidate)
            except ValueError as e:
                QMessageBox.warning(self,'No se pudo corregir',str(e)); return
            self.answers[:]=candidate; self.result=result
        self.move_stage(target)

    def check_counts(self):
        actual=(self.config.questions,self.config.reserves)
        if self.expected_counts is None or self.expected_counts==actual: return True
        q,r=self.expected_counts
        if not confirm(self,'Número de preguntas',f'Configuración: {q} ordinarias y {r} reservas.\nSolucionario: {actual[0]} ordinarias y {actual[1]} reservas.\n¿Corregir usando las cantidades del solucionario? Si no, vuelve a Configuración o importa el solucionario correcto.'): return False
        self.expected_counts=actual
        return True

    def key_summary_text(self):
        return f'Solucionario: {self.config.questions} preguntas · {self.config.reserves} reservas · {self.config.options} opciones'

    def show_config(self):
        p=panel(self.body); p.addWidget(label('Datos del examen','tileTitle'))
        p.addWidget(label('Nombre del simulacro')); self.name=QLineEdit(self.config.name); self.name.setMaxLength(120); p.addWidget(self.name)
        grid=QGridLayout(); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(7)
        self.penalty=SafeComboBox(); self.penalty.setEditable(True)
        self.penalty.addItems(['0','1/4','1/3','1/2','1']); self.penalty.setCurrentText(self.config.penalty)
        self.maximum=QLineEdit(self.config.maximum); self.maximum.setMaxLength(24)
        self.question_count=SafeSpinBox(); self.question_count.setRange(1,500); self.reserve_count=SafeSpinBox(); self.reserve_count.setRange(0,100)
        q,r=self.expected_counts or (self.config.questions,self.config.reserves); self.question_count.setValue(q); self.reserve_count.setValue(r)
        for i,(title,widget) in enumerate((('Preguntas ordinarias',self.question_count),('Preguntas de reserva',self.reserve_count),('Penalización por error',self.penalty),('Nota máxima',self.maximum))):
            col=i%2; row=(i//2)*2; grid.addWidget(label(title),row,col); grid.addWidget(widget,row+1,col)
        grid.setColumnStretch(0,1); grid.setColumnStretch(1,1); p.addLayout(grid)
        self.floor=QCheckBox('Limitar la nota mínima a 0'); self.floor.setChecked(self.config.floor_zero); p.addWidget(self.floor)
        if self.form_override:
            f=self.form_override; self.name.setText(f['name']); self.penalty.setCurrentText(f['penalty']); self.maximum.setText(f['maximum']); self.floor.setChecked(f['floor_zero']); self.question_count.setValue(f.get('questions',q)); self.reserve_count.setValue(f.get('reserves',r))
        self.key_summary=label(self.key_summary_text(),'tileTitle',True); p.addWidget(self.key_summary); self.key_summary.setVisible(bool(self.key_source))
        t=panel(self.body); t.addWidget(label('Plantillas guardadas','tileTitle')); self.templates_combo=SafeComboBox(); t.addWidget(self.templates_combo)
        row=QHBoxLayout(); row.addWidget(btn('Consultar plantilla',self.view_template)); self.use_template_button=btn('Usar plantilla',self.load_template); row.addWidget(self.use_template_button); self.use_template_button.hide(); row.addWidget(btn('Eliminar plantilla',self.remove_template)); row.addWidget(btn('Quitar plantilla',self.clear_template)); row.addStretch(); t.addLayout(row); self.refresh_templates(); self.templates_combo.activated.connect(self.template_selected)
        p2=panel(self.body,12); row=QHBoxLayout(); row.addWidget(btn('Nuevo / limpiar borrador',self.reset)); row.addStretch(); p2.addLayout(row); p2.addWidget(btn('Continuar a soluciones  ›',self.apply_config,'primary'))

    def refresh_templates(self):
        previous=self.templates_combo.blockSignals(True)
        try:
            self.templates_combo.clear(); self.templates_combo.addItem('Selecciona una plantilla',None)
            self._template_items=self.storage.templates()
            for i,name,d in self._template_items: self.templates_combo.addItem(name,i)
            idx=self.templates_combo.findData(self.template_id)
            if idx>=0: self.templates_combo.setCurrentIndex(idx)
        except Exception as e: self.notice.setText('No se pudieron cargar las plantillas: '+str(e))
        finally: self.templates_combo.blockSignals(previous)
        self.update_template_action()

    def update_template_action(self):
        tid=self.templates_combo.currentData()
        self.use_template_button.setVisible(tid is not None and tid!=self.template_id)

    def template_selected(self,*_):
        tid=self.templates_combo.currentData()
        if tid is None or tid==self.template_id:
            self.update_template_action(); return
        # Selection alone must not overwrite an existing exam or its name.
        if not self.active(): self.load_template()
        self.update_template_action()

    def view_template(self):
        tid=self.templates_combo.currentData()
        if tid is None:
            QMessageBox.information(self,'Plantillas guardadas','Selecciona primero una plantilla.'); return
        from .library_ui import consult_template
        try:
            name,d=next((n,p) for i,n,p in self._template_items if i==tid)
            consult_template(self,self.storage,name,d)
        except Exception as e: QMessageBox.warning(self,'Plantilla no válida',str(e))

    def load_template(self):
        tid=self.templates_combo.currentData()
        if tid is None: return False
        if tid==self.template_id: return True
        try:
            d=next(p for i,n,p in self._template_items if i==tid); c=ExamConfig(**d['config']); k=list(d['key'])
            evaluate(c,k,['-']*c.size)
        except Exception as e: QMessageBox.warning(self,'Plantilla no válida',str(e)); return False
        if self.active() and not confirm(self,'Cargar plantilla','Se reemplazará el borrador actual, incluidas tus respuestas. ¿Continuar? Si eliges No, podrás consultar o eliminar la plantilla sin cargarla.'):
            self.notice.setText('Plantilla seleccionada, no cargada'); return False
        # Stay in configuration so Consultar / Eliminar remain accessible.
        self.optical_cache.clear(); self.template_id=tid; self.document_ref=d.get('document_ref'); self.attempt_id=None; self.saved_snapshot=None; self.config=c; self.key=k; self.key_source=d.get('key_source') or 'Plantilla guardada'; self.answers=['']*c.size; self.result=None; self.cursor=0; self.form_override=None
        self.expected_counts=(c.questions,c.reserves); self.question_count.setValue(c.questions); self.reserve_count.setValue(c.reserves)
        self.name.setText(c.name); self.penalty.setCurrentText(c.penalty); self.maximum.setText(c.maximum); self.floor.setChecked(c.floor_zero)
        self.key_summary.setText(self.key_summary_text()); self.key_summary.show()
        self.persist(True)
        if not self.persist_failed: self.notice.setText('Plantilla cargada')
        self.update_template_action(); return True

    def clear_template(self):
        # Deselect a merely highlighted template without touching an unrelated imported key.
        if self.templates_combo.currentData() != self.template_id and self.templates_combo.currentData() is not None:
            self.templates_combo.setCurrentIndex(max(0,self.templates_combo.findData(self.template_id))); self.update_template_action(); return True
        if self.template_id is None and not self.key_source:
            self.templates_combo.setCurrentIndex(0); self.update_template_action(); return True
        if self.template_id is None and self.templates_combo.currentData() is not None:
            self.templates_combo.setCurrentIndex(0); self.update_template_action(); return True
        # Older versions did not retain the template ID; allow explicitly clearing their key too.
        if not confirm(self,'Quitar plantilla','Se quitará el solucionario actual y las respuestas del borrador. Los simulacros y plantillas guardados no se borrarán. ¿Continuar?'):
            idx=self.templates_combo.findData(self.template_id)
            if idx>=0: self.templates_combo.setCurrentIndex(idx)
            return False
        self.form_override=self.form_data()
        self.expected_counts=None
        self.config=replace(self.config,questions=ExamConfig().questions,reserves=ExamConfig().reserves,options=ExamConfig().options)
        self.key=['']*self.config.size; self.answers=['']*self.config.size
        self.key_source=''; self.document_ref=None; self.template_id=None; self.result=None; self.cursor=0
        self.optical_cache.clear(); self.attempt_id=None; self.saved_snapshot=None
        self.templates_combo.setCurrentIndex(0); self.update_template_action(); self.key_summary.hide(); self.persist(True)
        return True

    def remove_template(self):
        tid=self.templates_combo.currentData()
        if tid is None: return
        from .template_ui import delete_named_template
        try:
            active=self.template_id==tid or self.attempt_id in {i for i,_ in self.storage.template_attempts(tid)}
            if delete_named_template(self,self.storage,tid,active):
                if active: self.reset_state()
                else: self.refresh_templates()
        except Exception as e: QMessageBox.warning(self,'No se pudo eliminar',str(e))

    def reset(self):
        if not confirm(self,'Nuevo simulacro','Se borrará el borrador actual y sus cambios no guardados. Las plantillas y los simulacros guardados se conservarán. ¿Continuar?'): return
        self.start_new()

    def apply_config(self,checked=False,*,target=1):
        try: c=replace(self.config,name=self.name.text().strip(),penalty=self.penalty.currentText().strip().replace(',','.'),maximum=self.maximum.text().strip().replace(',','.'),floor_zero=self.floor.isChecked())
        except ValueError as e: QMessageBox.warning(self,'Revisa la configuración',str(e)); return
        counts=(self.question_count.value(),self.reserve_count.value())
        self.expected_counts=counts
        if c!=self.config or (self.expected_counts is not None and self.expected_counts!=(c.questions,c.reserves)): self.result=None
        self.config=c; self.form_override=None; self.open_stage(target)

    def show_key(self):
        p=panel(self.body); p.addWidget(label('Soluciones correctas','tileTitle'))
        p.addWidget(btn('Importar documento de soluciones',self.import_key,'primary'))
        if self.key_source:
            p.addWidget(label('Origen: '+self.key_source,'muted',True))
            actions=QHBoxLayout()
            if self.document_ref: actions.addWidget(btn('Consultar documento original',self.view_original,'softAction'))
            actions.addWidget(btn('Guardar plantilla',self.save_template,'softAction')); actions.addStretch(); p.addLayout(actions)
            self.show_entry(True)
    def view_original(self):
        if self.document_ref:
            from .library_ui import consult_document
            consult_document(self,self.storage,self.document_ref)

    def import_key(self):
        dialog=ImportDialog(self)
        if dialog.exec()!=QDialog.DialogCode.Accepted or not dialog.item: return
        name,data=dialog.item
        try: imported=extract_key(data,name)
        except Exception as e:
            QMessageBox.warning(self,'No se pudo leer el solucionario',str(e)); return
        self.review_import(imported,name,data)
    def review_import(self,imported,name,data=None):
        from .template_ui import review_key
        options=review_key(self,imported,name,self.config.options)
        if options is None: return
        c=replace(self.config,questions=len(imported.ordinary),reserves=len(imported.reserves),options=options)
        expected=self.expected_counts or (self.config.questions,self.config.reserves)
        if expected!=(c.questions,c.reserves):
            q,r=expected
            if not confirm(self,'Revisar cantidades',f'Configuración: {q} preguntas y {r} reservas. Solucionario: {c.questions} preguntas y {c.reserves} reservas. ¿Importar igualmente?'): return
        changed=(c.questions,c.reserves,c.options)!=(self.config.questions,self.config.reserves,self.config.options)
        if any(self.answers) and (changed or imported.key!=self.key):
            if not confirm(self,'Sustituir solucionario','Se borrarán tus respuestas actuales para evitar mezclarlas con otro examen. ¿Continuar?'): return
        try: ref=self.storage.archive_solution_document(name,data) if data is not None else None
        except Exception as e: QMessageBox.warning(self,'No se pudo conservar el documento',str(e)); return
        if changed or (any(self.answers) and imported.key!=self.key): self.answers=['']*c.size
        self.expected_counts=expected
        self.install_key(imported,name,c.options,document_ref=ref,preserve_expected=True)
    def install_key(self,imported,name,options,document_ref=None,preserve_expected=False):
        # Internal operation, after preview/confirmation.
        c=replace(self.config,questions=len(imported.ordinary),reserves=len(imported.reserves),options=options)
        if c.size!=len(self.answers): self.answers=['']*c.size
        if c.size!=self.config.size or (c.questions,c.reserves,c.options)!=(self.config.questions,self.config.reserves,self.config.options) or list(imported.key)!=list(self.key): self.optical_cache.clear()
        if not preserve_expected: self.expected_counts=(c.questions,c.reserves)
        self.template_id=None; self.document_ref=document_ref; self.config=c; self.key=imported.key; self.key_source=name; self.result=None; self.move_stage(1)
    def show_answers(self):
        if self.mode=='manual': self.show_entry(False); return
        from .omr_ui import OpticalPage
        self.reader=OpticalPage(self.config,self.answers,self.optical_cache,self.optical_changed)
        self.body.addWidget(self.reader)
        bar=QWidget(); actions=QHBoxLayout(bar); actions.setContentsMargins(0,0,0,0); actions.addWidget(btn('Reiniciar lectura',self.reader.reset)); actions.addStretch(); actions.addWidget(btn('Corregir examen',self.correct_optical,'primary')); self.body.addWidget(bar)
    def correct_optical(self): self.open_stage(3)
    def optical_changed(self):
        self.result=None; self.persist()

    def show_entry(self,is_key):
        self.is_key=is_key; self.values=self.key if is_key else self.answers
        p=panel(self.body); p.addWidget(label(self.config.name,'tileTitle',True))
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
        if not is_key: row.addWidget(btn('Pendientes → blanco',self.fill_blanks))
        p.addLayout(row); p.addWidget(btn('Continuar a respuestas ›' if is_key else 'Corregir examen',self.next_entry,'primary'))
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
            num.setText(self.config.number(i)); num.setProperty('selected',i==self.cursor); num.setProperty('pending',self.values[i]==''); num.setToolTip('Pendiente de rellenar' if self.values[i]=='' else 'Respuesta registrada'); num.style().unpolish(num); num.style().polish(num)
            for value,b in choices: b.setChecked(self.values[i]==value)
            clear.setEnabled(bool(self.values[i]))
        # Set focus inside page when coming from a navigation button, enabling keyboard entry.
        focused=QApplication.focusWidget()
        if focused is None or not self.isAncestorOf(focused) or not focused.isVisible(): self.focus_entry()

    def focus_entry(self):
        if self.stage in (1,2) and not (self.stage==2 and self.mode=='automatic') and (self.stage==2 or self.key_source) and self.isVisible(): self.grid_rows[self.cursor%16][1].setFocus()

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
        from .template_ui import named_save
        try:
            payload={'config':asdict(self.config),'key':list(self.key),'key_source':self.key_source,'document_ref':self.document_ref}
            suggested=next((n for i,n,_ in self.storage.templates() if i==self.template_id),None) or (Path(self.key_source).stem if self.document_ref else self.config.name)
            tid=named_save(self,self.storage,payload,suggested)
            if tid is not None:
                self.template_id=tid; self.persist(); self.notice.setText('Plantilla guardada')
        except Exception as e: QMessageBox.warning(self,'No se pudo guardar',str(e))
    def fill_blanks(self):
        n=self.answers.count('')
        if n and confirm(self,'Respuestas pendientes',f'¿Marcar las {n} respuestas pendientes como en blanco?'):
            self.result=None; self.answers[:]=[v or '-' for v in self.answers]; self.persist(); self.refresh_entries()
    def next_entry(self):
        if self.is_key:
            if self.complete_key(): self.move_stage(2)
        else:
            if not self.check_counts(): return
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
