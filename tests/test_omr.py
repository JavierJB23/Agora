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
