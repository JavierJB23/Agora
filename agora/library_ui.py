"""Read-only library of solution documents and reusable answer keys."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,QHeaderView,
    QAbstractItemView,QLabel,QScrollArea,QFileDialog,QMessageBox)
from .manual import label,btn
from .grading import ExamConfig,evaluate


def export_document(parent,name,data):
    dest,_=QFileDialog.getSaveFileName(parent,'Guardar copia del documento',name,'PDF (*.pdf)' if name.lower().endswith('.pdf') else 'Word (*.docx)')
    if dest:
        try: Path(dest).write_bytes(data)
        except OSError as e: QMessageBox.warning(parent,'No se pudo guardar la copia',str(e))


def consult_document(parent,storage,ref):
    try: name,data=storage.load_solution_document(ref)
    except Exception as e: QMessageBox.warning(parent,'Documento no disponible',str(e)); return
    dlg=QDialog(parent); dlg.setWindowTitle('Consultar documento original'); dlg.resize(800,720); lay=QVBoxLayout(dlg)
    lay.addWidget(label(name,'heading',True))
    if not name.lower().endswith('.pdf'):
        lay.addWidget(label('Documento Word conservado sin modificaciones. Guarda una copia para abrirla en tu lector habitual.',wrap=True)); lay.addStretch()
        lay.addWidget(btn('Guardar copia',lambda:export_document(dlg,name,data),'primary')); lay.addWidget(btn('Cerrar',dlg.accept)); dlg.exec(); return
    import pypdfium2 as pdfium
    try: doc=pdfium.PdfDocument(data)
    except Exception as e: QMessageBox.warning(parent,'No se pudo abrir el PDF',str(e)); return
    try:
        page_number=0; info=label('','muted'); nav=QHBoxLayout()
        previous=btn('‹ Anterior',lambda:change(-1)); following=btn('Siguiente ›',lambda:change(1)); nav.addWidget(previous); nav.addWidget(info,1,Qt.AlignmentFlag.AlignCenter); nav.addWidget(following); lay.addLayout(nav)
        scroll=QScrollArea(); scroll.setWidgetResizable(False); scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter); image=QLabel(); scroll.setWidget(image); lay.addWidget(scroll,1)
        def render():
            info.setText(f'Página {page_number+1} de {len(doc)}'); previous.setEnabled(page_number>0); following.setEnabled(page_number+1<len(doc))
            try:
                page=doc[page_number]
                try:
                    w,h=page.get_size(); bitmap=page.render(scale=min(1.6,1400/max(w,h)))
                    try:
                        pil=bitmap.to_pil().convert('RGB'); raw=pil.tobytes(); q=QImage(raw,pil.width,pil.height,pil.width*3,QImage.Format.Format_RGB888).copy()
                    finally: bitmap.close()
                finally: page.close()
                image.setPixmap(QPixmap.fromImage(q)); image.resize(q.size()); scroll.verticalScrollBar().setValue(0)
            except Exception as e: image.clear(); image.setText('No se pudo mostrar esta página: '+str(e)); image.adjustSize()
        def change(delta):
            nonlocal page_number
            page_number=max(0,min(len(doc)-1,page_number+delta)); render()
        bar=QHBoxLayout(); bar.addWidget(btn('Guardar copia del PDF',lambda:export_document(dlg,name,data))); bar.addStretch(); bar.addWidget(btn('Cerrar',dlg.accept,'primary')); lay.addLayout(bar)
        render(); dlg.exec()
    finally: doc.close()


def consult_template(parent,storage,name,d):
    c=ExamConfig(**d['config']); k=list(d['key']); evaluate(c,k,['-']*c.size)
    dialog=QDialog(parent); dialog.setWindowTitle('Consultar plantilla'); dialog.resize(540,560)
    lay=QVBoxLayout(dialog); lay.addWidget(label(name,'heading',True))
    lay.addWidget(label(f'{c.questions} preguntas · {c.reserves} reservas · {c.options} opciones · Penalización: {c.penalty} · Nota máxima: {c.maximum}','muted',True))
    table=QTableWidget(c.size,2); table.setHorizontalHeaderLabels(['Pregunta','Respuesta correcta']); table.verticalHeader().hide(); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); table.setAlternatingRowColors(True)
    for i,v in enumerate(k):
        for j,text in enumerate((c.number(i),'Anulada' if v=='X' else v)):
            item=QTableWidgetItem(text); item.setTextAlignment(Qt.AlignmentFlag.AlignCenter); table.setItem(i,j,item)
    lay.addWidget(table,1)
    if d.get('document_ref'): lay.addWidget(btn('Consultar documento original',lambda:consult_document(dialog,storage,d['document_ref'])))
    else: lay.addWidget(label('Plantilla anterior: no se conserva el archivo original.','muted',True))
    lay.addWidget(btn('Cerrar',dialog.accept,'primary')); dialog.exec()
