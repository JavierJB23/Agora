import unittest
from dataclasses import replace
from unittest.mock import patch
import cv2 as cv
import numpy as np
from agora import omr,number_ocr
from agora.optical_archive import record,unpack


def numbers(start=31,prefix=''):
    im=np.full((omr.HEIGHT,omr.WIDTH,3),255,np.uint8); marks=[]
    for j in range(10):
        y=100+j*45
        cv.putText(im,prefix+str(start+j),(82,y+8),cv.FONT_HERSHEY_SIMPLEX,.8,(0,0,0),2)
        marks.append(omr.Mark(str(j+1),'A','Azul detectado',(50,0,0),(0,0,0),(160,y-19,260,y+19)))
    return im,marks


class NumberOCRTests(unittest.TestCase):
    def test_consistent_real_numbering(self):
        _,marks=numbers()
        result,n,changed,conflicts=number_ocr.reconcile(marks,[marks],{j:(str(j+31),96) for j in range(10)})
        self.assertEqual([m.number for m in result],[str(j+31) for j in range(10)])
        self.assertEqual((n,changed,conflicts),(10,10,[])); self.assertEqual(result[0].number_check,'OCR')
        self.assertEqual([omr.proposed(m) for m in result],['A']*10)

    def test_weak_or_missing_ocr_keeps_geometry(self):
        _,marks=numbers(); result,n,changed,conflicts=number_ocr.reconcile(marks,[marks],{0:('31',96),1:('32',99)})
        self.assertEqual([m.number for m in result],[m.number for m in marks]); self.assertEqual(changed,0)
        self.assertTrue(all(m.number_check=='geometry' for m in result))

    def test_missing_reserve_prefix_does_not_convert_to_ordinary(self):
        _,marks=numbers(); marks=[replace(m,number='R'+m.number) for m in marks]
        result,_,changed,_=number_ocr.reconcile(marks,[marks],{j:(str(j+1),99) for j in range(10)})
        self.assertEqual(changed,0); self.assertTrue(all(m.number.startswith('R') for m in result))

    def test_conflicting_sequences(self):
        _,marks=numbers(); labels={j:(str(j+1 if j<5 else j+2),99) for j in range(10)}
        result,n,changed,conflicts=number_ocr.reconcile(marks,[marks],labels)
        self.assertEqual(conflicts,['1']); self.assertEqual(changed,0)

    def test_duplicate_numbers_rejected(self):
        _,marks=numbers(); other=[replace(m,number=str(j+31)) for j,m in enumerate(marks)]
        with self.assertRaises(ValueError): number_ocr.reconcile(marks+other,[marks,other],{j:(str(j%10+31),99) for j in range(20)})

    def test_real_local_engine_and_archive(self):
        if not number_ocr.engine()[0]: self.skipTest('No hay motor OCR instalado en este entorno de desarrollo')
        im,marks=numbers(); actual=number_ocr.read_labels(im,marks)
        self.assertGreaterEqual(sum(v[0]==str(j+31) for j,v in actual.items()),6)
        result,verified,changed,conflicts=number_ocr.reconcile(marks,[marks],actual)
        self.assertEqual([m.number for m in result],[str(j+31) for j in range(10)])
        self.assertEqual(unpack(record(im,im,result),0)[2],result)

    def test_optional_engine_integration(self):
        im,marks=numbers()
        with patch.object(omr,'_automatic_page',return_value=(im,marks)),patch('agora.number_ocr.verify',side_effect=RuntimeError('missing')):
            _,out=omr.automatic_page(im,10,verify_ocr=True)
            self.assertTrue(all(m.number_check=='unavailable' for m in out))
            self.assertEqual([m.number for m in out],[m.number for m in marks])
        with patch.object(omr,'_automatic_page',return_value=(im,marks)),patch('agora.number_ocr.verify',return_value=(marks,0,0,['1'])):
            with self.assertRaises(ValueError): omr.automatic_page(im,10,verify_ocr=True)

    def test_explicit_reserve_prefix_can_identify_new_block(self):
        _,marks=numbers(); result,verified,changed,conflicts=number_ocr.reconcile(marks,[marks],{j:(f'R{j+1}',98) for j in range(10)})
        self.assertEqual([m.number for m in result],[f'R{j+1}' for j in range(10)])
        self.assertEqual((verified,changed,conflicts),(10,10,[]))
