import re
import unittest
from unittest.mock import patch
from io import BytesIO
from agora import answer_import as ai

class Fix05Tests(unittest.TestCase):
    def make_image(self, missing=False):
        from reportlab.pdfgen import canvas
        from agora.omr import decode
        import cv2 as cv
        b=BytesIO(); c=canvas.Canvas(b,pagesize=(595,842)); c.setFont('Helvetica',12)
        c.drawString(70,775,'Respuestas correctas simulacro 19')
        letters='ABC'*15
        for i,v in enumerate(letters):
            col=i//15; row=i%15
            c.drawString(85+165*col,710-row*19,f'{i+1}. '+('' if missing and i==2 else v.lower()))
        c.drawString(395,405,'Preguntas de reserva:')
        for i,v in enumerate('CAB'): c.drawString(415,380-i*19,f'{i+1}. {v.lower()}')
        c.showPage(); c.save()
        return cv.cvtColor(decode('key.pdf',b.getvalue())[0],cv.COLOR_RGB2GRAY)

    def run_omission(self, missing=False):
        from agora.number_ocr import engine
        if not engine()[0]: self.skipTest('Motor OCR no disponible')
        im=self.make_image(missing); real=ai._ocr_image; hits=[]
        def ocr(gray,psm=6,whitelist=None):
            text=real(gray,psm,whitelist)
            if psm==6 and whitelist and '0123456789' in whitelist and re.search(r'(?m)^1\.',text):
                # Reproduce the Windows OCR omission reported in compilation 94.
                text,n=re.subn(r'(?m)^3\.[^\n]*$', '3.',text)
                hits.append(n)
            return text
        with patch.object(ai,'_ocr_image',side_effect=ocr):
            if missing:
                with self.assertRaises(ValueError): ai._column_ocr(im,'Respuestas correctas simulacro 19\ntexto defectuoso')
            else:
                k=ai.parse_pages([ai._column_ocr(im,'Respuestas correctas simulacro 19\ntexto defectuoso')])
                self.assertEqual(''.join(k.ordinary),'ABC'*15)
                self.assertEqual(''.join(k.reserves),'CAB')
        self.assertGreater(sum(hits),0)

    def test_windows_omitted_letter_recovered_from_pixels(self):
        self.run_omission()

    def test_missing_printed_letter_is_not_invented(self):
        self.run_omission(missing=True)
