import sys
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory


def create_app():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont
    app = QApplication([sys.argv[0]])
    app.setApplicationName('Ágora')
    app.setOrganizationName('Agora')
    app.setStyle('Fusion')
    app.setFont(QFont('Segoe UI', 10))
    return app


def smoke_test(report):
    """Exercise the bundled EXE itself, with disposable data and no dialogs."""
    try:
        report.write_text('START\n', encoding='utf-8')
        import numpy as np
        import cv2 as cv
        from PIL import Image
        from pypdf import PdfWriter
        from io import BytesIO
        from agora import omr
        from agora.storage import Storage
        from agora.ui import MainWindow
        app = create_app()
        with TemporaryDirectory() as folder:
            w = MainWindow(Storage(folder))
            w.show()
            app.processEvents()
            w.go('automatic')
            app.processEvents()
            im = np.full((omr.HEIGHT, omr.WIDTH, 3), 250, np.uint8)
            for _, xs, y in omr.locations(0):
                for x in xs:
                    cv.circle(im, (x, y), 10, (60, 60, 60), 2)
            _, xs, y = next(iter(omr.locations(0)))
            x = xs[1]
            cv.line(im, (x-7, y-7), (x+7, y+7), (20, 40, 120), 3)
            cv.line(im, (x-7, y+7), (x+7, y-7), (20, 40, 120), 3)
            buf = BytesIO()
            Image.fromarray(im).save(buf, format='PNG')
            images = omr.decode('test.png', buf.getvalue())
            marks = omr.scan(omr.align(images[0]), 0)
            if len(marks) != 120 or marks[0].suggestion != 'B':
                raise RuntimeError('Prueba de lectura OMR incorrecta')
            pdf = PdfWriter()
            pdf.add_blank_page(width=595, height=842)
            buf = BytesIO()
            pdf.write(buf)
            if len(omr.decode('test.pdf', buf.getvalue())) != 1:
                raise RuntimeError('Prueba de render PDF incorrecta')
            w.go('home')
            w.close()
            app.processEvents()
        report.write_text('OK\nNumPy '+np.__version__+'\nOpenCV '+cv.__version__+'\nQt, ventana, OMR PNG y PDF: OK\n', encoding='utf-8')
        return 0
    except Exception:
        report.write_text(traceback.format_exc(), encoding='utf-8')
        return 1


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        return smoke_test(Path(sys.argv[2]))
    app = create_app()
    from PySide6.QtWidgets import QMessageBox
    try:
        from agora.storage import Storage
        from agora.ui import MainWindow
        w = MainWindow(Storage())
        w.show()
    except Exception as exc:
        QMessageBox.critical(None, 'Ágora — Error de inicio', str(exc))
        return 1
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
