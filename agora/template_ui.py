"""Shared naming, duplicate review and import preview for both entry points."""
from dataclasses import asdict
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QInputDialog,QMessageBox)
from .manual import label,btn,confirm
from .controls import SafeSpinBox
from .grading import ExamConfig,evaluate


def review_key(parent, imported, name, default_options=3):
    dlg=QDialog(parent); dlg.setWindowTitle('Revisar soluciones'); dlg.resize(640,610); lay=QVBoxLayout(dlg)
    lay.addWidget(label(name,'heading',True)); lay.addWidget(label(f'{len(imported.ordinary)} preguntas · {len(imported.reserves)} reservas','tileTitle'))
    options=SafeSpinBox(); options.setRange(imported.options,5); options.setValue(max(default_options,imported.options)); row=QHBoxLayout(); row.addWidget(label('Opciones por pregunta')); row.addWidget(options); lay.addLayout(row)
    table=QTableWidget(len(imported.key),2); table.setHorizontalHeaderLabels(['Pregunta','Solución']); table.verticalHeader().hide(); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    for i,v in enumerate(imported.key):
        number=str(i+1) if i<len(imported.ordinary) else 'R'+str(i-len(imported.ordinary)+1)
        for j,value in enumerate((number,'Anulada' if v=='X' else v)):
            item=QTableWidgetItem(value); item.setTextAlignment(Qt.AlignmentFlag.AlignCenter); table.setItem(i,j,item)
    lay.addWidget(table,1); row=QHBoxLayout(); row.addWidget(btn('Cancelar',dlg.reject)); row.addWidget(btn('Confirmar',dlg.accept,'primary')); lay.addLayout(row)
    return options.value() if dlg.exec()==QDialog.DialogCode.Accepted else None


def named_save(parent,storage,payload,suggested,document=None):
    """Return ID or None. Exact pattern ignores name, scoring and option count."""
    c=ExamConfig(**payload['config']); evaluate(c,payload['key'],['-']*c.size)
    matches=storage.matching_templates(payload)
    replace_id=None
    if matches:
        box=QMessageBox(parent); box.setWindowTitle('Plantilla coincidente'); box.setIcon(QMessageBox.Icon.Question)
        box.setText('Ya existen plantillas con el mismo patrón de respuestas:'); box.setInformativeText('\n'.join(n for _,n,_ in matches)); box.setTextFormat(Qt.TextFormat.PlainText)
        overwrite=box.addButton('Sobrescribir',QMessageBox.ButtonRole.AcceptRole); other=box.addButton('Guardar con otro nombre',QMessageBox.ButtonRole.ActionRole); cancel=box.addButton('Cancelar',QMessageBox.ButtonRole.RejectRole); box.setDefaultButton(cancel); box.setEscapeButton(cancel); box.exec()
        if box.clickedButton() is overwrite:
            if len(matches)==1: replace_id=matches[0][0]; suggested=matches[0][1]
            else:
                choices=[f'{n} (#{tid})' for tid,n,_ in matches]
                chosen,ok=QInputDialog.getItem(parent,'Sobrescribir plantilla','Selecciona la plantilla:',choices,0,False)
                if not ok: return None
                replace_id,suggested,_=matches[choices.index(chosen)]
        elif box.clickedButton() is not other: return None
    name=ask_template_name(parent,suggested)
    if name is None: return None
    if not name: return None
    if len(name)>120: raise ValueError('Usa como máximo 120 caracteres.')
    existing=[r for r in storage.templates() if r[1].casefold()==name.casefold() and r[0]!=replace_id]
    if existing:
        QMessageBox.warning(parent,'Nombre ya utilizado','Elige un nombre diferente para distinguir las plantillas.'); return None
    if replace_id is not None and not confirm(parent,'Sobrescribir plantilla','Se sustituirá la plantilla guardada. Los simulacros existentes no cambiarán. ¿Continuar?'): return None
    if document is not None:
        payload=dict(payload,document_ref=storage.archive_solution_document(*document))
    return storage.save_template(name,dict(payload,config=dict(payload['config'],name=name)),replace_id=replace_id)


def ask_template_name(parent,suggested):
    dlg=QInputDialog(parent); dlg.setWindowTitle('Guardar plantilla'); dlg.setLabelText('Nombre de la plantilla:'); dlg.setTextValue(suggested[:120]); dlg.setOkButtonText('Guardar'); dlg.setCancelButtonText('Cancelar')
    return dlg.textValue().strip() if dlg.exec()==QDialog.DialogCode.Accepted else None


def delete_named_template(parent,storage,tid,active=False):
    affected=storage.template_attempts(tid)
    message='Se va a eliminar la plantilla seleccionada.'
    if affected:
        message+=f' Se ha utilizado en {len(affected)} simulacro(s) guardado(s), que también se eliminarán:\n'+'\n'.join(n for _,n in affected)
    if active: message+='\nEl simulacro actual que utiliza esta plantilla también se cerrará.'
    message+='\nEsta operación no se puede deshacer. ¿Seguro que quieres continuar?'
    if not confirm(parent,'Eliminar plantilla',message): return False
    return storage.delete_template(tid,confirmed_attempts=[i for i,_ in affected])

