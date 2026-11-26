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
    scores: tuple[int,...]
    red: tuple[int,...]
    crop: tuple[int,int,int,int]

def decode(name,data):
    ext=Path(name).suffix.lower()
    if ext not in EXTENSIONS: raise ValueError('Formato no admitido: PDF, JPG o PNG.')
    if ext=='.pdf':
        doc=pdfium.PdfDocument(data)
        try:
            if not 1<=len(doc)<=20: raise ValueError('Importa hasta 20 páginas de respuestas, no el enunciado.')
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

def grid_anchors(page):
    rows=list(locations(page)); n=30 if page==0 else 3
    return np.float32([(rows[0][1][0],rows[0][2]),(rows[-n][1][-1],rows[-n][2]),(rows[-1][1][-1],rows[-1][2]),(rows[n-1][1][0],rows[n-1][2])])


def align_grid(im,page,points):
    """Four printed circle centers, not paper corners. Works with cropped margins."""
    q=np.asarray(points,dtype=np.float32); h,w=im.shape[:2]
    if q.shape!=(4,2) or not np.isfinite(q).all() or not cv.isContourConvex(q) or cv.contourArea(q)<h*w*(.07 if page==0 else .002):
        raise ValueError('Marca los centros de los cuatro círculos indicados, en orden.')
    if np.any(q<0) or np.any(q[:,0]>=w) or np.any(q[:,1]>=h) or q[0,0]>=q[1,0] or q[3,0]>=q[2,0] or q[0,1]>=q[3,1] or q[1,1]>=q[2,1]:
        raise ValueError('Comprueba el orden de los cuatro círculos de referencia.')
    if page==1:
        # Three rows occupy a very shallow strip: projective extrapolation is unstable.
        mat=np.linalg.lstsq(np.column_stack([q,np.ones(4)]),grid_anchors(page),rcond=None)[0].T
        if not np.isfinite(mat).all(): raise ValueError('Referencias no válidas.')
        return cv.warpAffine(im,mat,(WIDTH,HEIGHT),borderValue=(255,255,255))
    mat=cv.getPerspectiveTransform(q,grid_anchors(page))
    if not np.isfinite(mat).all(): raise ValueError('Referencias no válidas.')
    return cv.warpPerspective(im,mat,(WIDTH,HEIGHT),borderValue=(255,255,255))


def locations(page):
    xs=[102.59,231.83,359.39,489.76] if page==0 else [127.38,300.27,475.04]
    n=30 if page==0 else 3; start=179.55 if page==0 else 63.75
    for col,x in enumerate(xs):
        for row in range(n):
            yield (str(col*n+row+1) if page==0 else 'R'+str(col*n+row+1),[round(2*(x+16.75*j)) for j in range(3)],round(2*(start+19.618*row)))

def grid_positions(im,page):
    """Fit the printed lattice, not the paper edges, and refine local row positions.
    Reject ambiguous geometry instead of silently reading a neighboring row.
    """
    g=cv.cvtColor(im,cv.COLOR_RGB2GRAY)
    lo,hi=(300,1580) if page==0 else (0,280)
    c=cv.HoughCircles(g[lo:hi],cv.HOUGH_GRADIENT,1,22,param1=80,param2=15,minRadius=7,maxRadius=16)
    if c is None: raise ValueError('No se reconocen los círculos de la hoja.')
    found=c[0,:,:2].astype(np.float32); found[:,1]+=lo
    nominal=np.array([(x,y) for _,xs,y in locations(page) for x in xs],dtype=np.float32)
    def nearest(pred):
        dist=np.linalg.norm(pred[:,None,:]-found[None,:,:],axis=2)
        j=dist.argmin(1); return j,dist[np.arange(len(pred)),j]
    j,d=nearest(nominal)
    close=d<22
    if close.sum()<len(nominal)*.68: raise ValueError('No se reconoce la cuadrícula de la hoja.')
    offset=np.median(found[j[close]]-nominal[close],axis=0)
    pred=nominal+offset
    # Two passes remove local false positives before refining the projective model.
    for radius in (13,9):
        j,d=nearest(pred); pairs=[]; used=set()
        for i in np.argsort(d):
            k=int(j[i])
            if d[i]<=radius and k not in used: pairs.append((i,k)); used.add(k)
        if len(pairs)<len(nominal)*.70: raise ValueError('No se pudo alinear la cuadrícula. Ajusta las esquinas o repite la foto.')
        src=np.array([nominal[i] for i,k in pairs]); dst=np.array([found[k] for i,k in pairs])
        if page==0:
            mat,inliers=cv.findHomography(src,dst,cv.RANSAC,4.0)
            if mat is None or inliers.sum()<len(nominal)*.65: raise ValueError('Alineación de la hoja ordinaria insuficiente.')
            pred=cv.perspectiveTransform(nominal.reshape(-1,1,2),mat).reshape(-1,2)
        else:
            mat,inliers=cv.estimateAffine2D(src,dst,method=cv.RANSAC,ransacReprojThreshold=4)
            if mat is None or inliers.sum()<20: raise ValueError('Alineación de reservas insuficiente.')
            pred=cv.transform(nominal.reshape(-1,1,2),mat).reshape(-1,2)
    if not np.isfinite(pred).all() or np.max(np.linalg.norm(pred-nominal,axis=1))>35:
        raise ValueError('Desplazamiento excesivo. Ajusta las esquinas o repite la foto.')
    j,d=nearest(pred)
    groups=[]
    for row,(n,_,_) in enumerate(locations(page)):
        sl=slice(row*3,row*3+3); pts=pred[sl].copy(); good=d[sl]<6
        # Shift the whole triplet consistently; marked circles can be missing from Hough.
        if good.sum()>=2: pts+=np.median(found[j[sl][good]]-pts[good],axis=0)
        if np.any(np.diff(pts[:,0])<25) or np.any(np.diff(pts[:,0])>43) or np.ptp(pts[:,1])>9:
            raise ValueError('Casillas desalineadas. Ajusta las esquinas o repite la foto.')
        groups.append((n,[tuple(map(int,xy)) for xy in np.round(pts)]))
    return groups

def reserve_positions(im): return grid_positions(im,1)

def centers(im,page): return grid_positions(im,page)

def identify(im):
    """Recognize the supplied template geometry, not arbitrary numbering."""
    matched=[]
    for page in (0,1):
        try: grid_positions(im,page); matched.append(page)
        except ValueError: pass
    if len(matched)!=1: raise ValueError('No se distingue con seguridad la hoja ordinaria de la de reservas. Fotografía la plantilla completa y nítida.')
    return matched[0]

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


def _clusters(values, tolerance):
    groups=[]
    for v in sorted(values):
        if not groups or v-np.median(groups[-1])>tolerance: groups.append([v])
        else: groups[-1].append(v)
    return [(float(np.median(g)),len(g)) for g in groups]


def square_blocks(im):
    """Detect connected printed grids, independently of paper size/position.
    Return one block per column of questions. Numbering must be confirmed externally.
    """
    g=cv.cvtColor(im,cv.COLOR_RGB2GRAY)
    mask=cv.adaptiveThreshold(g,255,cv.ADAPTIVE_THRESH_GAUSSIAN_C,cv.THRESH_BINARY_INV,31,9)
    contours,_=cv.findContours(mask,cv.RETR_LIST,cv.CHAIN_APPROX_SIMPLE)
    blocks=[]
    for c in sorted(contours,key=cv.contourArea,reverse=True):
        x,y,w,h=cv.boundingRect(c)
        if not (65<=w<=WIDTH*.8 and 65<=h<=HEIGHT*.9 and cv.contourArea(c)>.45*w*h): continue
        if any(x>=bx-5 and y>=by-5 and x+w<=bx+bw+5 and y+h<=by+bh+5 for (bx,by,bw,bh),_ in blocks): continue
        q=cv.approxPolyDP(c,.015*cv.arcLength(c,True),True).reshape(-1,2).astype('float32')
        if len(q)!=4 or not cv.isContourConvex(q): continue
        q=q[np.argsort(q[:,1])]; q=np.vstack((q[:2][np.argsort(q[:2,0])],q[2:][np.argsort(q[2:,0])[::-1]]))
        dst=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
        mat=cv.getPerspectiveTransform(q,dst); inv=cv.getPerspectiveTransform(dst,q)
        a=cv.warpPerspective(im,mat,(w,h)); gray=cv.cvtColor(a,cv.COLOR_RGB2GRAY)
        b=cv.adaptiveThreshold(gray,255,cv.ADAPTIVE_THRESH_GAUSSIAN_C,cv.THRESH_BINARY_INV,31,9)
        cs,_=cv.findContours(b,cv.RETR_LIST,cv.CHAIN_APPROX_SIMPLE); pts=[]
        for s in cs:
            xx,yy,ww,hh=cv.boundingRect(s)
            if 8<=ww<=45 and 8<=hh<=45 and .68<ww/hh<1.45 and cv.contourArea(s)/(ww*hh)>.48:
                pts.append((xx+ww/2,yy+hh/2,ww,hh))
        if len(pts)<12: continue
        p=np.array(pts); size=float(np.median(p[:,2:4])); tol=max(4,size*.45)
        # Use the last printed answer column (normally free of question numbers).
        peaks=_clusters(p[:,0],tol)
        peaks=[(v,n) for v,n in peaks if n>=max(4,len(p)*.055)]
        if not 2<=len(peaks)<=7: continue
        # Number labels may form an extra peak. Keep a regular suffix ending at the right edge.
        xs=None
        for k in range(min(5,len(peaks)),1,-1):
            trial=np.array([v for v,n in peaks[-k:]])
            gaps=np.diff(trial); step=float(np.median(gaps))
            if trial[0]>w*.18 and step>=size*.85 and np.max(abs(gaps-step))<step*.23 and w-trial[-1]<step*1.05:
                xs=trial; break
        if xs is None: continue
        last=p[abs(p[:,0]-xs[-1])<max(tol,size*.7)]
        ys=np.array([v for v,n in _clusters(last[:,1],size*.65)])
        if not 3<=len(ys)<=60: continue
        pitch=float(np.median(np.diff(ys)))
        if pitch<size*.85 or np.any(np.diff(ys)<pitch*.55) or np.any(np.diff(ys)>pitch*1.5) or ys[0]>pitch or h-ys[-1]>pitch: continue
        # Refine individual cell centers from contours near the predicted grid.
        rows=[]
        for yy in ys:
            local=[]
            for xx in xs:
                near=p[(abs(p[:,0]-xx)<size*.8)&(abs(p[:,1]-yy)<pitch*.35)]
                px,py=(np.median(near[:,:2],axis=0) if len(near) else (xx,yy))
                local.append((float(px),float(py)))
            rows.append(local)
        marks=[]; rgb=a.astype(np.int16); R,G,B=rgb.transpose(2,0,1)
        blue=(B-R>5)&(B-G>7)&(B<225)&(R<190); red=(R-B>18)&(R-G>18)&(G<180)&(B-G<35)&(R<205)
        for row in rows:
            scores=[]; reds=[]; dark=[]
            for xx,yy in row:
                r=max(3,round(size*.32)); px,py=round(xx),round(yy); sl=np.s_[max(0,py-r):py+r+1,max(0,px-r):px+r+1]
                scores.append(int(blue[sl].sum())); reds.append(int(red[sl].sum())); dark.append(int((gray[sl]<min(150,int(np.median(gray[sl]))-25)).sum()))
            order=np.argsort(scores)[::-1]; first,second=order[:2]; s=scores[first]; minimum=max(4,round(size*.38)); strong=max(9,round(size*.85))
            suggestion='ABCDE'[first] if s>=minimum and scores[second]<max(minimum,.35*s) else ''
            status='Azul detectado' if suggestion else 'Doble o dudosa' if s>=minimum else 'Sin azul: revisar blanco u otra tinta'
            if suggestion and s<strong: status='Azul débil: revisar'
            if suggestion and max(reds)>8: status+=' · posible rojo'
            if not suggestion and (max(dark)>max(10,size*.8) or max(reds)>8): status='Marca oscura o roja: revisar'; scores[0]=max(scores[0],5)
            bounds=np.float32([[[row[0][0]-size*.7,row[0][1]-pitch*.45],[row[-1][0]+size*.7,row[-1][1]-pitch*.45],[row[-1][0]+size*.7,row[-1][1]+pitch*.45],[row[0][0]-size*.7,row[0][1]+pitch*.45]]])
            xy=cv.perspectiveTransform(bounds,inv)[0]; x1,y1=np.floor(xy.min(0)).astype(int); x2,y2=np.ceil(xy.max(0)).astype(int)
            crop=tuple(map(int,(max(0,x1),max(0,y1),min(WIDTH,x2),min(HEIGHT,y2))))
            marks.append(Mark('',suggestion,status,tuple(scores),tuple(reds),crop))
        blocks.append(((x,y,w,h),marks))
    if not blocks: raise ValueError('No se reconocen bloques de casillas cuadradas con suficiente seguridad.')
    # Sort groups left to right, then top to bottom for groups sharing the same column.
    blocks.sort(key=lambda b:(b[0][0]//35,b[0][1]))
    return blocks


def number_blocks(blocks, starts):
    from dataclasses import replace
    import re
    if len(blocks)!=len(starts): raise ValueError('Indica un número inicial por bloque.')
    result=[]; seen=set()
    for (_,marks),start in zip(blocks,starts):
        m=re.fullmatch(r'(R-?)?([1-9][0-9]{0,2})',start.strip().upper())
        if not m: raise ValueError('Usa números como 1, 31 o R1.')
        prefix='R' if m[1] else ''; first=int(m[2]);
        for j,mark in enumerate(marks):
            number=prefix+str(first+j)
            if number in seen: raise ValueError('La numeración de los bloques se solapa.')
            seen.add(number); result.append(replace(mark,number=number))
    return result


def guided_block(im, points, rows, options, start):
    """Read a regular grid from its four outer answer-cell centers."""
    if not 2<=rows<=120 or not 2<=options<=5: raise ValueError('Bloque: 2–120 filas y 2–5 opciones.')
    q=np.asarray(points,np.float32)
    if q.shape!=(4,2) or not np.isfinite(q).all() or not cv.isContourConvex(q) or cv.contourArea(q)<100: raise ValueError('Marca los cuatro centros en orden.')
    if np.any(q<0) or np.any(q[:,0]>=WIDTH) or np.any(q[:,1]>=HEIGHT): raise ValueError('Punto fuera de la hoja.')
    if q[0,0]>=q[1,0] or q[3,0]>=q[2,0] or q[0,1]>=q[3,1] or q[1,1]>=q[2,1]: raise ValueError('Orden de puntos incorrecto.')
    mat=cv.getPerspectiveTransform(np.float32([[0,0],[options-1,0],[options-1,rows-1],[0,rows-1]]),q)
    centers=cv.perspectiveTransform(np.float32([[(j,i) for i in range(rows) for j in range(options)]]),mat)[0].reshape(rows,options,2)
    dx=np.linalg.norm(np.diff(centers,axis=1),axis=2).min(); dy=np.linalg.norm(np.diff(centers,axis=0),axis=2).min()
    if min(dx,dy)<10: raise ValueError('Las casillas son demasiado pequeñas o la cantidad de filas es incorrecta.')
    r=max(3,min(15,round(min(dx,dy)*.29)))
    a=im.astype(np.int16); R,G,B=a.transpose(2,0,1)
    blue=(B-R>5)&(B-G>7)&(B<225)&(R<190); red=(R-B>18)&(R-G>18)&(G<180)&(B-G<35)&(R<205)
    marks=[]
    for row in centers:
        scores=[]; reds=[]
        for x,y in np.round(row).astype(int):
            sl=np.s_[max(0,y-r):y+r+1,max(0,x-r):x+r+1]; scores.append(int(blue[sl].sum())); reds.append(int(red[sl].sum()))
        high,second=sorted(range(options),key=lambda j:scores[j],reverse=True)[:2]; s=scores[high]
        suggestion='ABCDE'[high] if s>=12 and scores[second]<max(12,.35*s) else ''
        status='Azul detectado' if suggestion else 'Doble o dudosa' if s>=12 else 'Sin azul: revisar blanco u otra tinta'
        if suggestion and s<25: status='Azul débil: revisar'
        if max(reds)>20: status+=' · posible rojo'
        x1,y1=np.floor(row.min(0)-r-3).astype(int); x2,y2=np.ceil(row.max(0)+r+4).astype(int)
        marks.append(Mark('',suggestion,status,tuple(scores),tuple(reds),tuple(map(int,(max(0,x1),max(0,y1),min(WIDTH,x2),min(HEIGHT,y2))))))
    return number_blocks([((0,0,0,0),marks)],[start])
