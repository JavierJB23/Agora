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
            m.name.setText('Prueba 3'); m.n.setValue(3); m.r.setValue(1); m.apply_config(); self.app.processEvents()
            self.assertEqual(m.stage,1)
            m.install_key(ImportedKey(tuple('AXB'),('C',)),'prueba.pdf',3)
            m.next_entry(); self.app.processEvents(); self.assertEqual(m.stage,2)
            for i,v in enumerate('AB-C'): m.choose(i,v)
            m.next_entry(); self.app.processEvents(); self.assertEqual(m.stage,3)
            self.assertEqual((m.result.correct,m.result.blank,m.result.reserve_used),(2,1,1)); self.assertEqual(m.table.rowCount(),4)
            m.filter.setCurrentIndex(3); self.assertEqual(m.table.rowCount(),1)
            w.close(); w.deleteLater(); self.app.processEvents()
            w2=MainWindow(Storage(d)); w2.show(); w2.go('manual'); self.app.processEvents(); self.assertEqual(w2.manual.stage,3); self.assertEqual(w2.manual.result.correct,2)
            w2.manual.move_stage(2); self.app.processEvents(); w2.manual.choose(0,'B'); w2.manual.next_entry(); self.app.processEvents(); self.assertEqual(w2.manual.result.wrong,1)
            w2.close(); w2.deleteLater(); self.app.processEvents()
    def test_manual_keyboard(self):
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('manual'); self.app.processEvents(); m=w.manual
            m.n.setValue(2); m.r.setValue(0); m.apply_config(); self.app.processEvents(); m.focus_entry(); self.app.processEvents()
            m.install_key(ImportedKey(('C','C'),()),'prueba.pdf',3); self.app.processEvents()
            # Exercise the keyboard handlers via their real QShortcut signals as well as mouse clicks.
            m.shortcuts[0].activated.emit(); self.assertEqual(m.key[0],'A'); self.assertEqual(m.cursor,1)
            m.grid_rows[1][2][1][1].click(); self.assertEqual(m.key[1],'B'); m.next_entry(); self.app.processEvents()
            m.shortcuts[0].activated.emit(); m.shortcuts[3].activated.emit(); self.assertEqual(m.answers,['A','-']); m.next_entry(); self.app.processEvents(); self.assertEqual(m.result.grade,5)
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_direct_steps_and_current_result(self):
        with tempfile.TemporaryDirectory() as d:
            w=MainWindow(Storage(d)); w.show(); w.go('manual'); self.app.processEvents(); m=w.manual
            m.n.setValue(2); m.r.setValue(0); m.step_labels[1].click()
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
            m.templates_combo.setCurrentIndex(1); m.name.setText('Borrador sin confirmar'); seen=[]
            def inspect():
                dlg=self.app.activeModalWidget()
                if isinstance(dlg,QDialog):
                    table=dlg.findChild(QTableWidget)
                    if table: seen.extend((table.rowCount(),table.item(1,1).text(),table.item(2,0).text()))
                    dlg.accept()
            QTimer.singleShot(0,inspect); m.view_template()
            self.assertEqual(seen,[3,'Anulada','R1']); self.assertEqual(m.name.text(),'Borrador sin confirmar'); self.assertIsNone(storage.load_draft()); self.assertEqual(len(storage.templates()),1)
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_saved_progress_and_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); w=MainWindow(s); w.show(); w.go('manual'); m=w.manual
            m.name.setText('Parcial'); m.n.setValue(2); m.r.setValue(0); m.apply_config(); m.install_key(ImportedKey(('A','B'),()),'prueba.pdf',3); m.next_entry(); m.choose(0,'A')
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
            click('Salir sin guardar'); self.assertTrue(ORIGINAL_LEAVE(m)); self.assertEqual(w.storage.load_draft()['form']['name'],'Sin guardar')
            click('Continuar'); self.assertTrue(ORIGINAL_ENTER(m)); self.assertEqual(m.name.text(),'Sin guardar')
            click('Iniciar uno nuevo'); self.assertTrue(ORIGINAL_ENTER(m)); self.assertFalse(m.active()); self.assertIsNone(w.storage.load_draft())
            w.close(); w.deleteLater(); self.app.processEvents()
