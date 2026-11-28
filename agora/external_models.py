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
    labels: tuple = ()  # printed identifiers, when independently available


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
        # Sliding groups can reuse the last two options of one column and the
        # first of another. Prefer complete columns, never count a cell twice.
        clean=[]; used=[]
        for b in sorted(blocks,key=lambda b:-len(b.rows)):
            cells=[(x,y,w,h) for row in b.rows for x,y,w,h in row]
            if any(abs(x-a)<min(w,c)*.5 and abs(y-bb)<min(h,d)*.5 for x,y,w,h in cells for a,bb,c,d in used): continue
            clean.append(b); used.extend(cells)
        blocks=clean
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


def pdf_labels(text):
    # Accept printed row labels, not footer page numbers or header fields.
    found=[]
    for line in (text or '').splitlines():
        m=re.fullmatch(r'\s*(R\s*-?\s*\d{1,4}|\d{1,4})(?:\s+[A-E](?:\s+[A-E])*)?\s*',line,re.I)
        if m:
            n=re.sub(r'[\s-]','',m[1].upper())
            if int(n.lstrip('R'))>0: found.append(n)
    return tuple(found)


def pdf_options(text):
    from collections import Counter
    counts=Counter()
    for line in (text or '').splitlines():
        m=re.fullmatch(r'\s*(?:R\s*-?\s*)?\d{1,4}\s+([A-E](?:\s+[A-E]){1,4})\s*',line,re.I)
        if m:
            letters=m[1].upper().split()
            if letters==list('ABCDE'[:len(letters)]): counts[len(letters)]+=1
    if counts: return counts.most_common(1)[0][0]
    for m in re.finditer(r'(?im)^\s*N[º°]\s*\n((?:[A-E]\s*\n){2,5})',text or ''):
        letters=m[1].split()
        if letters==list('ABCDE'[:len(letters)]): counts[len(letters)]+=1
    return counts.most_common(1)[0][0] if counts else None


def detected_options(pages,fallback):
    choices={len(row) for p in pages for b in p.blocks for row in b.rows}
    if len(choices)>1: raise ValueError('Las páginas tienen distintos números de opciones. Comprueba los documentos del modelo.')
    return next(iter(choices),fallback)


def learn_with_hints(im,source,options,text=''):
    labels=pdf_labels(text); preferred=pdf_options(text) or options
    p=learn_page(im,source,preferred)
    rows=lambda x:sum(len(b.rows) for b in x.blocks)
    if not rows(p) or (labels and rows(p)!=len(labels)):
        for o in range(2,6):
            if o==preferred: continue
            candidate=learn_page(im,source,o)
            if labels:
                if abs(rows(candidate)-len(labels))<abs(rows(p)-len(labels)): p=candidate
                if rows(p)==len(labels): break
            elif rows(candidate)>rows(p): p=candidate
    p.labels=labels or photo_labels(p)
    return p


def photo_labels(page):
    # Use independent printed-number OCR, not handwritten ink or the answer key.
    from . import number_ocr
    try:
        tokens=number_ocr.recognize(omr.geometry_gray(page.image),11)
    except (RuntimeError, OSError, ValueError, __import__('subprocess').TimeoutExpired): return ()
    labels=[]
    for block in page.blocks:
        votes={}
        for j,row in enumerate(block.rows):
            x,y,w,h=row[0]
            matches=[(conf,t) for t,conf,l,top,ww,hh in tokens if conf>=65 and 0<x-(l+ww/2)<max(8*w,80) and abs(top+hh/2-y)<max(h*.65,5)]
            if matches:
                t=max(matches)[1]; start=int(t.lstrip('R'))-j
                if start>0:
                    k=(t.startswith('R'),start); votes[k]=votes.get(k,0)+1
        n=len(block.rows)
        def strong(votes):
            if not votes: return None
            key,support=max(votes.items(),key=lambda kv:kv[1])
            return key if support>=min(n,max(2,(n+3)//4)) and support>=.8*sum(votes.values()) else None
        anchor=strong(votes)
        if anchor is None:
            # OCR on a narrow strip immediately preceding the detected cells.
            # Separating the digits from printed A/B/C improves colored sheets.
            x0=min(row[0][0] for row in block.rows); y0=min(row[0][1] for row in block.rows); y1=max(row[0][1] for row in block.rows)
            cw=float(np.median([row[0][2] for row in block.rows])); ch=float(np.median([row[0][3] for row in block.rows])); x1=max(1,int(x0-cw*.60)); left=max(0,int(x0-cw*7)); top=max(0,int(y0-ch*.75)); bottom=min(page.image.shape[0],int(y1+ch*.75)+1)
            if bottom<=top or x1<=left: return ()
            strip=omr.geometry_gray(page.image[top:bottom,left:x1]); strip=cv.resize(strip,None,fx=2,fy=2,interpolation=cv.INTER_CUBIC)
            try: local=number_ocr.recognize(strip,6)
            except (RuntimeError,OSError,ValueError,__import__('subprocess').TimeoutExpired): local=[]
            votes={}
            for t,conf,l,yy,ww,hh in local:
                if conf<55: continue
                cy=top+(yy+hh/2)/2; j=min(range(n),key=lambda j:abs(block.rows[j][0][1]-cy)); v=int(t.lstrip('R'))-j
                if abs(block.rows[j][0][1]-cy)<ch*.65 and v>0:
                    k=(t.startswith('R'),v); votes[k]=votes.get(k,0)+1
            anchor=strong(votes)
        if anchor is None: return ()
        reserve,start=anchor
        labels.extend(('R' if reserve else '')+str(start+j) for j in range(n))
    return tuple(labels)


def learn_items(items,options):
    # Model imports have their own page limit; the stable exam reader stays unchanged.
    pages=[]
    for name,data in items:
        if Path(name).suffix.lower()=='.pdf':
            import pypdfium2 as pdfium
            from pypdf import PdfReader
            try: reader=PdfReader(BytesIO(data))
            except Exception: reader=None
            doc=pdfium.PdfDocument(data)
            try:
                if not 1<=len(doc)<=200-len(pages): raise ValueError('Máximo 200 páginas por modelo.')
                for i in range(len(doc)):
                    pdfpage=doc[i]
                    try:
                        w,h=pdfpage.get_size(); bitmap=pdfpage.render(scale=min(3,2000/max(w,h)))
                        try: im=np.array(bitmap.to_pil().convert('RGB'))
                        finally: bitmap.close()
                    finally: pdfpage.close()
                    try: text=reader.pages[i].extract_text() if reader else ''
                    except Exception: text=''
                    pages.append(learn_with_hints(im,f'{name} · {i+1}',options,text))
            finally: doc.close()
        else:
            for i,im in enumerate(omr.decode(name,data)):
                if len(pages)>=200: raise ValueError('Máximo 200 páginas por modelo.')
                pages.append(learn_with_hints(im,f'{name} · {i+1}',options))
    if not pages: raise ValueError('No hay páginas.')
    return pages


def suggest_numbering(pages,questions,reserves):
    """Prefer printed identifiers; use initial values only for ambiguous geometry."""
    n=1; r=1; total=sum(len(b.rows) for p in pages for b in p.blocks)
    reliable=[]
    for p in pages:
        count=sum(len(b.rows) for b in p.blocks)
        reliable.append(bool(count and len(p.labels)==count and len(set(p.labels))==count))
    # If the total is exactly the suggested ordinary count, do not invent reserves.
    # With no printed labels, a reserve hint or ordinary boundary is only a proposal.
    cutoff=questions if total>=questions and (reserves or total>questions) else total
    for p,known in zip(pages,reliable):
        cursor=0; rebuilt=[]
        for b in p.blocks:
            if known:
                labels=p.labels[cursor:cursor+len(b.rows)]; cursor+=len(b.rows)
            else:
                labels=[]
                for _ in b.rows:
                    if n<=cutoff: labels.append(str(n)); n+=1
                    else: labels.append('R'+str(r)); r+=1
            runs=[]
            for row,label in zip(b.rows,labels):
                reserve=label.startswith('R'); v=int(label.lstrip('R'))
                if known:
                    if reserve: r=max(r,v+1)
                    else: n=max(n,v+1)
                if not runs or label!=next_label(runs[-1].start,len(runs[-1].rows)):
                    runs.append(Block([],label))
                runs[-1].rows.append(row)
            rebuilt.extend(runs)
        p.blocks=rebuilt
    return detected_counts(pages)


def next_label(start,offset):
    start=start.strip().upper().replace('-',''); return ('R' if start.startswith('R') else '')+str(int(start.lstrip('R'))+offset)


def detected_counts(pages):
    return tuple(sum(len(b.rows) for p in pages for b in p.blocks if b.start.startswith('R')==reserve) for reserve in (False,True))


def page_kind(page):
    types={b.start.startswith('R') for b in page.blocks}
    return 'mixed' if len(types)>1 else ('reserve' if True in types else 'ordinary')


def reorder_pages(pages,order,kinds):
    # Keep mixed column classifications; a deliberate override changes only numbers.
    if sorted(order)!=list(range(len(pages))) or len(kinds)!=len(pages): raise ValueError('Orden de páginas incorrecto.')
    result=[pages[i] for i in order]; nexts={False:1,True:1}
    for p,kind in zip(result,kinds):
        for b in p.blocks:
            reserve=b.start.startswith('R') if kind=='mixed' else kind=='reserve'
            b.start=('R' if reserve else '')+str(nexts[reserve]); nexts[reserve]+=len(b.rows)
    return result


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
        if p.labels and len(p.labels)!=sum(len(b.rows) for b in p.blocks): raise ValueError('La numeración impresa y las filas reconocidas no coinciden en '+p.source+'. Repite la importación con una hoja nítida.')
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
    def update(self,mid,name,items,pages,questions,reserves,options):
        """Replace geometry and sources atomically, preserving the model identity."""
        name=name.strip()
        if not name or len(name)>100: raise ValueError('Introduce un nombre de hasta 100 caracteres.')
        meta=metadata(pages,questions,reserves,options)
        signature=hashlib.sha256(b''.join(hashlib.sha256(data).digest() for _,data in items)).hexdigest()
        refs=[]
        for i,p in enumerate(pages):
            buf=BytesIO(); Image.fromarray(p.image).save(buf,format='PNG'); refs.append((mid,'reference',i,f'pagina-{i+1}.png',buf.getvalue()))
        with closing(sqlite3.connect(self.path)) as db,db:
            if not db.execute('SELECT 1 FROM external WHERE id=?',(mid,)).fetchone(): raise ValueError('El modelo ya no existe.')
            existing=db.execute('SELECT name FROM external WHERE signature=? AND id<>?',(signature,mid)).fetchone()
            if existing: raise ValueError('Estos documentos ya están guardados como «'+existing[0]+'».')
            db.execute('UPDATE external SET name=?,signature=?,metadata=? WHERE id=?',(name,signature,json.dumps(meta,ensure_ascii=False),mid))
            db.execute('DELETE FROM files WHERE id=?',(mid,))
            db.executemany('INSERT INTO files VALUES (?,?,?,?,?)',[(mid,'original',i,fn,data) for i,(fn,data) in enumerate(items)]+refs)
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
