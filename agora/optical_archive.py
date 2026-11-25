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
    marks=[Mark(m['number'],m['suggestion'],m['status'],tuple(m['scores']),tuple(m['red']),tuple(m['crop'])) for m in json.loads(metadata)]
    if normalized.shape!=(HEIGHT,WIDTH,3) or len(marks)!=(120 if slot==0 else 9): raise ValueError('Imagen guardada no válida.')
    for j,m in enumerate(marks):
        x,y,x2,y2=m.crop
        if m.number!=('' if slot==0 else 'R')+str(j+1) or not (0<=x<x2<=WIDTH and 0<=y<y2<=HEIGHT): raise ValueError('Recorte guardado no válido.')
    return original,normalized,marks
