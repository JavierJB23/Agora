import unittest
from io import BytesIO
from agora.answer_import import parse_pages, _column_ocr
from agora.mobile_session import mobile_page

class Fix04Tests(unittest.TestCase):
    def test_native_picker_not_three_buttons(self):
        html=mobile_page(); self.assertEqual(html.count('type="file"'),1)
        self.assertIn('Seleccionar archivos',html); self.assertIn('Enviar archivos',html)
        self.assertIn("f.removeAttribute('accept')",html)
        self.assertIn("f.accept=v.extensions.join(',')",html)
        self.assertNotIn('capture=',html)
    def test_columns_reserve_layout(self):
        from agora.number_ocr import engine
        if not engine()[0]: self.skipTest('Motor OCR no disponible')
        from reportlab.pdfgen import canvas
        from agora.omr import decode
        import cv2 as cv
        b=BytesIO(); c=canvas.Canvas(b,pagesize=(595,842)); c.setFont('Helvetica',12)
        c.drawString(70,775,'Respuestas correctas simulacro 19')
        letters='ABC'*15
        for i,v in enumerate(letters):
            col=i//15; row=i%15
            c.drawString(85+165*col,710-row*19,f'{i+1}. {v.lower()}')
        c.drawString(395,405,'Preguntas de reserva:')
        for i,v in enumerate('CAB'): c.drawString(415,380-i*19,f'{i+1}. {v.lower()}')
        c.showPage(); c.save()
        im=cv.cvtColor(decode('key.pdf',b.getvalue())[0],cv.COLOR_RGB2GRAY)
        k=parse_pages([_column_ocr(im,'Respuestas correctas simulacro 19\ntexto defectuoso')])
        self.assertEqual(''.join(k.ordinary),letters); self.assertEqual(''.join(k.reserves),'CAB')
