import os, tempfile, unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    HAS_QT=True
except ImportError:
    HAS_QT=False
if HAS_QT:
    from agora.ui import MainWindow
    from agora.manual import ManualPage
    ORIGINAL_LEAVE=ManualPage.allow_leave
    ORIGINAL_ENTER=ManualPage.allow_enter
from agora.storage import Storage
from agora.answer_import import ImportedKey
from agora.modules import MODULES

@unittest.skipUnless(HAS_QT,'PySide6 no disponible')
class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        # Older tests exercise grading, not modal leave/enter prompts.
        from unittest.mock import patch
        from agora.manual import ManualPage
        for method in ('allow_leave','allow_enter'):
            p=patch.object(ManualPage,method,return_value=True); p.start(); self.addCleanup(p.stop)
    def test_navigation_and_settings(self):
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); self.app.processEvents()
            for key in ['home',*(m.key for m in MODULES),'settings']:
                w.nav[key].click(); self.assertIs(w.stack.currentWidget(),w.pages[key]); self.assertEqual(sum(b.isChecked() for b in w.nav.values()),1)
            w.name.setText('Prueba'); w.message.setText('Vamos'); w.save_settings(); w.go('home')
            self.assertEqual(w.greeting.text(),'¡Hola, Prueba!'); self.assertEqual(w.motto.text(),'Vamos')
            w.close()
    def test_manual_workflow_and_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('manual'); self.app.processEvents(); m=w.manual
            m.name.setText('Prueba 3'); m.apply_config(); self.app.processEvents()
            self.assertEqual(m.stage,1)
            m.install_key(ImportedKey(tuple('AXB'),('C',)),'prueba.pdf',3)
            m.next_entry(); self.app.processEvents(); self.assertEqual(m.stage,2)
            for i,v in enumerate('AB-C'): m.choose(i,v)
            m.next_entry(); self.app.processEvents(); self.assertEqual(m.stage,3)
            self.assertEqual((m.result.correct,m.result.blank,m.result.reserve_used),(2,1,1)); self.assertEqual(m.table.rowCount(),4)
            m.filter.setCurrentIndex(3); self.assertEqual(m.table.rowCount(),1)
            self.assertTrue(m.save_progress()); aid=m.attempt_id
            w.close(); w.deleteLater(); self.app.processEvents()
            w2=MainWindow(Storage(d)); w2.show(); w2.go('manual'); self.assertEqual(w2.manual.stage,0); w2.open_history(aid); self.app.processEvents(); self.assertEqual(w2.manual.stage,3); self.assertEqual(w2.manual.result.correct,2)
            w2.manual.move_stage(2); self.app.processEvents(); w2.manual.choose(0,'B'); w2.manual.next_entry(); self.app.processEvents(); self.assertEqual(w2.manual.result.wrong,1)
            w2.close(); w2.deleteLater(); self.app.processEvents()
    def test_manual_keyboard(self):
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('manual'); self.app.processEvents(); m=w.manual
            m.apply_config(); self.app.processEvents(); m.focus_entry(); self.app.processEvents()
            m.install_key(ImportedKey(('C','C'),()),'prueba.pdf',3); self.app.processEvents()
            # Exercise the keyboard handlers via their real QShortcut signals as well as mouse clicks.
            m.shortcuts[0].activated.emit(); self.assertEqual(m.key[0],'A'); self.assertEqual(m.cursor,1)
            m.grid_rows[1][2][1][1].click(); self.assertEqual(m.key[1],'B'); m.next_entry(); self.app.processEvents()
            m.shortcuts[0].activated.emit(); m.shortcuts[3].activated.emit(); self.assertEqual(m.answers,['A','-']); m.next_entry(); self.app.processEvents(); self.assertEqual(m.result.grade,5)
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_direct_steps_and_current_result(self):
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('manual'); self.app.processEvents(); m=w.manual
            m.step_labels[1].click()
            self.assertEqual(m.stage,1)
            m.step_labels[2].click(); self.assertEqual(m.stage,1)
            m.install_key(ImportedKey(('A','B'),()),'prueba.pdf',3); m.step_labels[2].click()
            m.choose(0,'A'); m.choose(1,'C'); m.step_labels[3].click()
            self.assertEqual(m.stage,3); self.assertEqual(m.result.wrong,1)
            m.step_labels[0].click(); self.assertEqual(m.stage,0)
            m.penalty.setCurrentText('0'); m.step_labels[3].click()
            self.assertEqual(m.stage,3); self.assertEqual(m.result.grade,5)
            m.step_labels[2].click(); m.choose(1,'B'); m.step_labels[3].click()
            self.assertEqual(m.result.grade,10)
            m.step_labels[2].click(); m.clear(1); m.step_labels[3].click()
            self.assertEqual(m.stage,2); self.assertEqual(m.answers[1],'')
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_wheel_does_not_change_form_controls(self):
        from PySide6.QtCore import QPoint,QPointF,Qt
        from PySide6.QtGui import QWheelEvent
        from agora.controls import SafeComboBox, SafeSpinBox, SafeDoubleSpinBox
        widgets=[SafeComboBox(),SafeComboBox(),SafeSpinBox(),SafeDoubleSpinBox()]
        for i,w in enumerate(widgets):
            if i<2:
                w.setEditable(i==1); w.addItems(['0','1/3','1/2']); w.setCurrentIndex(1)
                before=w.currentText(); get=w.currentText
            else:
                w.setRange(0,100); w.setValue(10); before=w.value(); get=w.value
            w.show(); w.setFocus(); self.app.processEvents()
            for delta in (120,-120):
                event=QWheelEvent(QPointF(5,5),QPointF(5,5),QPoint(),QPoint(0,delta),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
                self.app.sendEvent(w,event); self.assertEqual(get(),before); self.assertFalse(event.isAccepted())
            w.close(); w.deleteLater()
        self.app.processEvents()

    def test_view_template_without_replacing_draft(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog,QTableWidget
        from dataclasses import asdict
        from agora.grading import ExamConfig
        with tempfile.TemporaryDirectory() as d:
            storage=Storage(d); storage.save_template('Guardada',{'config':asdict(ExamConfig(questions=2,reserves=1)),'key':['A','X','C']})
            w=MainWindow(storage); w.show(); w.go('manual'); self.app.processEvents(); m=w.manual
            m.templates_combo.setCurrentIndex(1); m.templates_combo.activated.emit(1); self.assertEqual(m.stage,0); self.assertEqual(m.key,['A','X','C']); self.assertEqual(m.answers,['','','']); m.name.setText('Borrador sin confirmar'); before=storage.load_draft(); seen=[]
            def inspect():
                dlg=self.app.activeModalWidget()
                if isinstance(dlg,QDialog):
                    table=dlg.findChild(QTableWidget)
                    if table: seen.extend((table.rowCount(),table.item(1,1).text(),table.item(2,0).text()))
                    dlg.accept()
            QTimer.singleShot(0,inspect); m.view_template()
            self.assertEqual(seen,[3,'Anulada','R1']); self.assertEqual(m.name.text(),'Borrador sin confirmar'); self.assertEqual(storage.load_draft(),before); self.assertEqual(len(storage.templates()),1)
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_saved_progress_and_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); w=MainWindow(s); w.show(); w.go('manual'); m=w.manual
            m.name.setText('Parcial'); m.apply_config(); m.install_key(ImportedKey(('A','B'),()),'prueba.pdf',3); m.next_entry(); m.choose(0,'A')
            self.assertTrue(m.dirty()); self.assertTrue(m.save_progress()); self.assertFalse(m.dirty()); aid=m.attempt_id
            m.choose(1,'C'); self.assertTrue(m.dirty()); self.assertTrue(m.start_new()); self.assertFalse(m.active()); self.assertEqual(len(s.attempts()),1)
            self.assertTrue(m.open_saved(aid)); self.assertEqual(m.answers,['A','']); self.assertFalse(m.dirty())
            m.choose(1,'B'); m.next_entry(); self.assertTrue(m.save_progress()); self.assertEqual(len(s.attempts()),1); self.assertEqual(s.load_attempt(aid)['stage'],3)
            w.go('history'); self.assertGreater(w.history_layout.count(),0); w.close(); w.deleteLater(); self.app.processEvents()
    def test_import_source_tiles_and_mobile_page(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QToolButton
        from agora.import_ui import ImportDialog
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); dlg=ImportDialog(w); dlg.show(); self.app.processEvents()
            self.assertEqual([b.text() for b in dlg.source.findChildren(QToolButton)],['Desde PC','Desde móvil']); self.assertEqual(dlg.cancel.width(),136)
            with patch('agora.import_ui.local_addresses',return_value=['127.0.0.1']): dlg.mobile()
            try:
                self.assertIs(dlg.stack.currentWidget(),dlg.mobile_page); self.assertFalse(dlg.qr.pixmap().isNull()); self.assertTrue(dlg.address.isHidden()); self.assertFalse(dlg.source.isVisible())
            finally: dlg.cleanup(); dlg.deleteLater(); w.close(); w.deleteLater(); self.app.processEvents()

    def test_exit_and_reentry_dialogs(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QMessageBox
        # Exercise original dialogs, not the bypass used by the older tests.
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('manual'); m=w.manual
            m.name.setText('Sin guardar')
            def click(text):
                def callback():
                    dlg=self.app.activeModalWidget()
                    if isinstance(dlg,QMessageBox):
                        for b in dlg.buttons():
                            if b.text()==text: b.click(); return
                        dlg.reject()
                QTimer.singleShot(0,callback)
            click('Cancelar'); self.assertFalse(ORIGINAL_LEAVE(m))
            click('Salir sin guardar'); self.assertTrue(ORIGINAL_LEAVE(m)); self.assertIsNone(w.storage.load_draft()); self.assertFalse(m.active())
            self.assertTrue(ORIGINAL_ENTER(m)); self.assertFalse(m.active()); self.assertIsNone(w.storage.load_draft())
            m.name.setText('Guardar al salir'); click('Guardar y salir'); self.assertTrue(ORIGINAL_LEAVE(m)); self.assertIsNone(w.storage.load_draft()); aid=w.storage.attempts()[0][0]
            self.assertTrue(ORIGINAL_ENTER(m)); self.assertFalse(m.active()); self.assertTrue(m.open_saved(aid)); self.assertEqual(m.name.text(),'Guardar al salir')
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_config_structure_and_import(self):
        from PySide6.QtWidgets import QSpinBox
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('manual'); m=w.manual
            self.assertEqual(len([x for x in m.content.findChildren(QSpinBox) if x.isVisible()]),2)
            m.name.setText('Importado'); m.apply_config(); m.install_key(ImportedKey(('A','B','D'),('A',)),'prueba.pdf',4)
            m.next_entry(); m.choose(0,'A'); m.move_stage(0); m.penalty.setCurrentText('0'); m.apply_config(target=2)
            self.assertEqual((m.config.questions,m.config.reserves,m.config.options),(3,1,4)); self.assertEqual(m.answers[0],'A'); self.assertEqual(m.config.penalty,'0')
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_history_delete_confirmation_and_active_draft(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); w=MainWindow(s); w.show(); w.go('manual'); m=w.manual
            m.name.setText('Conservar'); m.apply_config(); m.install_key(ImportedKey(('A','B'),()),'prueba.pdf',3); m.next_entry(); m.choose(0,'A'); m.save_progress(); keep=m.attempt_id
            m.start_new(); m.name.setText('Eliminar'); m.apply_config(); m.install_key(ImportedKey(('B','C'),()),'prueba.pdf',3); m.next_entry(); m.choose(0,'B'); m.save_progress(); remove=m.attempt_id
            w.go('history')
            with patch('agora.ui.confirm',return_value=False): w.delete_history(remove,'Eliminar')
            self.assertEqual(len(s.attempts()),2); self.assertEqual(m.attempt_id,remove)
            with patch('agora.ui.confirm',return_value=True): w.delete_history(remove,'Eliminar')
            self.assertEqual([x[0] for x in s.attempts()],[keep]); self.assertIsNone(s.load_draft()); self.assertFalse(m.active())
            self.assertTrue(m.open_saved(keep)); self.assertEqual(m.answers,['A',''])
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_automatic_workflow_history_and_excluded_cells(self):
        from unittest.mock import patch
        from test_omr import sheet, mark
        from agora import omr
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); w=MainWindow(s); w.show(); w.go('automatic'); m=w.automatic
            m.name.setText('Automático'); m.apply_config(); m.install_key(ImportedKey(('A','B'),('C',)),'soluciones.pdf',3); m.next_entry()
            self.assertEqual(m.stage,2)
            im=sheet(); mark(im,0,0,0,(20,40,120)); mark(im,0,1,1,(20,40,120)); mark(im,0,2,2,(20,40,120)); res=sheet(1); mark(res,1,0,2,(20,40,120))
            m.reader.install(1,res,res,omr.scan(res,1)); m.reader.install(0,im,im,omr.scan(im,0)); m.optical_changed()
            self.assertEqual(m.answers,['A','B','C']); self.assertIsNone(s.load_draft()); self.assertEqual(s.load_draft('automatic')['answers'],['A','B','C'])
            with patch('agora.manual.confirm',return_value=True): m.correct_optical()
            self.assertEqual(m.stage,3); self.assertEqual(m.result.correct,2); self.assertEqual(m.result.reserve_used,0); self.assertTrue(m.save_progress()); aid=m.attempt_id
            w.go('history'); from PySide6.QtWidgets import QLabel
            self.assertTrue(any(x.text()=='· Corrección automática' for x in w.history_panel.findChildren(QLabel,'historyMode'))); m.start_new(); w.open_history(aid); self.assertIs(w.stack.currentWidget(),w.pages['automatic']); self.assertEqual(m.result.correct,2)
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_template_auto_load_cancel_preserves_active(self):
        from unittest.mock import patch
        from dataclasses import asdict
        from agora.grading import ExamConfig
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); s.save_template('Primera',{'config':asdict(ExamConfig(name='Primera',questions=2,reserves=0)),'key':['A','B']}); s.save_template('Segunda',{'config':asdict(ExamConfig(name='Segunda',questions=3,reserves=0)),'key':['C','B','A']})
            w=MainWindow(s); w.show(); w.go('manual'); m=w.manual
            m.templates_combo.setCurrentIndex(m.templates_combo.findText('Primera')); m.templates_combo.activated.emit(m.templates_combo.currentIndex()); self.assertEqual(m.key,['A','B']); self.assertEqual(m.stage,0)
            m.name.setText('En curso'); before=m.payload(True)
            m.templates_combo.setCurrentIndex(m.templates_combo.findText('Segunda')); m.templates_combo.activated.emit(m.templates_combo.currentIndex())
            self.assertEqual(m.payload(True),before); self.assertEqual(m.templates_combo.currentText(),'Segunda')
            with patch('agora.manual.confirm',return_value=False): self.assertFalse(m.load_template())
            self.assertEqual(m.payload(True),before)
            with patch('agora.manual.confirm',return_value=True): self.assertTrue(m.load_template())
            self.assertEqual(m.key,['C','B','A']); self.assertEqual(m.answers,['','','']); self.assertEqual(m.name.text(),'Segunda')
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_clear_template_and_pending_number(self):
        from unittest.mock import patch
        from dataclasses import asdict
        from agora.grading import ExamConfig
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); s.save_template('Plantilla',{'config':asdict(ExamConfig(name='Plantilla',questions=3,reserves=0)),'key':['A','B','C']})
            w=MainWindow(s); w.show(); w.go('manual'); m=w.manual; m.templates_combo.setCurrentIndex(1); m.templates_combo.activated.emit(1)
            m.apply_config(target=2); m.choose(0,'A'); m.choose(2,'-'); self.assertFalse(m.grid_rows[0][1].property('pending')); self.assertTrue(m.grid_rows[1][1].property('pending')); self.assertFalse(m.grid_rows[2][1].property('pending')); m.save_progress(); aid=m.attempt_id
            m.move_stage(0); self.assertEqual(m.templates_combo.currentText(),'Plantilla')
            with patch('agora.manual.confirm',return_value=False): self.assertFalse(m.clear_template())
            self.assertEqual(m.key,['A','B','C'])
            with patch('agora.manual.confirm',return_value=True): self.assertTrue(m.clear_template())
            self.assertEqual(m.templates_combo.currentIndex(),0); self.assertFalse(m.key_source); self.assertFalse(any(m.answers)); self.assertEqual(s.load_attempt(aid)['answers'],['A','','-']); self.assertEqual(len(s.templates()),1)
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_optical_reopen_images_and_review(self):
        from unittest.mock import patch
        import numpy as np
        from test_omr import sheet,mark
        from agora import omr
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); w=MainWindow(s); w.show(); w.go('automatic'); m=w.automatic
            m.install_key(ImportedKey(('B','A'),('C',)),'test.pdf',3); m.next_entry()
            im=sheet(); mark(im,0,0,1,(20,40,120)); res=sheet(1); mark(res,1,0,2,(20,40,120))
            m.reader.install(0,im,im,omr.scan(im,0)); m.reader.install(1,res,res,omr.scan(res,1)); m.optical_changed(); m.reader.set_choice(1,'A'); m.save_progress(); aid=m.attempt_id
            self.assertTrue(m.start_new()); w.close(); w.deleteLater(); self.app.processEvents()
            w=MainWindow(Storage(d)); w.show(); w.open_history(aid); m=w.automatic; self.assertEqual(m.stage,2); self.assertEqual(m.answers,['B','A','C']); self.assertFalse(m.dirty()); self.assertTrue(np.array_equal(m.reader.images[0],im)); self.assertTrue(np.array_equal(m.reader.images[1],res)); self.assertEqual(m.reader.table.rowCount(),2)
            with patch('agora.omr_ui.OpticalPage.alignment_dialog',side_effect=ValueError('Fallo simulado')),patch('agora.omr_ui.QMessageBox.warning'):
                m.reader.adjust()
            self.assertEqual(m.answers,['B','A','C']); self.assertTrue(np.array_equal(m.reader.images[0],im)); self.assertFalse(m.dirty())
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_same_template_consult_does_not_change_name_or_answers(self):
        from unittest.mock import patch
        from dataclasses import asdict
        from agora.grading import ExamConfig
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); s.save_template('Plantilla',{'config':asdict(ExamConfig(name='Plantilla',questions=2,reserves=0)),'key':['A','B']})
            w=MainWindow(s); w.show(); w.go('manual'); m=w.manual; m.templates_combo.setCurrentIndex(1); m.templates_combo.activated.emit(1); m.apply_config(target=2); m.choose(0,'A'); m.move_stage(0); m.name.setText('Nombre propio'); before=m.payload(True)
            m.templates_combo.activated.emit(1)
            with patch('agora.library_ui.consult_template') as view: m.view_template(); view.assert_called_once()
            self.assertEqual(m.payload(True),before); self.assertEqual(m.name.text(),'Nombre propio'); self.assertEqual(m.answers,['A',''])
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_library_documents_and_fresh_entry_from_history(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); ref=s.archive_solution_document('soluciones.pdf',b'%PDF-1.4\noriginal'); w=MainWindow(s); w.show(); w.go('manual'); m=w.manual
            m.install_key(ImportedKey(('A','B'),()),'soluciones.pdf',3,document_ref=ref); m.next_entry(); m.choose(0,'A'); m.save_progress(); aid=m.attempt_id
            self.assertTrue(ORIGINAL_LEAVE(m)); w.go('library'); self.assertEqual(w.library_tabs.tabText(1),'Mis plantillas'); self.assertEqual(len(s.solution_documents()),1)
            w.go('manual'); self.assertTrue(ORIGINAL_ENTER(m)); self.assertFalse(m.active()); self.assertEqual(m.stage,0); self.assertEqual(len(s.attempts()),1)
            w.go('history'); w.open_history(aid); self.assertEqual(m.answers,['A','']); self.assertEqual(m.document_ref,ref)
            self.assertTrue(ORIGINAL_LEAVE(m)); w.go('home'); w.close(); w.deleteLater(); self.app.processEvents()

    def test_shared_library_from_both_directions(self):
        from unittest.mock import patch
        from dataclasses import asdict
        from agora.grading import ExamConfig
        from agora.answer_import import ImportedKey
        from PySide6.QtWidgets import QPushButton
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); w=MainWindow(s); w.show(); w.go('library')
            with patch('agora.answer_import.extract_key',return_value=ImportedKey(('A','B'),())), patch('agora.template_ui.review_key',return_value=3), patch('agora.template_ui.ask_template_name',return_value='Biblioteca'):
                w.register_library_document('Biblioteca.pdf',b'original')
            w.refresh_library(); self.assertEqual(len(s.library_entries()),1)
            self.assertEqual(w.library_tabs.tabText(1),'Mis plantillas')
            w.go('manual'); m=w.manual; m.refresh_templates(); self.assertGreaterEqual(m.templates_combo.findText('Biblioteca'),1)
            m.move_stage(1)
            with patch('agora.template_ui.review_key',return_value=3), patch('agora.manual.confirm',return_value=True): m.review_import(ImportedKey(('C','B'),()),'Corrector.pdf',b'original2')
            self.assertEqual(len(s.library_entries()),1); self.assertTrue(any(b.text()=='Guardar plantilla' for b in m.findChildren(QPushButton)))
            with patch('agora.template_ui.ask_template_name',return_value=None): m.save_template()
            self.assertEqual(len(s.library_entries()),1)
            with patch('agora.template_ui.ask_template_name',return_value='Corrector'): m.save_template()
            self.assertEqual(len(s.library_entries()),2)
            w.go('automatic'); w.automatic.refresh_templates(); self.assertGreaterEqual(w.automatic.templates_combo.findText('Corrector'),1)
            w.close()

    def test_library_root_and_deletion_confirmation(self):
        from unittest.mock import patch
        from dataclasses import asdict
        from agora.grading import ExamConfig
        from PySide6.QtWidgets import QPushButton
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); p={'config':asdict(ExamConfig(questions=2,reserves=0)),'key':['A','B']}; tid=s.save_template('Vinculada',p); aid=s.save_attempt(dict(p,template_id=tid,answers=['A','B']))
            w=MainWindow(s); w.show(); w.go('library'); self.assertEqual(w.library_stack.currentIndex(),0)
            w.library_buttons[0].click(); self.assertEqual(w.library_stack.currentIndex(),1); self.assertEqual(w.library_tabs.currentIndex(),0)
            w.go('library'); self.assertEqual(w.library_stack.currentIndex(),0); w.library_buttons[1].click(); self.assertEqual(w.library_tabs.currentIndex(),1)
            self.assertTrue(any(b.text()=='Eliminar plantilla' for b in w.library_tabs.widget(1).findChildren(QPushButton)))
            with patch('agora.template_ui.confirm',return_value=False) as ask:
                w.delete_library_template(tid); self.assertIn('1 simulacro',ask.call_args.args[2]); self.assertIsNotNone(s.load_attempt(aid))
            with patch('agora.template_ui.confirm',return_value=True): w.delete_library_template(tid)
            self.assertIsNone(s.load_attempt(aid)); self.assertEqual(s.library_entries(),[]); w.close(); w.deleteLater(); self.app.processEvents()

    def test_missing_reserves_and_invalid_printed_option(self):
        from unittest.mock import patch
        from dataclasses import replace
        from agora import omr
        from test_omr import sheet
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('automatic'); m=w.automatic
            m.install_key(ImportedKey(('A','B'),('C',)),'key.pdf',3); m.next_entry()
            im=sheet(); marks=omr.scan(im,0)
            marks[0]=replace(marks[0],suggestion='D',status='Azul detectado',scores=(0,0,0,50),red=(0,0,0,0))
            m.reader.install(0,im,im,marks); self.assertEqual(m.answers,['','-',''])
            m.reader.set_choice(0,'A'); m.reader.set_choice(1,'B')
            with patch('agora.manual.confirm',return_value=False): m.correct_optical()
            self.assertEqual(m.answers,['A','B','']); self.assertEqual(m.stage,2)
            with patch('agora.manual.confirm',return_value=True): m.correct_optical()
            self.assertEqual(m.result.correct,2); self.assertEqual(m.result.reserve_used,0); self.assertEqual(m.stage,3)
            w.close()

    def test_config_counts_mismatch_requires_confirmation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('manual'); m=w.manual
            m.question_count.setValue(3); m.reserve_count.setValue(0); m.apply_config()
            self.assertEqual(m.expected_counts,(3,0))
            m.install_key(ImportedKey(('A','B'),()),'key.pdf',3,preserve_expected=True); m.next_entry(); m.choose(0,'A'); m.choose(1,'B')
            with patch('agora.manual.confirm',return_value=False): m.next_entry()
            self.assertEqual(m.stage,2)
            with patch('agora.manual.confirm',return_value=True): m.next_entry()
            self.assertEqual(m.result.correct,2); self.assertEqual(m.expected_counts,(2,0)); w.close()
