"""Block 05: optical mark proposals for the supplied 120+9 A/B/C layout.
Blue ink is interpreted; clear results are proposed and the set is confirmed before scoring.
"""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import cv2 as cv
import numpy as np
from PIL import Image, ImageOps
import pypdfium2 as pdfium

WIDTH, HEIGHT = 1190,1684
EXTENSIONS=('.pdf','.jpg','.jpeg','.png')
@dataclass(frozen=True)
class Mark:
    number: str
    suggestion: str
    status: str
    scores: tuple[int,int,int]
    red: tuple[int,int,int]
    crop: tuple[int,int,int,int]

def decode(name,data):
    ext=Path(name).suffix.lower()
    if ext not in EXTENSIONS: raise ValueError('Formato no admitido: PDF, JPG o PNG.')
    if ext=='.pdf':
        doc=pdfium.PdfDocument(data)
        try:
            if not 1<=len(doc)<=2: raise ValueError('Importa una o dos páginas de la hoja de respuestas, no el enunciado.')
            result=[]
            for i in range(len(doc)):
                page=doc[i]
                try:
                    w,h=page.get_size(); bitmap=page.render(scale=min(3,2000/max(w,h)))
                    try: result.append(np.array(bitmap.to_pil().convert('RGB')))
                    finally: bitmap.close()
                finally: page.close()
            return result
        finally: doc.close()
    with Image.open(BytesIO(data)) as im:
        if im.width*im.height>60_000_000: raise ValueError('Imagen demasiado grande. Reduce su resolución.')
        im=ImageOps.exif_transpose(im); im.thumbnail((2200,2200)); return [np.array(im.convert('RGB'))]

def full_corners(im):
    h,w=im.shape[:2]; return np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])

def detect_corners(im):
    h,w=im.shape[:2]
    hsv=cv.cvtColor(im,cv.COLOR_RGB2HSV)
    mask=((hsv[:,:,1]<55)&(hsv[:,:,2]>100)).astype('uint8')*255
    k=max(3,round(min(h,w)/70)); mask=cv.morphologyEx(mask,cv.MORPH_CLOSE,np.ones((k,k),np.uint8))
    rows=np.mean(np.min(im,axis=2)>248,axis=1); non=np.flatnonzero(rows<.95)
    if len(non): mask[:non[0]+3]=0; mask[max(0,non[-1]-2):]=0
    contours,_=cv.findContours(mask,cv.RETR_EXTERNAL,cv.CHAIN_APPROX_SIMPLE)
    for ct in sorted(contours,key=cv.contourArea,reverse=True)[:3]:
        if cv.contourArea(ct)<.35*h*w: continue
        q=cv.approxPolyDP(ct,.02*cv.arcLength(ct,True),True).reshape(-1,2).astype('float32')
        if len(q)!=4 or not cv.isContourConvex(q): continue
        q=q[np.argsort(q[:,1])]; top=q[:2][np.argsort(q[:2,0])]; bot=q[2:][np.argsort(q[2:,0])]; q=np.array([top[0],top[1],bot[1],bot[0]],np.float32)
        if min(q[:,0])<.015*w and max(q[:,0])>.985*w and abs(w/h-WIDTH/HEIGHT)<.07: return full_corners(im)
        if np.linalg.norm(q[1]-q[0])>1.1*np.linalg.norm(q[3]-q[0]): continue
        return q
    return full_corners(im)

def align(im,corners=None):
    if min(im.shape[:2])<450: raise ValueError('Resolución insuficiente. Fotografía la hoja completa con mayor nitidez.')
    q=detect_corners(im) if corners is None else np.asarray(corners,dtype=np.float32)
    if q.shape!=(4,2) or not cv.isContourConvex(q) or cv.contourArea(q)<.2*im.shape[0]*im.shape[1]: raise ValueError('Selecciona las cuatro esquinas de la hoja en orden.')
    return cv.warpPerspective(im,cv.getPerspectiveTransform(q,np.float32([[0,0],[WIDTH-1,0],[WIDTH-1,HEIGHT-1],[0,HEIGHT-1]])),(WIDTH,HEIGHT))

def locations(page):
    xs=[102.59,231.83,359.39,489.76] if page==0 else [127.38,300.27,475.04]
    n=30 if page==0 else 3; start=179.55 if page==0 else 63.75
    for col,x in enumerate(xs):
        for row in range(n):
            yield (str(col*n+row+1) if page==0 else 'R'+str(col*n+row+1),[round(2*(x+16.75*j)) for j in range(3)],round(2*(start+19.618*row)))

def reserve_positions(im):
    """Find the 27 printed circles near the reserve grid, then refine each center."""
    g=cv.cvtColor(im,cv.COLOR_RGB2GRAY)
    c=cv.HoughCircles(g[:260],cv.HOUGH_GRADIENT,1,22,param1=80,param2=15,minRadius=7,maxRadius=15)
    if c is None: raise ValueError('No se encuentran los círculos de reserva.')
    found=np.round(c[0,:,:2]).astype(int)
    nominal=np.array([(x,y) for _,xs,y in locations(1) for x in xs],dtype=np.float32)
    # A modest translation from perspective detection is expected. Find consistent unique matches.
    pairs=[]; used=set()
    for i,(x,y) in enumerate(nominal):
        dist=np.linalg.norm(found-[x,y],axis=1)
        j=int(np.argmin(dist))
        if dist[j]<=24 and j not in used: pairs.append((i,j)); used.add(j)
    if len(pairs)<22: raise ValueError('No se reconoce la cuadrícula de reservas.')
    src=np.array([nominal[i] for i,j in pairs]); dst=np.array([found[j] for i,j in pairs],np.float32)
    transform,inliers=cv.estimateAffine2D(src,dst,method=cv.RANSAC,ransacReprojThreshold=5)
    if transform is None or int(inliers.sum())<20: raise ValueError('No se pudo alinear la cuadrícula de reservas.')
    pred=cv.transform(nominal.reshape(-1,1,2),transform).reshape(-1,2)
    if np.max(np.linalg.norm(pred-nominal,axis=1))>30: raise ValueError('Desplazamiento excesivo de las reservas.')
    for i,(x,y) in enumerate(pred):
        dist=np.linalg.norm(found-[x,y],axis=1); j=int(np.argmin(dist))
        if dist[j]<6: pred[i]=found[j]
    return [(n,[tuple(map(int,xy)) for xy in np.round(pred[j*3:j*3+3])]) for j,(n,_,_) in enumerate(locations(1))]

def centers(im,page):
    if page==1: return reserve_positions(im)
    return [(n,[(x,y) for x in xs]) for n,xs,y in locations(0)]

def identify(im):
    """Recognize the supplied template geometry, not arbitrary handwritten numbering."""
    g=cv.cvtColor(im,cv.COLOR_RGB2GRAY)
    c=cv.HoughCircles(g[330:1550],cv.HOUGH_GRADIENT,1.3,22,param1=80,param2=17,minRadius=7,maxRadius=15)
    main=False
    if c is not None:
        found=c[0,:,:2].copy(); found[:,1]+=330
        nominal=np.array([(x,y) for _,xs,y in locations(0) for x in xs])
        main=int(np.sum(np.min(np.linalg.norm(nominal[:,None,:]-found[None,:,:],axis=2),axis=1)<20))>=270
    try: reserve_positions(im); reserve=True
    except ValueError: reserve=False
    if main==reserve: raise ValueError('No se distingue con seguridad la hoja ordinaria de la de reservas. Fotografía la plantilla completa y nítida.')
    return 0 if main else 1

def proposed(mark):
    if mark.suggestion and 'débil' not in mark.status: return mark.suggestion
    if not mark.suggestion and max(mark.scores)<5 and max(mark.red)<=20: return '-'
    return ''

def scan(im,page):
    if page not in (0,1) or im.shape[:2]!=(HEIGHT,WIDTH): raise ValueError('Página no válida.')
    a=im.astype(np.int16); R,G,B=a.transpose(2,0,1)
    blue=(B-R>5)&(B-G>7)&(B<220)&(R<180)
    red=(R-B>18)&(R-G>18)&(G<180)&(B-G<35)&(R<205)
    gray=cv.cvtColor(im,cv.COLOR_RGB2GRAY)
    out=[]; present=0
    for number,points in centers(im,page):
        scores=[]; reds=[]; dark=[]
        for x,y in points:
            r=14; sl=np.s_[y-r:y+r+1,x-r:x+r+1]; scores.append(int(blue[sl].sum())); reds.append(int(red[sl].sum())); g=gray[sl]; dark.append(int((g<min(190,int(np.median(g))-22)).sum()))
        present+=sum(d>12 for d in dark)
        order=sorted(range(3),key=lambda j:scores[j],reverse=True); high,second=order[:2]; s=scores[high]; other=scores[second]
        suggestion='ABC'[high] if s>=15 and other<max(15,.35*s) else ''
        status='Azul detectado' if suggestion else 'Doble o dudosa' if s>=15 else 'Sin azul: revisar blanco u otra tinta'
        if suggestion and s<40: status='Azul débil: revisar'
        if suggestion and max(reds)>20: status+=' · posible rojo'
        out.append(Mark(number,suggestion,status,tuple(scores),tuple(reds),(min(x for x,y in points)-19,min(y for x,y in points)-17,max(x for x,y in points)+19,max(y for x,y in points)+18)))
    if present < len(out)*3*.45: raise ValueError('No se reconoce la distribución de casillas. Comprueba la página y ajusta las cuatro esquinas.')
    return out

def overlay(im,page):
    result=im.copy()
    for _,points in centers(im,page):
        for x,y in points: cv.rectangle(result,(x-14,y-14),(x+14,y+14),(28,167,112),1)
    return result
