import os, tempfile, unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    HAS_QT=True
except ImportError:
    HAS_QT=False
if HAS_QT:
    from agora.ui import MainWindow
from agora.storage import Storage
from agora.modules import MODULES

@unittest.skipUnless(HAS_QT,'PySide6 no disponible')
class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
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
            for i,v in enumerate('AXBC'): m.choose(i,v)
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
            # Exercise the keyboard handlers via their real QShortcut signals as well as mouse clicks.
            m.shortcuts[0].activated.emit(); self.assertEqual(m.key[0],'A'); self.assertEqual(m.cursor,1)
            m.grid_rows[1][2][1][1].click(); self.assertEqual(m.key[1],'B'); m.next_entry(); self.app.processEvents()
            m.shortcuts[0].activated.emit(); m.shortcuts[3].activated.emit(); self.assertEqual(m.answers,['A','-']); m.next_entry(); self.app.processEvents(); self.assertEqual(m.result.grade,5)
            w.close(); w.deleteLater(); self.app.processEvents()
