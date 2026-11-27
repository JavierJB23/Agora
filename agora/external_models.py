"""Learn the printed geometry of blank sheets, separate from exam answers.
No ink classifier or exam history is modified in 06D.
"""
from dataclasses import dataclass
from datetime import datetime
from contextlib import closing
from pathlib import Path
from io import BytesIO
import hashlib, json, re, sqlite3, uuid
import cv2 as cv
import numpy as np
from PIL import Image
from . import omr

@dataclass
class Block:
    rows: list  # rows of (x,y,w,h) measured cell rectangles, on the reference image
    start: str = ''

@dataclass
class Page:
    image: np.ndarray
    blocks: list
    source: str


def _candidates(im):
    gray=omr.geometry_gray(im)
    mask=cv.adaptiveThreshold(gray,255,cv.ADAPTIVE_THRESH_GAUSSIAN_C,cv.THRESH_BINARY_INV,31,7)
    contours,hier=cv.findContours(mask,cv.RETR_TREE,cv.CHAIN_APPROX_SIMPLE)
    pts=[]
    if hier is None: return np.empty((0,4))
    for i,c in enumerate(contours):
        x,y,w,h=cv.boundingRect(c); area=cv.contourArea(c); per=cv.arcLength(c,True)
        # A closed printed outline has an interior hole. Reject most text and headers.
        child=hier[0,i,2]
        if child<0 or not (9<=w<=65 and 7<=h<=65 and .60<=w/h<=2.4 and area>=.48*w*h and per>0 and 4*np.pi*area/per**2>.48): continue
        pts.append((x+w/2,y+h/2,w,h))
    keep=[]
    for p in sorted(pts,key=lambda v:-v[2]*v[3]):
        if not any(abs(p[0]-q[0])<min(p[2],q[2])*.30 and abs(p[1]-q[1])<min(p[3],q[3])*.30 for q in keep): keep.append(p)
    return np.array(keep,dtype=float).reshape(-1,4)


def detect_blocks(im,options):
    """Find complete rows of repeated outlines, without counting text headers.
    Each candidate is checked in both axes; incomplete rows are not interpolated.
    """
    if not 2<=options<=5: raise ValueError('Indica entre 2 y 5 casillas por fila.')
    allpts=_candidates(im); best=[]; bestscore=0
    if len(allpts)<options: raise ValueError('No se reconocen casillas cerradas.')
    sizes=np.sqrt(allpts[:,2]*allpts[:,3]); trials=sorted(set(round(s/3)*3 for s in sizes))
    for size in trials:
        p=allpts[(sizes>=size*.78)&(sizes<=size*1.27)]
        if len(p)<options: continue
        # Group approximately horizontal rows, then identify regular option sequences.
        rows=[]
        for y,_ in omr._clusters(p[:,1],max(3,size*.34)):
            line=p[abs(p[:,1]-y)<=max(3,size*.34)]; line=line[np.argsort(line[:,0])]
            if len(line)<options: continue
            for i in range(len(line)-options+1):
                group=line[i:i+options]; gaps=np.diff(group[:,0]); step=float(np.median(gaps))
                if not size*.80<=step<=size*15.0 or np.max(abs(gaps-step))>step*.17: continue
                if np.ptp(group[:,1])>size*.55: continue
                # Do not cut a longer sequence into shorter sliding windows.
                if i and abs(group[0,0]-line[i-1,0]-step)<step*.22: continue
                if i+options<len(line) and abs(line[i+options,0]-group[-1,0]-step)<step*.22: continue
                rows.append(group)
        if not rows: continue
        groups=[]
        for row in sorted(rows,key=lambda r:(float(r[0,0]),float(r[0,1]))):
            target=next((g for g in groups if np.max(abs(np.median(np.array(g)[:,:,0],axis=0)-row[:,0]))<size*.65),None)
            if target is None: groups.append([row])
            else: target.append(row)
        blocks=[]
        for g in groups:
            g.sort(key=lambda r:float(np.mean(r[:,1]))); ys=np.array([np.mean(r[:,1]) for r in g]); dif=np.diff(ys)
            useful=dif[dif>size*.65]; pitch=float(np.median(useful)) if len(useful) else size*1.5
            runs=[[]]
            for i,row in enumerate(g):
                if i and not pitch*.65<=ys[i]-ys[i-1]<=pitch*1.45: runs.append([])
                runs[-1].append(row)
            for run in runs:
                if len(run)<2: continue
                blocks.append(Block([r.tolist() for r in run]))
        score=sum(len(b.rows) for b in blocks)-.5*len(blocks)
        if score>bestscore: bestscore=score; best=blocks
    if not best: raise ValueError('No se reconocen bloques de casillas. Comprueba las opciones impresas y la nitidez.')
    return sorted(best,key=lambda b:(round(b.rows[0][0][0]/20),b.rows[0][0][1]))


def learn_page(im,source,options):
    raw=omr.original_canvas(im)[0]; candidates=[]
    canvases=[raw]
    try:
        if im.shape[0]>=im.shape[1]: canvases.append(omr.align(im))
    except ValueError: pass
    for a in canvases:
        try: candidates.append(Page(a,detect_blocks(a,options),source))
        except ValueError: pass
    if not candidates: return Page(raw,[],source)
    return max(candidates,key=lambda p:sum(len(b.rows) for b in p.blocks)-.5*len(p.blocks))


def learn_items(items,options):
    pages=[]
    for name,data in items:
        for i,im in enumerate(omr.decode(name,data)):
            if len(pages)>=20: raise ValueError('Máximo 20 páginas por modelo.')
            pages.append(learn_page(im,f'{name} · {i+1}',options))
    if not pages: raise ValueError('No hay páginas.')
    return pages


def preview(page):
    im=page.image.copy()
    for i,b in enumerate(page.blocks):
        if not b.rows: continue
        for row in b.rows:
            for x,y,w,h in row:
                cv.rectangle(im,(round(x-w/2),round(y-h/2)),(round(x+w/2),round(y+h/2)),(0,155,100),2)
        x,y,_,_=b.rows[0][0]; cv.putText(im,str(i+1),(round(x-20),max(25,round(y-18))),cv.FONT_HERSHEY_SIMPLEX,.8,(165,83,121),2)
    return im


def metadata(pages,questions,reserves,options):
    if not 1<=questions<=500 or not 0<=reserves<=100 or not 2<=options<=5: raise ValueError('Configuración fuera de rango.')
    wanted={str(i) for i in range(1,questions+1)}|{f'R{i}' for i in range(1,reserves+1)}; seen=set(); result=[]
    for p in pages:
        h,w=p.image.shape[:2]; blocks=[]; used=[]
        for b in p.blocks:
            if not b.rows: continue
            m=re.fullmatch(r'(R-?)?([1-9][0-9]{0,2})',b.start.strip().upper())
            if not m: raise ValueError('Indica el inicio de cada bloque (1, 31 o R1).')
            prefix='R' if m[1] else ''; start=int(m[2]); rows=[]
            for i,row in enumerate(b.rows):
                num=prefix+str(start+i)
                if not prefix and start<=questions<start+i: num='R'+str(start+i-questions)
                if num in seen: raise ValueError('Numeración repetida: '+num)
                if len(row)!=options: raise ValueError('Número de opciones incorrecto.')
                for x,y,cw,ch in row:
                    if not (0<x<w and 0<y<h and cw>0 and ch>0): raise ValueError('Casilla fuera de la página.')
                    if any(abs(x-a)<min(cw,c)*.5 and abs(y-b)<min(ch,d)*.5 for a,b,c,d in used): raise ValueError('Hay casillas superpuestas.')
                    used.append((x,y,cw,ch))
                seen.add(num); rows.append({'number':num,'cells':[[float(x)/w,float(y)/h,float(cw)/w,float(ch)/h] for x,y,cw,ch in row]})
            blocks.append({'start':prefix+str(start),'rows':rows})
        if not blocks: raise ValueError('Hay una página sin bloques válidos.')
        result.append({'source':p.source,'width':w,'height':h,'blocks':blocks})
    if seen!=wanted:
        missing=sorted(wanted-seen,key=lambda n:(n.startswith('R'),int(n.lstrip('R')))); extra=sorted(seen-wanted)
        raise ValueError('La numeración no coincide. Faltan: '+(', '.join(missing[:12]) or 'ninguna')+' · Sobran: '+(', '.join(extra[:12]) or 'ninguna'))
    return {'schema':1,'questions':questions,'reserves':reserves,'options':options,'pages':result}


class ExternalLibrary:
    def __init__(self,directory):
        self.path=Path(directory)/'external_models.sqlite3'
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS external (id TEXT PRIMARY KEY,name TEXT NOT NULL,created TEXT NOT NULL,signature TEXT UNIQUE NOT NULL,metadata TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS files (id TEXT NOT NULL,kind TEXT NOT NULL,position INTEGER NOT NULL,name TEXT NOT NULL,data BLOB NOT NULL,PRIMARY KEY(id,kind,position))')
    def entries(self):
        with closing(sqlite3.connect(self.path)) as db:
            return [(i,n,d,json.loads(m)) for i,n,d,m in db.execute('SELECT id,name,created,metadata FROM external ORDER BY created DESC,id')]
    def files(self,mid,kind):
        with closing(sqlite3.connect(self.path)) as db:
            return list(db.execute('SELECT name,data FROM files WHERE id=? AND kind=? ORDER BY position',(mid,kind)))
    def save(self,name,items,pages,questions,reserves,options):
        name=name.strip()
        if not name or len(name)>100: raise ValueError('Introduce un nombre de hasta 100 caracteres.')
        meta=metadata(pages,questions,reserves,options); signature=hashlib.sha256(b''.join(hashlib.sha256(data).digest() for _,data in items)).hexdigest(); mid=uuid.uuid4().hex
        with closing(sqlite3.connect(self.path)) as db,db:
            existing=db.execute('SELECT name FROM external WHERE signature=?',(signature,)).fetchone()
            if existing: raise ValueError('El mismo documento ya está guardado como «'+existing[0]+'».')
            db.execute('INSERT INTO external VALUES (?,?,?,?,?)',(mid,name,datetime.now().isoformat(timespec='seconds'),signature,json.dumps(meta,ensure_ascii=False)))
            for i,(fn,data) in enumerate(items): db.execute('INSERT INTO files VALUES (?,?,?,?,?)',(mid,'original',i,fn,data))
            for i,p in enumerate(pages):
                buf=BytesIO(); Image.fromarray(p.image).save(buf,format='PNG'); db.execute('INSERT INTO files VALUES (?,?,?,?,?)',(mid,'reference',i,f'pagina-{i+1}.png',buf.getvalue()))
        return mid
    def rename(self,mid,name):
        name=name.strip()
        if not name or len(name)>100: raise ValueError('Introduce un nombre de hasta 100 caracteres.')
        with closing(sqlite3.connect(self.path)) as db,db: db.execute('UPDATE external SET name=? WHERE id=?',(name,mid))
    def delete(self,mid):
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('DELETE FROM files WHERE id=?',(mid,)); db.execute('DELETE FROM external WHERE id=?',(mid,))


def propose_starts(pages,questions):
    n=1
    for p in pages:
        for b in p.blocks:
            b.start=str(n) if n<=questions else 'R'+str(n-questions)
            n+=len(b.rows)


def manual_block(points,rows,options,start):
    q=np.asarray(points,np.float32)
    if not 1<=rows<=500 or not 2<=options<=5: raise ValueError('Dimensiones no válidas.')
    if rows==1:
        if q.shape!=(2,2): raise ValueError('Marca la primera y última casilla.')
        pitch=np.linalg.norm(q[1]-q[0])/(options-1); v=(q[1]-q[0])/(options-1)
        if pitch<7 or v[0]<=0: raise ValueError('Marca las casillas de izquierda a derecha.')
        return Block([[(float(x),float(y),float(pitch*.55),float(pitch*.55)) for x,y in [q[0]+j*v for j in range(options)]]],start)
    if q.shape!=(4,2) or not cv.isContourConvex(q) or cv.contourArea(q)<50 or q[1,0]<=q[0,0] or q[3,1]<=q[0,1]: raise ValueError('Marca las cuatro casillas exteriores en el orden indicado.')
    src=np.float32([[0,0],[options-1,0],[options-1,rows-1],[0,rows-1]])
    mat=cv.getPerspectiveTransform(src,q); grid=np.float32([[[j,i] for j in range(options)] for i in range(rows)])
    xy=cv.perspectiveTransform(grid.reshape(1,-1,2),mat).reshape(rows,options,2)
    size=min(np.median(np.linalg.norm(np.diff(xy,axis=1),axis=2)),np.median(np.linalg.norm(np.diff(xy,axis=0),axis=2)))*.60
    if size<4: raise ValueError('Casillas demasiado pequeñas.')
    return Block([[(float(x),float(y),float(size),float(size)) for x,y in row] for row in xy],start)
