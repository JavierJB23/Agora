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
            with patch('agora.omr_ui.OpticalPage.alignment_workspace',side_effect=ValueError('Fallo simulado')),patch('agora.omr_ui.QMessageBox.warning'):
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

    def test_large_tile_content_centered(self):
        from agora.import_ui import ImportDialog
        from agora.controls import CenteredTile
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); self.app.processEvents()
            dlg=ImportDialog(w); dlg.show(); self.app.processEvents()
            for tile in [*w.home_tiles.values(),*w.library_buttons,*dlg.source.findChildren(CenteredTile)]:
                icon_rect,text_rect=tile.content_rects()
                self.assertLessEqual(abs(icon_rect.top()-(tile.height()-text_rect.bottom()-1)),1)
                self.assertLessEqual(abs(icon_rect.center().x()-tile.rect().center().x()),1)
                self.assertGreater(text_rect.top(),icon_rect.bottom())
            dlg.reject(); w.close()

    def test_restore_numbering_without_reimport(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QDialog,QLineEdit,QPushButton
        from agora.omr_ui import OpticalPage
        from agora import omr
        from test_omr import square_sheet
        im=square_sheet(); blocks=omr.square_blocks(im)
        # Invoke the real dialog controls, without blocking on a modal window.
        def exercise(d):
            field=d.findChild(QLineEdit); self.assertEqual(field.text(),'1, 11')
            field.setText('7, R1')
            next(b for b in d.findChildren(QPushButton) if b.text()=='Restablecer').click()
            self.assertEqual(field.text(),'1, 11')
            return QDialog.DialogCode.Accepted
        # Numbering dialog does not require the rest of the corrector state.
        from PySide6.QtWidgets import QWidget
        parent=QWidget()
        with patch.object(QDialog,'exec',exercise):
            marks=OpticalPage.choose_numbering(parent,im,blocks)
        self.assertEqual([m.number for m in marks],list(map(str,range(1,21))))

    def test_alignment_workspace_cancel_and_apply(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QDialog,QPushButton
        from agora.omr_ui import OpticalPage
        from agora.grading import ExamConfig
        from agora import omr
        from test_omr import square_sheet
        im=square_sheet(); blocks=omr.square_blocks(im); marks=omr.number_blocks(blocks,['1','11'])
        cache={}; answers=['']*20; changed=[]
        page=OpticalPage(ExamConfig(questions=20,reserves=0),answers,cache,lambda:changed.append(True))
        page.install(0,im,im,marks); page.set_choice(0,'X'); before=list(answers); changed.clear()
        original_record=page.records[0]
        def exercise(d):
            next(b for b in d.findChildren(QPushButton) if b.text()=='Restablecer automática').click()
            self.assertEqual(page.records[0],original_record); self.assertEqual(answers,before)
            return QDialog.DialogCode.Rejected
        with patch.object(page,'automatic_candidate',return_value=(im,marks)) as auto,patch.object(QDialog,'exec',exercise):
            page.adjust(); auto.assert_called_once()
        self.assertEqual(answers,before); self.assertFalse(changed)
        def apply(d):
            next(b for b in d.findChildren(QPushButton) if b.text()=='Restablecer automática').click()
            return QDialog.DialogCode.Accepted
        with patch.object(page,'automatic_candidate',return_value=(im,marks)),patch.object(QDialog,'exec',apply),patch('agora.omr_ui.confirm',return_value=True):
            page.adjust()
        self.assertEqual(answers[0],'X'); self.assertEqual(answers,before); self.assertTrue(changed)
        page.deleteLater(); self.app.processEvents()

    def test_annulment_controls_and_saved_attempt(self):
        from unittest.mock import patch
        from agora.grading import ExamConfig
        from PySide6.QtWidgets import QComboBox
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); w=MainWindow(s); m=w.manual
            m.install_key(ImportedKey(('A','A','A'),('B','C')),'test.pdf',3); m.next_entry()
            next(b for v,b in m.grid_rows[0][2] if v=='X').click()
            for i,v in enumerate('AABC',1): m.choose(i,v)
            m.next_entry(); self.assertEqual((m.result.annulled,m.result.reserve_used,m.result.correct),(1,1,3)); self.assertEqual(m.key,['A','A','A','B','C'])
            self.assertTrue(m.save_progress()); aid=m.attempt_id; m.start_new(); self.assertTrue(m.open_saved(aid)); self.assertEqual(m.answers[0],'X'); self.assertEqual(m.result.grade,10)
            a=w.automatic; a.install_key(ImportedKey(('A','A'),('B',)),'test.pdf',3); a.next_entry()
            a.reader.filter.setCurrentIndex(1); combo=a.reader.table.cellWidget(0,3); combo.setCurrentText('Anulada'); a.reader.set_choice(1,'A'); a.reader.set_choice(2,'B')
            with patch('agora.manual.confirm',return_value=True): a.correct_optical()
            self.assertEqual((a.result.annulled,a.result.reserve_used,a.result.correct),(1,1,2)); self.assertEqual(a.key,['A','A','B'])
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_alignment_has_same_actions_for_both_shapes(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QDialog,QPushButton
        from agora.omr_ui import OpticalPage
        from agora.grading import ExamConfig
        from agora import omr
        from test_omr import square_sheet,sheet
        menus=[]
        for im,marks in [(sheet(),omr.scan(sheet(),0)),(square_sheet(),omr.number_blocks(omr.square_blocks(square_sheet()),['1','11']))]:
            page=OpticalPage(ExamConfig(questions=120,reserves=0),['']*120,{},lambda:None)
            page.install(0,im,im,marks)
            def exercise(d):
                menus.append([b.text() for b in d.findChildren(QPushButton)])
                return QDialog.DialogCode.Rejected
            with patch.object(QDialog,'exec',exercise):
                self.assertIsNone(page.alignment_workspace(0))
            page.deleteLater(); self.app.processEvents()
        self.assertEqual(menus[0],menus[1])
        self.assertNotIn('Ajuste por bloques',menus[0]); self.assertNotIn('Redefinir bloques',menus[0])
        self.assertIn('Restablecer automática',menus[0]); self.assertNotIn('Ajuste por referencias',menus[0])

    def test_successful_import_and_reset_never_open_numbering(self):
        from unittest.mock import patch
        from agora.omr_ui import OpticalPage
        from agora.grading import ExamConfig
        from agora import omr
        from test_omr import square_sheet
        im=square_sheet(); marks=omr.number_blocks(omr.square_blocks(im),['1','11'])
        page=OpticalPage(ExamConfig(questions=20,reserves=0),['']*20,{},lambda:None)
        with patch.object(omr,'automatic_page',return_value=(im,marks)) as detect,patch.object(page,'choose_numbering',side_effect=AssertionError('No debe abrir numeración')),patch.object(page,'alignment_workspace',side_effect=AssertionError('No debe abrir ajuste')):
            self.assertEqual(page.read_page(im)[1],marks)
            self.assertEqual(page.automatic_candidate(im)[1],marks)
            self.assertEqual(detect.call_count,2)
        with patch.object(omr,'automatic_page',side_effect=ValueError('Lectura incierta')),patch.object(page,'alignment_workspace') as fallback,patch('agora.omr_ui.QMessageBox.warning') as warning:
            self.assertIsNone(page.read_page(im)); fallback.assert_not_called(); warning.assert_called_once()
        page.deleteLater(); self.app.processEvents()

    def test_import_reserve_without_key_keeps_image_and_does_not_score(self):
        from unittest.mock import patch
        from agora.omr_ui import OpticalPage
        from agora.grading import ExamConfig
        from agora.optical_archive import record,unpack
        from agora import omr
        from test_omr import sheet,mark
        from PySide6.QtWidgets import QDialog
        ordinary=sheet(); reserve=sheet(1); mark(reserve,1,0,1,(20,40,120))
        m0=omr.scan(ordinary,0); m1=omr.scan(reserve,1)
        for count in (0,9):
            answers=['']*(112+count); cache={}
            page=OpticalPage(ExamConfig(questions=112,reserves=count),answers,cache,lambda:None)
            results=[(im,im,marks,record(im,im,marks)) for im,marks in ((ordinary,m0),(reserve,m1))]
            with patch('agora.omr_ui.ImportDialog') as dialog,patch.object(page,'run_import',return_value=(results,[])),patch('agora.omr_ui.QMessageBox.information'):
                dialog.return_value.exec.return_value=QDialog.DialogCode.Accepted
                dialog.return_value.items=[('main.png',b'main'),('reserve.png',b'reserve')]
                page.load()
            self.assertEqual(set(cache['images']),{0,1}); self.assertEqual(len(answers),112+count)
            self.assertEqual(unpack(page.records[1],1)[2][0].number,'R1')
            page.page.setCurrentIndex(1); page.filter.setCurrentIndex(1)
            self.assertEqual(page.choose_page(),1); self.assertEqual(page.table.rowCount(),9)
            if count: self.assertEqual(answers[112],'B')
            else: self.assertIn('no puntúan',page.count.text())
            page.deleteLater(); self.app.processEvents()

    def test_mobile_reusable_dialog_accumulates_until_finish(self):
        from unittest.mock import patch
        from agora.import_ui import ImportDialog
        from PySide6.QtWidgets import QDialog
        from urllib.request import urlopen,Request
        from urllib.parse import quote
        import json
        dlg=ImportDialog(None,('.png',),multiple=True,max_files=20)
        try:
            with patch('agora.import_ui.local_addresses',return_value=['127.0.0.1']): dlg.mobile()
            url=dlg.session.url('127.0.0.1')
            for i in range(2):
                name=f'hoja{i}.png'; req=Request(url+'batch',data=b'abc',headers={'X-Files':quote(json.dumps([[name,3]]))})
                with urlopen(req,timeout=3) as response: self.assertEqual(response.status,200)
                dlg.poll(); self.assertEqual(len(dlg.items),i+1); self.assertEqual(dlg.session.url('127.0.0.1'),url)
                self.assertNotEqual(dlg.result(),QDialog.DialogCode.Accepted)
            self.assertIn('2',dlg.finish_button.text()); dlg.finish_upload()
            self.assertEqual(dlg.result(),QDialog.DialogCode.Accepted); self.assertIsNone(dlg.session)
        finally: dlg.cleanup(); dlg.deleteLater(); self.app.processEvents()

    def test_mobile_connection_routes_and_keeps_link(self):
        from unittest.mock import patch
        from agora.import_ui import ImportDialog
        from urllib.request import urlopen,Request
        from urllib.parse import quote
        import json
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); self.app.processEvents(); w.go('automatic'); m=w.automatic; m.apply_config(); m.install_key(ImportedKey(('B',),()),'prueba.pdf',3); m.next_entry()
            conn=w.mobile_connection; dlg=ImportDialog(m.reader,('.jpg',),multiple=True,max_files=20); dlg.show(); self.app.processEvents()
            try:
                with patch('agora.import_ui.local_addresses',return_value=['127.0.0.1']): dlg.mobile()
                url=conn.session.url('127.0.0.1')
                def send(name):
                    conn.update_route(); token=conn.session.status()['token']; self.assertTrue(token)
                    req=Request(url+'batch',data=b'abc',headers={'X-Destination':token,'X-Files':quote(json.dumps([[name,3]]))})
                    with urlopen(req,timeout=3) as r: self.assertEqual(r.status,200)
                    conn.poll()
                send('hoja.jpg'); self.assertEqual(dlg.items,[('hoja.jpg',b'abc')]); self.assertEqual(dlg.result(),1); self.assertIsNotNone(conn.session)
                self.app.processEvents()
                with patch.object(m.reader,'import_items') as imp:
                    send('reserva.jpg'); imp.assert_called_once_with([('reserva.jpg',b'abc')])
                w.go('library'); w.select_library_tab(1)
                with patch.object(w,'receive_library_items') as imp:
                    send('plantilla.pdf'); imp.assert_called_once_with([('plantilla.pdf',b'abc')])
                w.go('home'); conn.update_route(); self.assertIsNone(conn.session.status()['token']); self.assertEqual(conn.session.url('127.0.0.1'),url)
                w.go('automatic'); m.move_stage(1)
                with patch.object(m,'receive_mobile_key') as imp:
                    send('clave.pdf'); imp.assert_called_once_with([('clave.pdf',b'abc')])
                w.close(); self.assertIsNone(conn.session)
            finally: dlg.cleanup(); conn.close(); dlg.deleteLater(); w.deleteLater(); self.app.processEvents()

    def test_mobile_solution_replace_cancel_preserves_key(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); m=w.manual; m.install_key(ImportedKey(('B',),()),'original.pdf',3)
            with patch('agora.manual.confirm',return_value=False) as ask,patch('agora.manual.extract_key') as read:
                m.receive_mobile_key([('otra.pdf',b'abc')]); ask.assert_called_once(); read.assert_not_called()
            self.assertEqual(m.key,['B']); self.assertEqual(m.key_source,'original.pdf'); w.close(); w.deleteLater(); self.app.processEvents()

    def test_mobile_optical_replacement_cancel_and_new_reserve(self):
        from unittest.mock import patch
        from agora.omr_ui import OpticalPage
        from agora.grading import ExamConfig
        from agora.optical_archive import record
        from agora import omr
        from test_omr import sheet,mark
        a=sheet(); mark(a,0,0,0,(20,40,120)); b=sheet(); mark(b,0,0,1,(20,40,120)); r=sheet(1); mark(r,1,0,2,(20,40,120))
        def result(im,slot):
            marks=omr.scan(im,slot); return (im,im,marks,record(im,im,marks))
        old=result(a,0); new=result(b,0); reserve=result(r,1)
        page=OpticalPage(ExamConfig(questions=120,reserves=9),['']*129,{},lambda:None)
        try:
            page.install(0,*old); self.assertEqual(page.answers[0],'A')
            with patch.object(page,'run_import',return_value=([new],[])),patch('agora.omr_ui.confirm',return_value=False) as ask:
                page.import_items([('replacement.png',b'abc')]); ask.assert_called_once()
            self.assertEqual(page.answers[0],'A'); self.assertIs(page.images[0],a)
            with patch.object(page,'run_import',return_value=([reserve],[])),patch('agora.omr_ui.confirm') as ask:
                page.import_items([('reserve.png',b'abc')]); ask.assert_not_called()
            self.assertEqual(page.answers[120],'C'); self.assertEqual(page.answers[0],'A')
        finally: page.deleteLater(); self.app.processEvents()

    def test_models_library_and_editor(self):
        from agora.models import PRESETS,ModelLibrary
        from agora.models_ui import ModelEditor
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('library'); w.library_buttons[2].click(); self.app.processEvents()
            self.assertEqual(w.library_tabs.currentIndex(),2); self.assertEqual(w.models_page.presets.count(),4)
            lib=ModelLibrary(d); mid=lib.save(PRESETS[0]); w.models_page.refresh(); self.assertEqual(w.models_page.custom.count(),1)
            dlg=ModelEditor(w,PRESETS[0]); dlg.show(); self.app.processEvents(); self.assertTrue(dlg.data); self.assertEqual(len(dlg.pages),2)
            dlg.change_page(1); self.assertEqual(dlg.counter.text(),'2 / 2'); dlg.fields['questions'].setValue(40); dlg.fields['reserves'].setValue(0); dlg.refresh(); self.assertEqual(len(dlg.pages),1)
            dlg.reject(); dlg.deleteLater(); w.close(); w.deleteLater(); self.app.processEvents()

    def test_delete_one_optical_page_and_preserve_other(self):
        from unittest.mock import patch
        from agora.omr_ui import OpticalPage
        from agora.grading import ExamConfig
        from agora.omr import Mark, WIDTH, HEIGHT
        from agora.optical_archive import unpack
        import numpy as np
        im=np.full((HEIGHT,WIDTH,3),255,np.uint8)
        def mark(n): return Mark(n,'A','Azul detectado',(100,0,0),(0,0,0),(10,10,70,30))
        for mixed in (False,True):
            answers=['']*4; cache={}; changed=[]; page=OpticalPage(ExamConfig(questions=2,reserves=2),answers,cache,lambda:changed.append(True))
            ordinary=[mark('1'),mark('2')]; reserves=[mark('R1'),mark('R2')]
            page.install(0,im,im,ordinary+reserves if mixed else ordinary)
            if not mixed: page.install(1,im,im,reserves)
            answers[:]=['B','X','C','A']; before=dict(page.records)
            with patch('agora.omr_ui.confirm',return_value=False): page.delete_page(1)
            self.assertEqual(page.records,before); self.assertEqual(answers,['B','X','C','A']); self.assertFalse(changed)
            with patch('agora.omr_ui.confirm',return_value=True): page.delete_page(1)
            self.assertEqual(answers,['B','X','','']); self.assertEqual(list(page.marks),[0]); self.assertEqual([m.number for m in unpack(page.records[0],0)[2]],['1','2']); self.assertEqual(len(changed),1)
            page.install(1,im,im,reserves); answers[2:]=['B','C']
            with patch('agora.omr_ui.confirm',return_value=True): page.delete_page(0)
            self.assertEqual(answers,['','','B','C']); self.assertEqual(list(page.images),[1]); self.assertEqual(list(page.aligned),[1]); self.assertEqual(list(page.records),[1]); page.deleteLater()
        self.app.processEvents()

    def test_model_consult_is_read_only_and_named_color(self):
        from agora.models import PRESETS
        from agora.models_ui import ModelEditor
        from PySide6.QtWidgets import QLineEdit,QSpinBox,QComboBox
        dlg=ModelEditor(None,PRESETS[0],read_only=True)
        self.assertTrue(dlg.data); self.assertEqual(dlg.model(),PRESETS[0]); self.assertFalse(dlg.findChildren(QSpinBox)); self.assertFalse(dlg.findChildren(QComboBox))
        for k in ('name','title','questions','reserves','options','columns','size','margin','shape','orientation'):
            self.assertIsInstance(dlg.fields[k],QLineEdit); self.assertTrue(dlg.fields[k].isReadOnly())
        for k in ('header','logo','stripe','notes','separate'): self.assertFalse(dlg.fields[k].isEnabled())
        self.assertEqual(dlg.color_button.text(),'Rosa Ágora'); self.assertIn('#A55379',dlg.color_button.styleSheet()); self.assertTrue(dlg.export_button.isEnabled()); dlg.deleteLater(); self.app.processEvents()

    def test_external_library_review_and_mobile_destination(self):
        from agora.external_models import ExternalLibrary,learn_items,propose_starts
        from agora.external_ui import ReviewDialog
        from agora.models import PRESETS,pdf_bytes
        from PySide6.QtCore import Qt
        m=PRESETS[-1]; items=[('blank.pdf',pdf_bytes(m))]; pages=learn_items(items,m.options); propose_starts(pages,m.questions)
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('library'); w.select_library_tab(2); self.app.processEvents()
            dest=w.mobile_connection.destination(); self.assertEqual(dest[0],('library',2)); self.assertIn('.png',dest[2]); self.assertEqual(dest[3],20)
            lib=ExternalLibrary(d); dlg=ReviewDialog(w,'Modelo externo',pages,m.questions,m.reserves,m.options,items,lib); dlg.show(); self.app.processEvents()
            self.assertEqual(dlg.table.rowCount(),1); self.assertEqual(dlg.table.item(0,3).text(),'1'); dlg.checked.setChecked(True); dlg.save(); self.assertIsNotNone(dlg.saved_id)
            w.models_page.refresh(); self.assertEqual(w.models_page.external.count(),1); self.assertEqual(w.models_page.presets.count(),4)
            from agora.external_ui import get_library
            self.assertEqual(get_library(w.models_page).entries()[0][0],dlg.saved_id)
            section=w.models_page.external_section; self.assertFalse(section.expanded); section.header.click(); section.anim.setCurrentTime(section.anim.duration()); self.assertTrue(section.expanded); self.assertGreater(section.viewport.height(),0); self.app.processEvents(); self.assertGreaterEqual(section.viewport.height(),section.content.height()); section.header.click(); section.anim.setCurrentTime(section.anim.duration()); self.assertFalse(section.expanded); self.assertEqual(section.viewport.height(),0)
            view=ReviewDialog(w,'Modelo externo',pages,m.questions,m.reserves,m.options,[],lib,True); self.assertFalse(bool(view.table.item(0,3).flags() & Qt.ItemFlag.ItemIsEditable)); view.reject(); dlg.deleteLater(); view.deleteLater(); w.close(); w.deleteLater(); self.app.processEvents()

    def test_blank_model_import_only_in_library(self):
        from PySide6.QtWidgets import QPushButton
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('automatic'); p=w.automatic
            p.install_key(ImportedKey(tuple('ABC'),()),'prueba.pdf',3); p.move_stage(2); self.app.processEvents()
            self.assertFalse(any(b.text()=='Importar modelo en blanco' for b in p.content.findChildren(QPushButton)))
            self.assertTrue(any(b.text()=='Importar modelo en blanco' for b in w.models_page.findChildren(QPushButton)))
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_template_search_filters_without_changing_exam(self):
        from dataclasses import asdict
        from agora.grading import ExamConfig
        with tempfile.TemporaryDirectory() as d:
            storage=Storage(d)
            for name in ('Psicología tema 24','Tema 57','Otra'):
                storage.save_template(name,{'config':asdict(ExamConfig(name=name,questions=2,reserves=0)),'key':['A','B']})
            w=MainWindow(storage); w.show(); w.go('manual'); p=w.manual; p.refresh_templates()
            before=list(p.key); p.template_search.setText('psicologia 24'); self.assertEqual(p.templates_combo.count(),2); self.assertEqual(p.key,before)
            p.template_search.setText('inexistente'); self.assertEqual(p.templates_combo.count(),1); p.template_search.clear(); self.assertEqual(p.templates_combo.count(),4)
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_model_range_validation(self):
        from agora.models_ui import ModelSpinBox
        from PySide6.QtGui import QValidator
        w=ModelSpinBox(1,500,120)
        self.assertEqual(w.validate('501',3)[0],QValidator.State.Intermediate); self.assertEqual(w.validate('0',1)[0],QValidator.State.Intermediate)
        self.assertEqual(w.validate('500',3)[0],QValidator.State.Acceptable); self.assertEqual(w.value(),120)

    def test_home_phrases_and_renamed_module(self):
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); first=w.greeting.text(); w.refresh_home(); self.assertNotEqual(first,w.greeting.text()); self.assertEqual(w.nav['errors'].text(),'Repasar respuestas'); w.close(); w.deleteLater(); self.app.processEvents()
