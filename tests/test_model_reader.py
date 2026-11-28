import tempfile,unittest
from dataclasses import replace
from unittest.mock import patch
import cv2 as cv
import numpy as np
from agora import omr
from agora.grading import ExamConfig
from agora.models import PRESETS,ModelLibrary,pdf_bytes
from agora.external_models import ExternalLibrary,learn_items,suggest_numbering
from agora.model_reader import ModelReader,own_references,qr_code,classify
from agora.optical_archive import record,unpack


def cross(im,cell,color=(20,40,130)):
    x,y,w,h=cell; a=round(x-w*.25); b=round(x+w*.25); c=round(y-h*.25); d=round(y+h*.25)
    cv.line(im,(a,c),(b,d),color,2); cv.line(im,(a,d),(b,c),color,2)


def perspective(im):
    h,w=im.shape[:2]; src=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
    dst=np.float32([[.04*w,.04*h],[.96*w,.01*h],[.98*w,.97*h],[.02*w,.98*h]])
    return cv.warpPerspective(im,cv.getPerspectiveTransform(src,dst),(w,h),borderValue=(235,235,230))

class ModelReaderTests(unittest.TestCase):
    def test_own_presets_printed_id_and_geometry(self):
        reader=ModelReader()
        for model in PRESETS:
            for ref in own_references(model):
                with self.subTest(key=ref.key):
                    im=ref.image.copy(); cross(im,ref.rows[0][1][1]); im=perspective(im)
                    self.assertEqual(qr_code(im)[0],ref.key)
                    result=reader.match(im,model.options); self.assertIsNotNone(result)
                    r,a,marks=result; self.assertEqual([m.number for m in marks],[n for n,_ in ref.rows]); self.assertEqual(omr.proposed(marks[0]),'B')
                    self.assertGreaterEqual(sum(omr.proposed(m)=='-' for m in marks[1:]),len(marks)-2)
    def test_custom_landscape_and_archive(self):
        model=replace(PRESETS[1],name='Personalizado',orientation='landscape',questions=20,options=5,columns=2,color='#315C83')
        with tempfile.TemporaryDirectory() as d:
            ModelLibrary(d).save(model); ref=next(own_references(model)); im=ref.image.copy(); cross(im,ref.rows[0][1][4]); reader=ModelReader(d)
            a,marks=reader.read(im,ExamConfig(questions=20,reserves=5,options=5))
            self.assertEqual(omr.proposed(marks[0]),'E'); self.assertEqual(marks[0].model_name,model.name)
            self.assertEqual(unpack(record(im,a,marks),0)[2],marks)
    def test_external_reference_and_reversed_reserves(self):
        model=replace(PRESETS[0],questions=18,reserves=6,columns=2); data=pdf_bytes(model)
        pages=learn_items([('model.pdf',data)],3); q,r=suggest_numbering(pages,18,6)
        for page in pages: page.image[round(page.image.shape[0]*.86):]=255
        with tempfile.TemporaryDirectory() as d:
            ExternalLibrary(d).save('Externo',[('model.pdf',data)],pages,q,r,3); reader=ModelReader(d)
            refs=list(reader.external()); self.assertEqual(len(refs),2)
            for ref in reversed(refs):
                im=ref.image.copy() # external reference has no QR
                # Treat as a learned external design, independent of QR detection.
                cross(im,ref.rows[0][1][0]);
                with patch('agora.model_reader.qr_code',return_value=('',None)):
                    result=reader.match(im,3)
                self.assertIsNotNone(result); self.assertEqual(result[2][0].number,ref.rows[0][0]); self.assertEqual(omr.proposed(result[2][0]),'A')
    def test_blank_red_double_black_and_cancel(self):
        ref=next(own_references(PRESETS[3])); im=ref.image.copy()
        cross(im,ref.rows[0][1][0]); cross(im,ref.rows[0][1][1]); cross(im,ref.rows[1][1][0],(150,20,20)); cross(im,ref.rows[2][1][0],(20,20,20))
        cells=ref.rows[3][1]; x,y,w,h=cells[0]; x2=cells[-1][0]; cv.line(im,(round(x-w*.45),round(y)),(round(x2+w*.45),round(y)),(165,20,20),3)
        marks=classify(ref,im); self.assertEqual(omr.proposed(marks[0]),''); self.assertEqual(omr.proposed(marks[1]),''); self.assertEqual(omr.proposed(marks[2]),''); self.assertEqual(omr.proposed(marks[3]),''); self.assertIn('Posible anulada',marks[3].status); self.assertEqual(omr.proposed(marks[4]),'-')
    def test_unknown_and_invalid_fall_back(self):
        im=np.full((700,500,3),255,np.uint8); config=ExamConfig(questions=20,reserves=0)
        for key in ['', 'AGORA1:0000000000000000:1:1']:
            with patch('agora.model_reader.qr_code',return_value=(key,None)),patch('agora.omr.automatic_page',return_value=('universal',[])) as old:
                self.assertEqual(ModelReader().read(im,config),('universal',[])); old.assert_called_once()
    def test_learned_reader_fallback_preserves_possible_annulment(self):
        ref=next(own_references(PRESETS[3])); ref.key=''; im=ref.image; raw=classify(ref,im)
        doubtful=[replace(m,status='Tinta dudosa · revisar') for m in raw]
        doubtful[0]=replace(doubtful[0],status='Posible anulada · tachadura roja · revisar')
        config=ExamConfig(questions=20,reserves=0)
        reader=ModelReader()
        with patch.object(reader,'match',return_value=(ref,im,doubtful)),patch('agora.number_ocr.verify',return_value=(doubtful,0,0,[])),patch('agora.omr.automatic_page',return_value=(im,raw)) as old:
            _,marks=reader.read(im,config); old.assert_called_once()
            self.assertIn('Posible anulada',marks[0].status); self.assertEqual(omr.proposed(marks[0]),''); self.assertEqual(omr.proposed(marks[1]),'-')
        with patch.object(reader,'match',return_value=(ref,im,raw)),patch('agora.number_ocr.verify',return_value=(raw,0,0,[])),patch('agora.omr.automatic_page') as old:
            _,marks=reader.read(im,config); old.assert_not_called(); self.assertEqual(marks[0].model_name,ref.name)

    def test_qr_is_not_enough(self):
        ref=next(own_references(PRESETS[0])); im=ref.image.copy(); im[200:1450]=255
        self.assertEqual(qr_code(im)[0],ref.key); self.assertIsNone(ModelReader().match(im,3))
