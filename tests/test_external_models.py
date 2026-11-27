import tempfile,unittest
from dataclasses import replace
import numpy as np
import cv2 as cv
from agora.external_models import (ExternalLibrary,learn_items,metadata,propose_starts,manual_block,Page,Block,detect_blocks,preview)
from agora.models import PRESETS,pdf_bytes

class ExternalTests(unittest.TestCase):
    def test_generated_examples(self):
        for m in PRESETS:
            with self.subTest(model=m.name):
                pages=learn_items([(m.name+'.pdf',pdf_bytes(m))],m.options)
                propose_starts(pages,m.questions)
                meta=metadata(pages,m.questions,m.reserves,m.options)
                self.assertEqual(sum(len(b['rows']) for p in meta['pages'] for b in p['blocks']),m.questions+m.reserves)
                self.assertEqual(meta['options'],m.options)
    def test_color_and_shapes(self):
        for shape,color in [('circle','#315C83'),('square','#A55379'),('oval','#237C56')]:
            m=replace(PRESETS[1],questions=40,reserves=0,shape=shape,color=color)
            pages=learn_items([('blank.pdf',pdf_bytes(m))],m.options); propose_starts(pages,m.questions)
            metadata(pages,m.questions,0,m.options)
    def test_storage_roundtrip_and_duplicate(self):
        m=PRESETS[0]; data=pdf_bytes(m); items=[('blank.pdf',data)]
        pages=learn_items(items,3); propose_starts(pages,120)
        with tempfile.TemporaryDirectory() as d:
            lib=ExternalLibrary(d); mid=lib.save('Original',items,pages,120,9,3)
            reopened=ExternalLibrary(d); self.assertEqual(reopened.files(mid,'original'),items)
            self.assertEqual(len(reopened.files(mid,'reference')),2)
            self.assertEqual(reopened.entries()[0][3],metadata(pages,120,9,3))
            with self.assertRaises(ValueError): lib.save('Duplicado',items,pages,120,9,3)
            reopened.rename(mid,'Nuevo'); self.assertEqual(lib.entries()[0][1],'Nuevo')
            lib.delete(mid); self.assertFalse(lib.entries()); self.assertFalse(lib.files(mid,'reference'))
    def test_missing_and_duplicate_labels(self):
        im=np.full((500,500,3),255,np.uint8)
        b=manual_block([(40,50),(120,50),(120,150),(40,150)],5,3,'1'); p=Page(im,[b],'test')
        metadata([p],5,0,3)
        with self.assertRaises(ValueError): metadata([p],6,0,3)
        b2=manual_block([(200,50),(280,50),(280,150),(200,150)],5,3,'1')
        with self.assertRaises(ValueError): metadata([Page(im,[b,b2],'test')],10,0,3)
        b2.start='6'; metadata([Page(im,[b,b2],'test')],10,0,3)
        b.start='6'
        with self.assertRaises(ValueError): metadata([Page(im,[b,b2],'test')],10,0,3)
    def test_single_row_and_overlapping_geometry(self):
        im=np.full((500,500,3),255,np.uint8); a=manual_block([(40,50),(120,50)],1,3,'1'); b=manual_block([(40,50),(120,50)],1,3,'R1')
        metadata([Page(im,[a],'test')],1,0,3)
        with self.assertRaises(ValueError): metadata([Page(im,[a,b],'test')],1,1,3)
        with self.assertRaises(ValueError): manual_block([(120,50),(40,50)],1,3,'1')
    def test_preview_nonmutating(self):
        im=np.full((500,500,3),255,np.uint8); a=manual_block([(40,50),(120,50)],1,3,'1'); p=Page(im,[a],'test')
        self.assertFalse(np.array_equal(preview(p),im)); self.assertTrue(np.all(im==255))
