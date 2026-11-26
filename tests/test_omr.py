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

class CurvedCircleTests(unittest.TestCase):
    def test_independent_columns_with_curvature(self):
        im=np.full((omr.HEIGHT,omr.WIDTH,3),250,np.uint8)
        expected=[]
        for i,(_,xs,y) in enumerate(omr.locations(0)):
            col,row=divmod(i,30)
            pts=[(x+int((col-1)*8+row*col*.35), y+int(12*np.sin(row/29*np.pi)*col/3+col*3)) for x in xs]
            expected.append(pts)
            for x,yy in pts: cv.circle(im,(x,yy),10,(60,60,60),2)
            if i in (0,32,75,91,119):
                x,yy=pts[1]; cv.line(im,(x-7,yy-7),(x+7,yy+7),(20,40,120),3); cv.line(im,(x-7,yy+7),(x+7,yy-7),(20,40,120),3)
        fitted=omr.local_circle_positions(im)
        self.assertLessEqual(np.max(abs(np.array([p for _,p in fitted])-np.array(expected))),5)
        ans=[omr.proposed(m) for m in omr.scan(im,0)]
        self.assertEqual([i for i,v in enumerate(ans) if v=='B'],[0,32,75,91,119])
        self.assertEqual(ans.count('-'),115)

class OutlineAlignmentTests(unittest.TestCase):
    def test_fourth_column_shift_and_different_pitch(self):
        """Four complete columns, but the last is displaced and the page is curved."""
        im=np.full((omr.HEIGHT,omr.WIDTH,3),225,np.uint8)
        expected=[]; marked={0:'A',28:'C',30:'B',60:'A',90:'A',91:'C',94:'B',103:'A',119:'C'}
        for i,(_,xs,y) in enumerate(omr.locations(0)):
            c,r=divmod(i,30)
            center=xs[1]+(7,12,16,24)[c]+(0,3,7,5)[c]*r/29
            start=(373,382,380,371)[c]; end=(1546,1544,1542,1545)[c]
            yy=start+(end-start)*r/29+(.025,-.03,-.04,.035)[c]*r*(r-29)
            pts=[(round(center+(j-1)*35),round(yy+(j-1)*(-1.5 if c==3 else .5))) for j in range(3)]
            expected.append(pts)
            cv.line(im,(pts[0][0]-75,round(yy+19)),(pts[-1][0]+20,round(yy+19)),(170,170,170),1)
            for j,(x,y0) in enumerate(pts):
                cv.circle(im,(x,y0),10,(65,65,65),2)
                cv.putText(im,'ABC'[j],(x-4,y0+4),cv.FONT_HERSHEY_SIMPLEX,.30,(70,70,70),1,cv.LINE_AA)
            if i in marked:
                x,y0=pts['ABC'.index(marked[i])]
                cv.line(im,(x-7,y0-7),(x+7,y0+7),(20,40,120),3)
                cv.line(im,(x-7,y0+7),(x+7,y0-7),(20,40,120),3)
        fitted=omr.grid_positions(im,0)
        self.assertLessEqual(np.max(abs(np.array([p for _,p in fitted])-np.array(expected))),5)
        ans=[omr.proposed(m) for m in omr.scan(im,0)]
        self.assertEqual({i:v for i,v in enumerate(ans) if v!='-'},marked)

    def test_missing_column_is_not_a_valid_main_sheet(self):
        im=sheet(); im[:,900:]=250
        with self.assertRaises(ValueError): omr.grid_positions(im,0)

    def test_four_columns_of_squares_not_mistaken_for_circles(self):
        im=np.full((omr.HEIGHT,omr.WIDTH,3),250,np.uint8)
        for x0 in (125,385,645,905):
            for r in range(30):
                y=350+r*36
                cv.rectangle(im,(x0,y-17),(x0+180,y+17),(60,60,60),2)
                for j in range(4):
                    x=x0+45+j*35
                    cv.rectangle(im,(x-10,y-10),(x+10,y+10),(50,50,50),2)
        with self.assertRaises(ValueError): omr.grid_positions(im,0)
        self.assertEqual([(len(m),len(m[0].scores)) for _,m in omr.square_blocks(im)],[(30,4)]*4)

class SquarePreviewTests(unittest.TestCase):
    def test_unrotated_canvas_and_horizontal_crops(self):
        from agora.optical_archive import record,unpack
        im=square_sheet()
        view,blocks=omr.square_page(im)
        self.assertTrue(np.array_equal(view,im))
        marks=omr.number_blocks(blocks,['1','11'])
        self.assertEqual(omr.proposed(marks[0]),'C')
        self.assertTrue(all(len(m.quad)==4 for m in marks))
        crop=omr.crop_image(view,marks[0]); self.assertGreater(crop.shape[1],crop.shape[0]*3)
        self.assertEqual(unpack(record(im,view,marks),0)[2],marks)

    def test_fallback_keeps_photo_and_maps_row_coordinates(self):
        from unittest.mock import patch
        im=square_sheet(); blocks=omr.square_blocks(im)
        # Simulate the detector requiring a projective alignment, with a known offset.
        original=np.roll(im,20,axis=0); corners=omr.full_corners(im)+np.float32([[0,20]]*4)
        with patch.object(omr,'square_blocks',side_effect=[ValueError('raw'),blocks]),patch.object(omr,'detect_corners',return_value=corners):
            view,mapped=omr.square_page(original,im)
        self.assertTrue(np.array_equal(view,original))
        old=blocks[0][1][0]; new=mapped[0][1][0]
        np.testing.assert_allclose(np.array(new.quad),np.array(old.quad)+[0,20],atol=.01)
        self.assertEqual(omr.proposed(new),omr.proposed(old))
        np.testing.assert_array_equal(omr.crop_image(view,new),omr.crop_image(im,old))

    def test_archive_without_row_geometry_remains_readable(self):
        import json
        from agora.optical_archive import record,unpack
        im=sheet(); marks=omr.scan(im,0)
        digest,original,view,metadata=record(im,im,marks)
        values=json.loads(metadata)
        for m in values: m.pop('quad')
        self.assertEqual(unpack((digest,original,view,json.dumps(values)),0)[2],marks)

class GuidedPreviewTests(unittest.TestCase):
    def test_guided_rows_have_individual_quads(self):
        im=square_sheet()
        marks=omr.guided_block(im,[(145,300),(250,300),(250,570),(145,570)],10,4,'1')
        self.assertTrue(all(len(m.quad)==4 for m in marks))
        self.assertEqual(omr.proposed(marks[0]),'C')
        crop=omr.crop_image(im,marks[0]); self.assertGreater(crop.shape[1],crop.shape[0]*3)
        from agora.optical_archive import record,unpack
        self.assertEqual(unpack(record(im,im,marks),0)[2],marks)


class ManualColumnAndStrikeTests(unittest.TestCase):
    def test_reject_full_page_as_one_block(self):
        im=sheet()
        with self.assertRaisesRegex(ValueError,'sola columna'):
            omr.guided_block(im,[(205,359),(1047,359),(1047,1497),(205,1497)],30,3,'1')

    def test_group_and_replace_one_column_only(self):
        im=sheet(); marks=omr.scan(im,0); blocks=omr.reading_blocks(marks)
        self.assertEqual([len(b) for b in blocks],[30]*4)
        block=blocks[1]; loc=list(omr.locations(0)); _,xs,y=loc[30]; _,last_xs,last_y=loc[59]
        new=omr.guided_block(im,[(xs[0],y),(xs[-1],y),(last_xs[-1],last_y),(last_xs[0],last_y)],30,3,'31')
        merged=omr.replace_reading_block(marks,block,new)
        self.assertEqual(merged[:30],marks[:30]); self.assertEqual(merged[60:],marks[60:]); self.assertEqual(merged[30:60],new)
        wrong=omr.guided_block(im,[(loc[0][1][0],y),(loc[0][1][-1],y),(loc[29][1][-1],last_y),(loc[29][1][0],last_y)],30,3,'31')
        with self.assertRaisesRegex(ValueError,'solapa'): omr.replace_reading_block(marks,block,wrong)

    def test_red_strike_requires_review_not_red_cross(self):
        im=sheet()
        for q in (11,12,117):
            mark(im,0,q,1,(20,40,120)); _,xs,y=list(omr.locations(0))[q]
            cv.line(im,(xs[0]-17,y),(xs[-1]+17,y+2),(145,115,120),2)
        mark(im,0,1,1,(20,40,120)); mark(im,0,1,2,(160,20,30))
        marks=omr.scan(im,0)
        self.assertEqual([m.number for m in marks if 'Posible anulada' in m.status],['12','13','118'])
        self.assertTrue(all(omr.proposed(marks[q])=='' for q in (11,12,117)))
        self.assertEqual(omr.proposed(marks[1]),'B')

    def test_square_strike_and_grouping(self):
        im=square_sheet(); blocks=omr.square_blocks(im); marks=omr.number_blocks(blocks,['1','11'])
        cv.line(im,(133,330),(262,330),(140,100,105),2)
        marks=omr.flag_strikes(im,marks)
        self.assertEqual([len(b) for b in omr.reading_blocks(marks)],[10,10]); self.assertIn('Posible anulada',marks[1].status)
        self.assertEqual(omr.proposed(marks[1]),''); self.assertEqual(omr.proposed(marks[0]),'C')

class AutomaticColorTests(unittest.TestCase):
    def test_colored_known_template_and_red_stroke(self):
        im=np.full((omr.HEIGHT,omr.WIDTH,3),255,np.uint8)
        for i,(_,xs,y) in enumerate(omr.locations(0)):
            if i%2: cv.rectangle(im,(xs[0]-55,y-18),(xs[-1]+30,y+18),(255,222,234),-1)
            for j,x in enumerate(xs):
                cv.circle(im,(x,y),10,(200,55,130),2)
                cv.putText(im,'ABC'[j],(x-4,y+4),cv.FONT_HERSHEY_SIMPLEX,.3,(200,55,130),1,cv.LINE_AA)
        mark(im,0,0,1,(20,40,120)); mark(im,0,11,1,(20,40,120))
        _,xs,y=list(omr.locations(0))[11]; cv.line(im,(xs[0]-17,y),(xs[-1]+17,y),(145,115,120),2)
        _,marks=omr.automatic_page(im,120,0,3)
        self.assertEqual(omr.proposed(marks[0]),'B')
        self.assertEqual([m.number for m in marks if 'Posible anulada' in m.status],['12'])
        self.assertEqual([omr.proposed(m) for m in marks].count('-'),118)

    def test_new_blue_layout_not_fixed_coordinates(self):
        im=np.full((omr.HEIGHT,omr.WIDTH,3),250,np.uint8)
        for c,bx in enumerate([150,550,925]):
            for r in range(20):
                y=200+r*45
                cv.putText(im,str(c*20+r+1),(bx-65,y+5),cv.FONT_HERSHEY_SIMPLEX,.45,(60,110,150),1)
                for j in range(3):
                    x=bx+j*35; cv.circle(im,(x,y),10,(95,165,230),2)
                    if r==5 and j==1:
                        cv.line(im,(x-7,y-7),(x+7,y+7),(20,40,120),3)
                        cv.line(im,(x-7,y+7),(x+7,y-7),(20,40,120),3)
        _,marks=omr.automatic_page(im,60,0,3)
        self.assertEqual(len(marks),60)
        self.assertEqual([(m.number,omr.proposed(m)) for m in marks if omr.proposed(m)!='-'],[('6','B'),('26','B'),('46','B')])

    def test_square_auto_numbering_without_dialog(self):
        im=square_sheet(); _,marks=omr.automatic_page(im,20,0,3)
        self.assertEqual([m.number for m in marks],list(map(str,range(1,21))))
        self.assertEqual([omr.proposed(marks[i]) for i in (0,10)],['C','C'])
        self.assertTrue(all(len(m.scores)==4 for m in marks))

    def test_auto_numbering_rejects_unmapped_partial_page(self):
        blocks=omr.square_blocks(square_sheet())
        with self.assertRaises(ValueError): omr.automatic_numbering(blocks,30,0)
        self.assertEqual([m.number for m in omr.automatic_numbering(blocks,18,0)],list(map(str,range(1,21))))
        # Only a separate short block at the configured boundary is inferred as reserves.
        reserves=[blocks[0],(blocks[1][0],blocks[1][1][:3])]
        self.assertEqual(omr.automatic_numbering(reserves,10,3)[-1].number,'R3')

class RepeatedPrintedRowsTests(unittest.TestCase):
    def test_scaled_colored_rows_preserve_crossed_row_indices(self):
        im=np.full((omr.HEIGHT,omr.WIDTH,3),240,np.uint8)
        for col in range(4):
            bx=280+col*200
            for r in range(30):
                x=bx-round(r*.35); y=420+r*30+round(.003*r*r)+col%2*4
                if r%2: cv.rectangle(im,(x-70,y-13),(x+65,y+13),(238,217,225),-1)
                cv.putText(im,str(col*30+r+1),(x-65,y+4),cv.FONT_HERSHEY_SIMPLEX,.4,(135,60,100),1,cv.LINE_AA)
                for j in range(3):
                    cx=x+j*26; cv.circle(im,(cx,y),8,(135,60,100),2); cv.putText(im,'ABC'[j],(cx-3,y+3),cv.FONT_HERSHEY_SIMPLEX,.25,(135,60,100),1)
                    if j==r%3: cv.line(im,(cx-5,y-5),(cx+5,y+5),(30,40,105),2); cv.line(im,(cx+5,y-5),(cx-5,y+5),(30,40,105),2)
                if r==4: cv.line(im,(x-65,y),(x+62,y+2),(40,55,125),2)
            cv.rectangle(im,(bx-70,390+col%2*4),(bx+70,407+col%2*4),(135,60,100),-1)
        pts=omr.repeated_circle_rows(im); marks=omr.scan_repeated_rows(im,pts)
        self.assertEqual([m.number for m in marks],list(map(str,range(1,121))))
        self.assertEqual([m.number for m in marks if 'Posible anulada' in m.status],['5','35','65','95'])
        self.assertEqual(omr.proposed(marks[0]),'A'); self.assertEqual(omr.proposed(marks[1]),'B'); self.assertEqual(omr.proposed(marks[2]),'C')

class VerifiedNumberingTests(unittest.TestCase):
    def test_header_cannot_be_accepted_as_answer(self):
        im=np.full((omr.HEIGHT,omr.WIDTH,3),240,np.uint8)
        cv.rectangle(im,(100,300),(220,325),(130,40,90),-1)
        m=omr.Mark('1','A','Azul detectado',(30,0,0),(0,0,0),(100,300,220,325))
        with self.assertRaisesRegex(ValueError,'cabecera'):
            omr.verify_numbered_rows(im,[m])

    def test_header_anchors_allow_column_specific_heights(self):
        im=np.full((omr.HEIGHT,omr.WIDTH,3),240,np.uint8)
        for col in range(4):
            bx=260+col*200; y0=390+col*19
            cv.rectangle(im,(bx-70,y0-28),(bx+68,y0-12),(135,60,100),-1)
            for r in range(30):
                y=y0+r*30; x=bx
                if r%2: cv.rectangle(im,(x-70,y-12),(x+65,y+12),(238,217,225),-1)
                cv.putText(im,str(col*30+r+1),(x-65,y+4),cv.FONT_HERSHEY_SIMPLEX,.4,(135,60,100),1,cv.LINE_AA)
                for j in range(3):
                    cx=x+j*26; cv.circle(im,(cx,y),8,(135,60,100),2)
                    cv.putText(im,'ABC'[j],(cx-3,y+3),cv.FONT_HERSHEY_SIMPLEX,.25,(135,60,100),1)
                    if j==r%3:
                        cv.line(im,(cx-5,y-5),(cx+5,y+5),(30,40,105),2); cv.line(im,(cx+5,y-5),(cx-5,y+5),(30,40,105),2)
                if r in (4,23): cv.line(im,(x-65,y),(x+62,y+2),(40,55,125),2)
        pos=omr.repeated_circle_rows(im); ms=omr.scan_repeated_rows(im,pos)
        omr.verify_numbered_rows(im,ms)
        self.assertEqual([m.number for m in ms],list(map(str,range(1,121))))
        self.assertEqual([m.number for m in ms if 'Posible anulada' in m.status],['5','24','35','54','65','84','95','114'])
        self.assertTrue(all(omr.proposed(m)=='ABC'[i%30%3] for i,m in enumerate(ms) if i%30 not in (4,23)))
