import unittest
import numpy as np
import cv2 as cv
from io import BytesIO
from PIL import Image
from agora import omr

def sheet(page=0):
    im=np.full((omr.HEIGHT,omr.WIDTH,3),250,np.uint8)
    for _,xs,y in omr.locations(page):
        for x in xs: cv.circle(im,(x,y),10,(60,60,60),2)
    return im

def mark(im,page,q,option,color):
    _,xs,y=list(omr.locations(page))[q]; x=xs[option]; cv.line(im,(x-7,y-7),(x+7,y+7),color,3); cv.line(im,(x-7,y+7),(x+7,y-7),color,3)
class OpticalTests(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(len(list(omr.locations(0))),120); self.assertEqual(len(list(omr.locations(1))),9)
    def test_blue_red_and_blank(self):
        im=sheet(); mark(im,0,0,1,(20,40,120)); mark(im,0,0,2,(160,20,30)); m=omr.scan(im,0); self.assertEqual(m[0].suggestion,'B'); self.assertIn('rojo',m[0].status); self.assertEqual(m[1].suggestion,'')
    def test_double(self):
        im=sheet(); mark(im,0,0,0,(20,40,120)); mark(im,0,0,1,(20,40,120)); self.assertEqual(omr.scan(im,0)[0].status,'Doble o dudosa')
    def test_black_not_guessed(self):
        im=sheet(); mark(im,0,0,0,(10,10,10)); self.assertEqual(omr.scan(im,0)[0].suggestion,'')
    def test_reserves(self):
        im=sheet(1); mark(im,1,8,2,(20,40,120)); self.assertEqual(omr.scan(im,1)[8].suggestion,'C')
    def test_reject_empty(self):
        with self.assertRaises(ValueError): omr.scan(np.full((omr.HEIGHT,omr.WIDTH,3),255,np.uint8),0)
    def test_decode_and_alignment(self):
        im=sheet(); b=BytesIO(); Image.fromarray(im).save(b,format='PNG'); pages=omr.decode('test.png',b.getvalue()); self.assertEqual(len(pages),1); self.assertEqual(omr.align(pages[0]).shape,im.shape)
        with self.assertRaises(ValueError): omr.align(im,[(0,0)]*4)

    def test_identify_reversed_and_shifted_reserve(self):
        reserve=sheet(1); shifted=cv.warpAffine(reserve,np.float32([[1,0,-5],[0,1,-14]]),(omr.WIDTH,omr.HEIGHT),borderValue=(250,250,250))
        self.assertEqual(omr.identify(shifted),1); self.assertEqual(omr.identify(sheet(0)),0)
        pts=omr.reserve_positions(shifted)
        for (_,xy),(_,xs,y) in zip(pts,omr.locations(1)):
            for (x2,y2),x in zip(xy,xs): self.assertLessEqual(abs(x2-(x-5)),3); self.assertLessEqual(abs(y2-(y-14)),3)
        self.assertEqual([omr.proposed(m) for m in omr.scan(shifted,1)],['-']*9)

    def test_proposals_clear_ambiguous_blank(self):
        im=sheet(); mark(im,0,0,1,(20,40,120)); mark(im,0,1,0,(20,40,120)); mark(im,0,1,1,(20,40,120)); mark(im,0,3,1,(160,20,30))
        m=omr.scan(im,0); self.assertEqual([omr.proposed(x) for x in m[:4]],['B','','-',''])

    def test_shifted_main_grid_preserves_rows(self):
        im=sheet(); mark(im,0,0,1,(20,40,120)); mark(im,0,29,2,(20,40,120)); mark(im,0,30,0,(20,40,120)); mark(im,0,119,2,(20,40,120))
        shifted=cv.warpAffine(im,np.float32([[1,0,10],[0,1,8]]),(omr.WIDTH,omr.HEIGHT),borderValue=(250,250,250))
        self.assertEqual(omr.identify(shifted),0)
        positions=omr.centers(shifted,0)
        for (_,pts),(_,xs,y) in zip(positions,omr.locations(0)):
            for (x2,y2),x in zip(pts,xs): self.assertLessEqual(abs(x2-x-10),4); self.assertLessEqual(abs(y2-y-8),4)
        ans=[omr.proposed(m) for m in omr.scan(shifted,0)]
        self.assertEqual([ans[i] for i in (0,29,30,119)],['B','C','A','C']); self.assertEqual(ans.count('-'),116)

    def test_manual_grid_anchors_with_crop_and_perspective(self):
        for slot,qidx in ((0,59),(1,8)):
            im=sheet(slot); mark(im,slot,qidx,2,(20,40,120))
            src=omr.grid_anchors(slot)
            dst=src+np.float32([[22,18],[-15,12],[-9,-13],[17,-10]]) if slot==0 else src+np.float32([[15,5],[-9,7],[-9,7],[15,5]])
            transform=cv.getPerspectiveTransform(src,dst)
            photo=cv.warpPerspective(im,transform,(omr.WIDTH,omr.HEIGHT),borderValue=(250,250,250))
            corrected=omr.align_grid(photo,slot,dst)
            self.assertEqual(omr.identify(corrected),slot)
            answers=[omr.proposed(x) for x in omr.scan(corrected,slot)]
            self.assertEqual(answers[qidx],'C'); self.assertEqual(answers.count('-'),len(answers)-1)
    def test_manual_grid_invalid_order(self):
        with self.assertRaises(ValueError): omr.align_grid(sheet(),0,omr.grid_anchors(0)[[0,2,1,3]])


def square_sheet():
    im=np.full((omr.HEIGHT,omr.WIDTH,3),250,np.uint8)
    for bx in (100,350):
        for j in range(10):
            y=300+j*30
            cv.rectangle(im,(bx,y-15),(bx+175,y+15),(40,40,40),2)
            cv.putText(im,str(j+1),(bx+4,y+4),cv.FONT_HERSHEY_SIMPLEX,.5,(40,40,40),1)
            for k in range(4):
                x=bx+45+k*35
                cv.rectangle(im,(x-10,y-10),(x+10,y+10),(40,40,40),2)
                if j==0 and k==2:
                    cv.line(im,(x-6,y-6),(x+6,y+6),(20,40,120),2)
                    cv.line(im,(x-6,y+6),(x+6,y-6),(20,40,120),2)
    return im

class FlexibleTests(unittest.TestCase):
    def test_square_detection_and_same_page_reserves(self):
        im=square_sheet(); blocks=omr.square_blocks(im)
        self.assertEqual([(len(m),len(m[0].scores)) for _,m in blocks],[(10,4),(10,4)])
        marks=omr.number_blocks(blocks,['1','R-1'])
        self.assertEqual([m.number for m in marks[:11]],list(map(str,range(1,11)))+['R1'])
        self.assertEqual([omr.proposed(marks[i]) for i in (0,10)],['C','C'])
        self.assertEqual(sum(omr.proposed(m)=='-' for m in marks),18)
        with self.assertRaises(ValueError): omr.number_blocks(blocks,['1','5'])
    def test_guided_block_rectangles_and_archive(self):
        from agora.optical_archive import record,unpack
        im=square_sheet(); marks=omr.guided_block(im,[(145,300),(250,300),(250,570),(145,570)],10,4,'21')
        self.assertEqual(marks[0].number,'21'); self.assertEqual(omr.proposed(marks[0]),'C'); self.assertEqual(marks[-1].number,'30')
        original,aligned,restored=unpack(record(im,im,marks),4)
        self.assertTrue(np.array_equal(original,im)); self.assertEqual(marks,restored)
    def test_many_pdf_pages(self):
        from pypdf import PdfWriter
        w=PdfWriter()
        for i in range(3): w.add_blank_page(595,842)
        b=BytesIO(); w.write(b); self.assertEqual(len(omr.decode('test.pdf',b.getvalue())),3)
