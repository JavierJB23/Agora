import os, tempfile, unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from agora.ui import MainWindow
    HAS_QT=True
except ImportError:
    HAS_QT=False
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
