import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QFont
from agora.storage import Storage
from agora.ui import MainWindow

def main():
    app=QApplication(sys.argv); app.setApplicationName('Ágora'); app.setOrganizationName('Agora'); app.setStyle('Fusion'); app.setFont(QFont('Segoe UI',10))
    try:
        w=MainWindow(Storage()); w.show()
    except Exception as exc:
        QMessageBox.critical(None,'Ágora — Error de inicio',str(exc)); return 1
    return app.exec()

if __name__=='__main__': sys.exit(main())
