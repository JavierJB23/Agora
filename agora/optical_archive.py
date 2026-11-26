"""Lossless snapshots of the images and exact crops used for each optical reading."""
import hashlib
import json
from dataclasses import asdict
from io import BytesIO
import numpy as np
from PIL import Image
from .omr import Mark, WIDTH, HEIGHT


def encode(im):
    b=BytesIO(); Image.fromarray(im).save(b,format='PNG',compress_level=3); return b.getvalue()


def record(im,aligned,marks):
    original=encode(im); normalized=encode(aligned)
    metadata=json.dumps([asdict(m) for m in marks],ensure_ascii=False,separators=(',',':'))
    digest=hashlib.sha256()
    for part in (original,normalized,metadata.encode('utf-8')):
        digest.update(len(part).to_bytes(8,'big')); digest.update(part)
    return (digest.hexdigest(),original,normalized,metadata)


def unpack(row,slot):
    _,original,normalized,metadata=row
    with Image.open(BytesIO(original)) as im: original=np.array(im.convert('RGB'))
    with Image.open(BytesIO(normalized)) as im: normalized=np.array(im.convert('RGB'))
    marks=[Mark(m['number'],m['suggestion'],m['status'],tuple(m['scores']),tuple(m['red']),tuple(m['crop']),tuple(tuple(float(v) for v in pt) for pt in m.get('quad',())),m.get('number_check','')) for m in json.loads(metadata)]
    import re
    if normalized.shape!=(HEIGHT,WIDTH,3) or not 1<=len(marks)<=600: raise ValueError('Imagen guardada no válida.')
    seen=set()
    for m in marks:
        x,y,x2,y2=m.crop
        if not re.fullmatch(r'R?[1-9][0-9]{0,2}',m.number) or m.number in seen or not (0<=x<x2<=WIDTH and 0<=y<y2<=HEIGHT) or not 2<=len(m.scores)==len(m.red)<=5: raise ValueError('Recorte guardado no válido.')
        if m.quad:
            import cv2 as cv
            q=np.asarray(m.quad,np.float32)
            if q.shape!=(4,2) or not np.isfinite(q).all() or np.any(q<0) or np.any(q[:,0]>=WIDTH) or np.any(q[:,1]>=HEIGHT) or not cv.isContourConvex(q) or cv.contourArea(q)<4: raise ValueError('Geometría guardada no válida.')
        if m.number_check not in ('','OCR','sequence','geometry','unavailable'): raise ValueError('Verificación OCR guardada no válida.')
        seen.add(m.number)
    return original,normalized,marks
