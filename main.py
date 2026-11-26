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
            # Exercise the bundled executable and language data, not merely the Python module.
            from agora.number_ocr import recognize
            sample = np.full((120,420),255,np.uint8)
            cv.putText(sample,'123',(50,84),cv.FONT_HERSHEY_SIMPLEX,2,0,3)
            if not any(x[0]=='123' for x in recognize(sample,7)):
                raise RuntimeError('Prueba OCR del motor incluido incorrecta')
            # New reader: four physical cells per row, independent of valid options.
            sq = np.full((omr.HEIGHT, omr.WIDTH, 3), 250, np.uint8)
            for j in range(10):
                y = 300+j*30
                cv.rectangle(sq, (100,y-15), (275,y+15), (40,40,40), 2)
                cv.putText(sq,str(j+1),(104,y+4),cv.FONT_HERSHEY_SIMPLEX,.5,(40,40,40),1)
                for k in range(4):
                    x = 145+k*35
                    cv.rectangle(sq,(x-10,y-10),(x+10,y+10),(40,40,40),2)
                    if j==0 and k==2:
                        cv.line(sq,(x-6,y-6),(x+6,y+6),(20,40,120),2)
                        cv.line(sq,(x-6,y+6),(x+6,y-6),(20,40,120),2)
            square_view,newmarks=omr.automatic_page(sq,10,0,3)
            if len(newmarks)!=10 or len(newmarks[0].scores)!=4 or omr.proposed(newmarks[0])!='C':
                raise RuntimeError('Prueba del lector de cuadrados incorrecta')
            from agora.optical_archive import record,unpack
            if not newmarks[0].quad or omr.crop_image(square_view,newmarks[0]).shape[1]<40:
                raise RuntimeError('Prueba de recorte horizontal incorrecta')
            if unpack(record(sq,square_view,newmarks),0)[2]!=newmarks:
                raise RuntimeError('Prueba de guardado de lectura flexible incorrecta')
            pdf = PdfWriter()
            pdf.add_blank_page(width=595, height=842)
            buf = BytesIO()
            pdf.write(buf)
            if len(omr.decode('test.pdf', buf.getvalue())) != 1:
                raise RuntimeError('Prueba de render PDF incorrecta')
            from agora.answer_import import ImportedKey
            from agora.grading import evaluate
            m=w.automatic; m.install_key(ImportedKey(('B',),()),'test.pdf',3); m.next_entry()
            m.reader.install(0,images[0],omr.align(images[0]),marks); m.optical_changed()
            if m.answers!=['B']: raise RuntimeError('Integración del lector incorrecta')
            m.result=evaluate(m.config,m.key,m.answers); m.move_stage(3)
            if m.result.correct!=1 or not m.save_progress(): raise RuntimeError('Corrección automática incorrecta')
            aid=m.attempt_id
            if not m.start_new() or not m.open_saved(aid): raise RuntimeError('Recuperación del simulacro incorrecta')
            m.move_stage(2)
            if not np.array_equal(m.reader.images[0],images[0]) or m.reader.marks[0]!=marks or m.answers!=['B']: raise RuntimeError('Recuperación de imágenes o respuestas incorrecta')
            w.go('home')
            w.close()
            app.processEvents()
        report.write_text('OK\nNumPy '+np.__version__+'\nOpenCV '+cv.__version__+'\nQt, ventana, OMR círculos y cuadrados, OCR local, PNG y PDF: OK\n', encoding='utf-8')
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
