import unittest, tempfile, zipfile
from io import BytesIO
from fractions import Fraction
from agora.grading import ExamConfig, evaluate, change_answer, restore_answer
from agora.answer_import import extract_key,parse_response_list,docx_images,KEY_EXTENSIONS
from agora.storage import Storage
from agora.mobile_session import mobile_page
from agora.omr import RESPONSE_EXTENSIONS

class Fix03Tests(unittest.TestCase):
    def test_reversible_annulments_and_saved_reserves(self):
        c=ExamConfig(questions=120,reserves=9)
        key=['A']*129; answers=['A']*119+['B']+['A','B']+['C']*7; before=answers.copy(); originals={}
        initial=evaluate(c,key,answers)
        self.assertEqual((initial.correct,initial.wrong,initial.reserve_used,initial.effective),(119,1,0,120))
        change_answer(answers,originals,119,'X'); change_answer(answers,originals,0,'X')
        r=evaluate(c,key,answers)
        self.assertEqual((r.reserve_used,r.effective),(2,120)); self.assertEqual(r.rows[120].replaces,'1'); self.assertEqual(r.rows[121].replaces,'120')
        with tempfile.TemporaryDirectory() as d:
            from dataclasses import asdict
            s=Storage(d); aid=s.save_attempt(dict(mode='manual',config=asdict(c),key=key,answers=answers,annul_originals=originals,stage=3,corrected=True)); saved=s.load_attempt(aid)
            self.assertEqual(saved['annul_originals'],{'119':'B','0':'A'})
            for i in (0,119): self.assertTrue(restore_answer(saved['answers'],saved['annul_originals'],i))
            self.assertEqual(saved['answers'],before); self.assertEqual(evaluate(c,key,saved['answers']),initial)
    def test_blank_restores_and_original_not_overwritten(self):
        a=['-','B']; original={}; change_answer(a,original,0,'X'); change_answer(a,original,0,'X'); self.assertEqual(original,{'0':'-'}); self.assertTrue(restore_answer(a,original,0)); self.assertEqual(a,['-','B'])
        change_answer(a,original,1,'X'); change_answer(a,original,1,'C'); self.assertEqual(original,{})
        self.assertFalse(restore_answer(['X'],{},0))
    def test_word_list_reserves_and_blanks(self):
        c=ExamConfig(questions=3,reserves=2)
        self.assertEqual(parse_response_list(['Respuestas\n1 A, 2 En blanco, 3 C\nR1 B R2 Anulada'],c),{0:'A',1:'-',2:'C',3:'B',4:'X'})
        self.assertEqual(parse_response_list(['4B 5A'],c),{3:'B',4:'A'})
        for text in ('1 A 1 B','1 D','6 A','1 A un texto','R3 C'):
            with self.subTest(text=text),self.assertRaises(ValueError): parse_response_list([text],c)
    def test_word_embedded_scan_order(self):
        from PIL import Image
        from agora.omr import decode
        img=BytesIO(); Image.new('RGB',(60,80),'white').save(img,format='PNG'); b=BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p r:embed="rId2"/><w:p r:embed="rId1"/></w:body></w:document>')
            z.writestr('word/_rels/document.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/one.png"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/two.png"/></Relationships>')
            for name in ('one','two'): z.writestr('word/media/'+name+'.png',img.getvalue())
        self.assertEqual([n for n,_ in docx_images(b.getvalue())],['word/media/two.png','word/media/one.png']); self.assertEqual(len(decode('answers.docx',b.getvalue())),2)
    def test_photo_key_and_archive(self):
        from unittest.mock import patch
        from PIL import Image
        b=BytesIO(); Image.new('RGB',(120,100),'white').save(b,format='PNG'); data=b.getvalue()
        with patch('agora.answer_import.ocr_text',return_value='1 A\n2 B\nR1 C'):
            self.assertEqual(extract_key(data,'soluciones.png').key,['A','B','C'])
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); ref=s.archive_solution_document('soluciones.png',data); self.assertEqual(s.load_solution_document(ref),('soluciones.png',data)); self.assertEqual(s.library_entries(),[])
    def test_local_ocr_photo(self):
        from agora.number_ocr import engine
        if not engine()[0]: self.skipTest('Motor OCR no disponible')
        from reportlab.pdfgen import canvas
        from agora.omr import decode
        from PIL import Image
        pdf=BytesIO(); c=canvas.Canvas(pdf,pagesize=(500,450)); c.setFont('Helvetica',32)
        for i,line in enumerate(('1 A','2 B','3 C','R1 A','R2 B')): c.drawString(90,380-i*60,line)
        c.showPage(); c.save(); image=Image.fromarray(decode('clave.pdf',pdf.getvalue())[0]); buf=BytesIO(); image.save(buf,format='PNG')
        self.assertEqual(extract_key(buf.getvalue(),'clave.png').key,['A','B','C','A','B'])
    def test_mobile_pickers_and_extensions(self):
        p=mobile_page()
        for x in ('id="camera"','id="photos"','id="file"','capture="environment"','PDF, Word o fotos','Tiempo agotado','Móvil desconectado'): self.assertIn(x,p)
        self.assertEqual(set(KEY_EXTENSIONS),set(RESPONSE_EXTENSIONS)); self.assertNotIn('id="camera" type="file" multiple',p)
