import unittest,tempfile
import numpy as np
from dataclasses import asdict
from agora.grading import ExamConfig
from agora.omr import Mark,WIDTH,HEIGHT
from agora.optical_archive import record,unpack,remove_page_kind
from agora.storage import Storage

class PageRemovalTests(unittest.TestCase):
    def make_cache(self,mixed):
        im=np.full((HEIGHT,WIDTH,3),255,np.uint8)
        def mark(n): return Mark(n,'A','Azul detectado',(100,0,0),(0,0,0),(10,10,70,30))
        a=[mark('1'),mark('2')]; b=[mark('R1'),mark('R2')]; marks={0:a+b} if mixed else {0:a,1:b}
        return dict(images={i:im for i in marks},aligned={i:im for i in marks},marks=marks,records={i:record(im,im,ms) for i,ms in marks.items()})
    def test_remove_reserve_and_save_roundtrip(self):
        for mixed in (False,True):
            c=ExamConfig(questions=2,reserves=2); a=['B','X','C','A']; cache=self.make_cache(mixed); old=cache['records'][0]
            self.assertTrue(remove_page_kind(cache,a,c,0 if mixed else 1,True)); self.assertEqual(a,['B','X','','']); self.assertEqual(set(cache['images']),{0}); self.assertEqual(set(cache['records']),{0}); self.assertEqual([m.number for m in unpack(cache['records'][0],0)[2]],['1','2'])
            if not mixed: self.assertEqual(old,cache['records'][0])
            with tempfile.TemporaryDirectory() as d:
                s=Storage(d); payload={'config':asdict(c),'key':['A']*4,'answers':a,'optical_pages':{'0':cache['records'][0][0]}}
                s.save_draft(payload,'automatic',cache['records'].values()); saved=s.load_draft('automatic'); self.assertEqual(saved['answers'],a); self.assertEqual([m.number for m in unpack(s.load_optical_page(saved['optical_pages']['0']),0)[2]],['1','2'])
    def test_remove_ordinary_and_keep_reserves_without_solution(self):
        c=ExamConfig(questions=2,reserves=0); a=['B','C']; cache=self.make_cache(True)
        self.assertTrue(remove_page_kind(cache,a,c,0,False)); self.assertEqual(a,['','']); self.assertEqual([m.number for m in unpack(cache['records'][0],0)[2]],['R1','R2']); self.assertFalse(remove_page_kind(cache,a,c,0,False)); self.assertTrue(remove_page_kind(cache,a,c,0,True)); self.assertTrue(all(not v for v in cache.values()))
