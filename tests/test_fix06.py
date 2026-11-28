import re
import unittest
from unittest.mock import patch
from io import BytesIO
from agora import answer_import as ai

class Fix06Tests(unittest.TestCase):
    def make_image(self, missing_number=False, missing_letter=False):
        from agora.number_ocr import engine
        if not engine()[0]: self.skipTest('Motor OCR no disponible')
        from reportlab.pdfgen import canvas
        from agora.omr import decode
        import cv2 as cv
        b=BytesIO(); c=canvas.Canvas(b,pagesize=(595,842)); c.setFont('Helvetica',12)
        c.drawString(70,775,'Respuestas correctas simulacro 19')
        for i,v in enumerate('ABC'*15):
            col=i//15; row=i%15
            n='' if missing_number and i==0 else str(i+1)
            letter='' if missing_letter and i==2 else v.lower()
            c.drawString(85+165*col,710-row*19,f'{n}. {letter}')
        c.drawString(395,405,'Preguntas de reserva:')
        for i,v in enumerate('CAB'): c.drawString(415,380-i*19,f'{i+1}. {v.lower()}')
        c.showPage(); c.save()
        return cv.cvtColor(decode('key.pdf',b.getvalue())[0],cv.COLOR_RGB2GRAY)

    def check(self, mode, missing_number=False, missing_letter=False, no_digits_ocr=False):
        im=self.make_image(missing_number,missing_letter); real=ai._ocr_image; hits=[]
        expected=['\n'.join(f'{i+1}. {v.lower()}' for i,v in enumerate('ABC'*15) if i//15==col) for col in range(3)]
        expected.append('1. c\n2. a\n3. b')
        # Inject the exact reported Windows variants independent of OCR version.
        def ocr(gray,psm=6,whitelist=None):
            if psm==6 and whitelist=='0123456789.ABCDEXabcdeRr ':
                idx=len(hits); hits.append(idx); lines=expected[idx].splitlines()
                if mode=='number':
                    for j in (0,len(lines)//2): lines[j]=re.sub(r'^\d+','',lines[j])
                elif mode=='both':
                    lines[0]='.'; lines[-1]=re.sub(r'\s+[a-e]$','',lines[-1])
                elif mode=='merged' and idx==3: lines.pop(1)
                elif mode=='missing_letter' and idx==0: lines[2]='3.'
                return '\n'.join(lines)
            if no_digits_ocr and whitelist=='0123456789.Rr-': return ''
            return real(gray,psm,whitelist)
        with patch.object(ai,'_ocr_image',side_effect=ocr):
            if missing_number or missing_letter or no_digits_ocr:
                with self.assertRaises(ValueError): ai._column_ocr(im,'Respuestas correctas simulacro 19\ntexto defectuoso')
            else:
                k=ai.parse_pages([ai._column_ocr(im,'Respuestas correctas simulacro 19\ntexto defectuoso')]); self.assertEqual(''.join(k.ordinary),'ABC'*15); self.assertEqual(''.join(k.reserves),'CAB')
        self.assertTrue(hits)

    def test_windows_missing_number_including_first_and_reserve(self): self.check('number')
    def test_both_fields_missing_from_ocr(self): self.check('both')
    def test_ocr_omitted_entire_line(self): self.check('merged')
    def test_number_not_printed(self): self.check('number',missing_number=True)
    def test_letter_not_printed(self): self.check('missing_letter',missing_letter=True)
    def test_visible_but_unreadable_number_not_inferred(self): self.check('number',no_digits_ocr=True)
