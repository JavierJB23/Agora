"""06E: optional reference-guided recognition, with the unchanged universal fallback.
A model is not selected merely by number of questions or colour. Registration and
independent printed geometry checks must succeed before reference coordinates vote.
"""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import logging
import cv2 as cv
import numpy as np
from PIL import Image
from . import omr
from .models import PRESETS, ModelLibrary, identifier, layout, pdf_bytes
from .external_models import ExternalLibrary

log=logging.getLogger(__name__)

@dataclass
class Reference:
    name: str
    image: np.ndarray
    rows: list  # (printed number, [(x,y,width,height), ...])
    key: str = ''  # exact printed AGORA1 identifier, including page
    features: object = None
    fiducials: object = None


def features(image):
    gray=omr.geometry_gray(image)
    # Full resolution: small printed labels are important, not just the grid.
    detector=cv.SIFT_create(nfeatures=2400, contrastThreshold=.022)
    points,desc=detector.detectAndCompute(gray,None)
    return np.float32([k.pt for k in points]).reshape(-1,2),desc


def qr_code(image):
    detector=cv.QRCodeDetector()
    # Original resolution first; a second pass on the lower half helps with small QR codes.
    h,w=image.shape[:2]
    regions=[(image,0,0,1,cv.INTER_LINEAR),
             (image[int(h*.85):,int(w*.75):],int(w*.75),int(h*.85),2.5,cv.INTER_LINEAR),
             (image[int(h*.85):,int(w*.75):],int(w*.75),int(h*.85),4,cv.INTER_LINEAR),
             (image[int(h*.78):,int(w*.65):],int(w*.65),int(h*.78),2,cv.INTER_NEAREST),
             (image[int(h*.78):,int(w*.65):],int(w*.65),int(h*.78),3,cv.INTER_LINEAR),
             (image[h//2:,w//2:],w//2,h//2,2,cv.INTER_NEAREST),
             (image[h//2:],0,h//2,2,cv.INTER_LINEAR)]
    for region,ox,oy,scale,interpolation in regions:
        try:
            sample=cv.resize(region,None,fx=scale,fy=scale,interpolation=interpolation) if scale!=1 else region
            value,points,_=detector.detectAndDecode(sample)
        except cv.error: continue
        if points is not None and re.fullmatch(r'AGORA1:[0-9a-f]{16}:[1-9]\d*:[1-9]\d*',value):
            return value,points.reshape(4,2)/scale+np.float32([ox,oy])
    return '',None


def own_references(model,only_page=None):
    import pypdfium2 as pdfium
    from reportlab.lib.units import mm
    pages=layout(model); doc=pdfium.PdfDocument(pdf_bytes(model))
    try:
        for i,page in enumerate(pages,1):
            if only_page is not None and i!=only_page: continue
            pdfpage=doc[i-1]
            try:
                w,h=pdfpage.get_size(); bitmap=pdfpage.render(scale=min(3,2000/max(w,h)))
                try: im=np.array(bitmap.to_pil().convert('RGB'))
                finally: bitmap.close()
            finally: pdfpage.close()
            yield own_reference(model,page,im,i,len(pages),mm)
    finally: doc.close()


def own_reference(model,page,im,i,count,mm):
    canvas,mat=omr.original_canvas(im); h,w=im.shape[:2]
    sx=w/page['width']; sy=h/page['height']; scale=mat[0,0]
    rows=[]
    for block in page['blocks']:
        for row in block['rows']:
            cells=[(float(x*sx*scale+mat[0,2]),float((page['height']-row['y'])*sy*scale+mat[1,2]),float(page['cell']*sx*scale),float(page['cell']*sy*scale*(.72 if model.shape=='oval' else 1))) for x in row['centers']]
            rows.append((row['number'],cells))
    ma=page['margin']; px=page['width']; py=page['height']
    fiducials=np.float32([((x*sx)*scale+mat[0,2],((py-y)*sy)*scale+mat[1,2]) for x,y in [(ma-3*mm,py-ma+3*mm),(px-ma+3*mm,py-ma+3*mm),(px-ma+3*mm,ma-3*mm),(ma-3*mm,ma-3*mm)]])
    return Reference(model.name,canvas,rows,f'AGORA1:{identifier(model)}:{i}:{count}',fiducials=fiducials)

def external_references(directory):
    if directory is None or not (Path(directory)/'external_models.sqlite3').is_file(): return
    lib=ExternalLibrary(directory)
    for mid,name,_,meta in lib.entries():
        if meta.get('schema')!=1: continue
        for i,p in enumerate(meta['pages']):
            from contextlib import closing
            import sqlite3
            with closing(sqlite3.connect(lib.path)) as db:
                result=db.execute("SELECT data FROM files WHERE id=? AND kind='reference' AND position=?",(mid,i)).fetchone()
            if result is None: continue
            blob=result[0]
            with Image.open(BytesIO(blob)) as img: im=np.array(img.convert('RGB'))
            h,w=im.shape[:2]
            if (h,w)!=(p['height'],p['width']): continue
            canvas,mat=omr.original_canvas(im); s=mat[0,0]
            rows=[(r['number'],[(x*w*s+mat[0,2],y*h*s+mat[1,2],cw*w*s,ch*h*s) for x,y,cw,ch in r['cells']]) for b in p['blocks'] for r in b['rows']]
            if rows: yield Reference(name,canvas,rows)


def registration(ref,query_features,image,qr_points=None):
    if ref.features is None: ref.features=features(ref.image)
    a,da=ref.features; b,db=query_features
    if da is None or db is None or min(len(da),len(db))<8: return None
    matches=cv.BFMatcher(cv.NORM_L2).knnMatch(da,db,k=2)
    good=[m for pair in matches if len(pair)==2 for m,n in [pair] if m.distance<.72*n.distance]
    # Repeated outlines must not count multiple times at the same destination.
    unique={}
    for m in sorted(good,key=lambda m:m.distance): unique.setdefault(m.trainIdx,m)
    good=list(unique.values())
    if len(good)<12: return None
    src=np.float32([a[m.queryIdx] for m in good]); dst=np.float32([b[m.trainIdx] for m in good]);
    H,inlier=cv.findHomography(src,dst,cv.RANSAC,3.5)
    if H is None or inlier is None: return None
    take=inlier.ravel().astype(bool); s=src[take]; d=dst[take]
    if len(s)<12 or take.mean()<.30: return None
    # Do not extrapolate from a tiny patch of repeated cells.
    cells=np.float32([(x,y) for _,row in ref.rows for x,y,_,_ in row]); extent=np.ptp(cells,axis=0)
    if np.any(np.ptp(s,axis=0)<np.maximum(30,extent*.42)): return None
    if qr_points is not None:
        key,ref_qr=qr_code(ref.image)
        if key!=ref.key or ref_qr is None: return None
        predicted=cv.perspectiveTransform(np.float32([ref_qr]),H)[0]
        if np.max(np.linalg.norm(predicted-qr_points,axis=1))>max(8,np.ptp(qr_points[:,0])*.15): return None
    return H,len(s)


def geometry_score(reference,aligned,rows):
    # Verify the printed outlines locally, not just the page corners. Missing
    # rows, header-as-row errors and severe curvature cause a fallback.
    def edges(im):
        gray=omr.geometry_gray(im); return cv.Canny(gray,35,100)
    a=edges(reference); b=edges(aligned)
    dist=cv.distanceTransform((b==0).astype(np.uint8),cv.DIST_L2,3)
    row_scores=[]
    for _,cells in rows:
        scores=[]
        for x,y,w,h in cells:
            x1=max(0,int(x-w*.65)); x2=min(omr.WIDTH,int(x+w*.65)+1); y1=max(0,int(y-h*.65)); y2=min(omr.HEIGHT,int(y+h*.65)+1)
            edge=a[y1:y2,x1:x2]>0
            if edge.sum()<8: scores.append(0.); continue
            scores.append(float(np.mean(dist[y1:y2,x1:x2][edge]<=max(2.4,min(w,h)*.15))))
        row_scores.append(float(np.mean(scores)))
    if not row_scores or min(row_scores)<.40 or np.percentile(row_scores,10)<.65 or np.mean(row_scores)<.78: return None
    # Also compare printed text and headings, including labels outside the cells.
    # One-sided coverage tolerates handwriting; mismatched layouts do not pass.
    coverage=float(np.mean(dist[a>0]<=2.7)) if np.any(a) else 0.
    reverse_dist=cv.distanceTransform((a==0).astype(np.uint8),cv.DIST_L2,3)
    reverse=float(np.mean(reverse_dist[b>0]<=3.2)) if np.any(b) else 0.
    if coverage<.65 or reverse<.48: return None
    # Reciprocal coverage distinguishes a short reserve grid from the top
    # of a longer ordinary sheet, while tolerating added pen strokes.
    return .55*float(np.mean(row_scores))+.20*coverage+.25*reverse


def refine_fiducials(ref,aligned):
    # The four printed black squares are independent alignment witnesses.
    # Work in the registered canvas; reject false square candidates by size,
    # fill and distance. Missing squares do not override verified geometry.
    if ref.fiducials is None: return aligned
    gray=cv.cvtColor(aligned,cv.COLOR_RGB2GRAY); found=[]
    expected_size=min(np.linalg.norm(ref.fiducials[1]-ref.fiducials[0]),np.linalg.norm(ref.fiducials[3]-ref.fiducials[0]))*.022
    radius=max(12,round(expected_size*1.4))
    for x,y in ref.fiducials:
        x1=max(0,round(x-radius)); y1=max(0,round(y-radius)); x2=min(omr.WIDTH,round(x+radius)); y2=min(omr.HEIGHT,round(y+radius))
        roi=gray[y1:y2,x1:x2]; mask=(roi<85).astype(np.uint8)
        cnts,_=cv.findContours(mask,cv.RETR_EXTERNAL,cv.CHAIN_APPROX_SIMPLE); candidates=[]
        for c in cnts:
            xx,yy,w,h=cv.boundingRect(c); area=cv.contourArea(c)
            if not (.5*expected_size<=w<=1.6*expected_size and .5*expected_size<=h<=1.6*expected_size and .7<=w/h<=1.4 and area>=.68*w*h): continue
            center=np.float32([x1+xx+(w-1)/2,y1+yy+(h-1)/2]); distance=np.linalg.norm(center-[x,y])
            if distance<=radius*.70: candidates.append((distance,center))
        if not candidates: return aligned
        found.append(min(candidates,key=lambda k:k[0])[1])
    src=np.float32(found); dst=ref.fiducials
    if not cv.isContourConvex(src): return aligned
    H=cv.getPerspectiveTransform(src,dst)
    return cv.warpPerspective(aligned,H,(omr.WIDTH,omr.HEIGHT),borderValue=(255,255,255))


def warp_checked(ref,image,H):
    if H is None or not np.isfinite(H).all(): return None
    h,w=image.shape[:2]
    bounds=cv.perspectiveTransform(np.float32([[[0,0],[omr.WIDTH-1,0],[omr.WIDTH-1,omr.HEIGHT-1],[0,omr.HEIGHT-1]]]),H)[0]
    if not np.isfinite(bounds).all() or not cv.isContourConvex(bounds) or cv.contourArea(bounds)<.10*w*h: return None
    centers=np.float32([[(x,y) for _,row in ref.rows for x,y,_,_ in row]])
    p=cv.perspectiveTransform(centers,H)[0]
    if not np.isfinite(p).all() or np.any(p[:,0]<3) or np.any(p[:,0]>=w-3) or np.any(p[:,1]<3) or np.any(p[:,1]>=h-3): return None
    try: aligned=cv.warpPerspective(image,np.linalg.inv(H),(omr.WIDTH,omr.HEIGHT),borderValue=(255,255,255))
    except (np.linalg.LinAlgError,cv.error): return None
    score=geometry_score(ref.image,aligned,ref.rows)
    if ref.fiducials is not None:
        refined=refine_fiducials(ref,aligned)
        if refined is not aligned:
            improved=geometry_score(ref.image,refined,ref.rows)
            if improved is not None and (score is None or improved>score): aligned,score=refined,improved
    return (aligned,score) if score is not None else None


def classify(ref,aligned):
    """Subtract printed ink; only new blue ink votes automatically. Ambiguous dark
    strokes, red-only marks and possible cancellations remain reviewable."""
    old=ref.image; R,G,B=aligned.astype(np.int16).transpose(2,0,1)
    gray=cv.cvtColor(aligned,cv.COLOR_RGB2GRAY); base=cv.cvtColor(old,cv.COLOR_RGB2GRAY)
    # Local illumination compensation, robust against coloured paper and shadows.
    bg=cv.dilate(gray,np.ones((19,19),np.uint8)).astype(np.int16)
    refbg=cv.dilate(base,np.ones((19,19),np.uint8)).astype(np.int16)
    old_dark=refbg-base.astype(np.int16)>22
    printed=cv.dilate(old_dark.astype(np.uint8),np.ones((3,3),np.uint8))>0
    oldR,oldG,oldB=old.astype(np.int16).transpose(2,0,1)
    new_dark=(bg-gray.astype(np.int16))>23
    blue=(B-R>5)&(B-G>7)&(R<205)&new_dark
    red=(R-B>16)&(R-G>16)&(G<205)&new_dark
    # Preserve ink of a different hue on a printed character, while avoiding
    # a false mark from the printed rim itself.
    blue &= (~printed | ((B-R)-(oldB-oldR)>22)&((B-G)-(oldB-oldG)>19))
    red &= (~printed | ((R-B)-(oldR-oldB)>25)&((R-G)-(oldR-oldG)>25))
    residual=new_dark & ~printed
    # Render only new pen pixels for the existing strike detector.
    ink=np.full_like(aligned,255); ink[blue]=(25,45,145); ink[red]=(165,25,25)
    marks=[]
    for number,cells in ref.rows:
        scores=[]; reds=[]; dark=[]; thresholds=[]
        for x,y,w,h in cells:
            rx=max(2,round(w*.32)); ry=max(2,round(h*.32)); x=round(x); y=round(y)
            sl=np.s_[max(0,y-ry):y+ry+1,max(0,x-rx):x+rx+1]
            scores.append(int(blue[sl].sum())); reds.append(int(red[sl].sum())); dark.append(int(residual[sl].sum())); thresholds.append(max(6,round(blue[sl].size*.065)))
        hi,second=sorted(range(len(cells)),key=lambda j:scores[j],reverse=True)[:2]; low=thresholds[hi]; strong=max(low+3,round(low*1.45)); s=scores[hi]
        suggestion='ABCDE'[hi] if s>=low and scores[second]<max(thresholds[second],s*.40) else ''
        status='Azul detectado' if suggestion else 'Doble o dudosa' if s>=low else 'Sin azul: revisar blanco u otra tinta'
        if suggestion and s<strong: status='Azul débil: revisar'
        if max(reds)>=min(thresholds): status+=' · posible rojo'
        if not suggestion and max(dark)>=max(9,min(thresholds)*2):
            # proposed() treats fewer than 5 blue pixels as a blank; force review
            # without fabricating a blue response when unexplained dark ink exists.
            status='Tinta dudosa · revisar'
        x1=min(x-w*.55 for x,y,w,h in cells); x2=max(x+w*.55 for x,y,w,h in cells)
        y1=min(y-h*.58 for x,y,w,h in cells); y2=max(y+h*.58 for x,y,w,h in cells)
        crop,quad=omr.row_geometry([(x1,y1),(x2,y1),(x2,y2),(x1,y2)])
        m=omr.Mark(number,suggestion,status,tuple(scores),tuple(reds),crop,quad,'geometry')
        if omr.red_strike(ink,m): m=omr.replace(m,status='Posible anulada · tachadura roja · revisar')
        elif omr.red_strike(ink,m,True): m=omr.replace(m,status='Posible anulada · tachadura azul · revisar')
        marks.append(m)
    return marks


class ModelReader:
    def __init__(self,directory=None):
        self.directory=directory; self._own={}
        models=list(PRESETS)
        if directory is not None and (Path(directory)/'models.sqlite3').is_file():
            try: models.extend(m for _,m,_ in ModelLibrary(directory).entries())
            except Exception: log.warning('No se pudieron consultar los modelos propios',exc_info=True)
        self.models={identifier(m):m for m in models}

    def own(self,key):
        mid=key.split(':')[1]
        if mid not in self.models: return []
        if key not in self._own:
            self._own[key]=list(own_references(self.models[mid],int(key.split(':')[2])))
            if len(self._own)>4: self._own.pop(next(iter(self._own)))
        return [ref for ref in self._own[key] if ref.key==key]

    def external(self):
        return external_references(self.directory)

    def match(self,image,options):
        key,qr=qr_code(image)
        candidates=self.own(key) if key else self.external()
        f=None; best=None; scores=[]
        for ref in candidates:
            if not all(len(row)>=options for _,row in ref.rows): continue
            if f is None: f=features(image)
            reg=registration(ref,f,image,qr if key else None)
            if reg is None: continue
            result=warp_checked(ref,image,reg[0])
            if result is not None:
                scores.append((result[1],ref.rows))
                if best is None or result[1]>best[0]: best=(result[1],ref,result[0])
        if best is None: return None
        score,ref,aligned=best
        # Compare every close alternative, without retaining all its images.
        for other_score,rows in scores:
            if score-other_score>.055 or rows is ref.rows: continue
            if len(ref.rows)!=len(rows) or any(n!=m or len(a)!=len(b) or np.max(np.abs(np.asarray(a)-np.asarray(b)))>4 for (n,a),(m,b) in zip(ref.rows,rows)):
                return None
        return ref,aligned,classify(ref,aligned)

    def read(self,image,config,progress=None):
        if progress: progress(.04,'Identificando modelo')
        def universal():
            return omr.automatic_page(image,config.questions,config.reserves,config.options,progress=progress,verify_ocr=True)
        try:
            result=self.match(image,config.options)
            if result is not None:
                ref,aligned,marks=result
                if any((m.number.startswith('R') and int(m.number[1:])<=config.reserves) or (not m.number.startswith('R') and int(m.number)<=config.questions) for m in marks) or all(m.number.startswith('R') for m in marks):
                    if not ref.key:
                        # Independent printed-number check for learned models.
                        # Never apply a reference if OCR strongly contradicts it.
                        from .number_ocr import verify
                        try:
                            checked,_,changed,conflicts=verify(aligned,marks)
                            if changed or conflicts: raise ValueError('Numeración impresa incompatible con el modelo aprendido.')
                            marks=checked
                        except (RuntimeError,OSError,omr.subprocess.TimeoutExpired): pass
                        # The stable reader is a second chance when residual
                        # ink is unusually ambiguous on a photographed reference.
                        if sum(not omr.proposed(m) for m in marks)>max(3,len(marks)*.20):
                            try:
                                alt=universal()
                                if {m.number for m in alt[1]}=={m.number for m in marks} and sum(bool(omr.proposed(m)) for m in alt[1])>sum(bool(omr.proposed(m)) for m in marks):
                                    alerts={m.number:m.status for m in marks if 'Posible anulada' in m.status}
                                    alt_marks=[omr.replace(m,status=alerts[m.number]) if m.number in alerts and 'Posible anulada' not in m.status else m for m in alt[1]]
                                    return alt[0],alt_marks
                            except ValueError: pass
                    marks=[omr.replace(m,model_name=ref.name) for m in marks]
                    if progress: progress(.80,'Modelo identificado · '+ref.name)
                    return aligned,marks
        except Exception:
            # A damaged optional library or failed registration must never
            # disable the stable reader or replace an existing saved exam.
            log.warning('Lectura por modelo no disponible; se usará el lector universal',exc_info=True)
        return universal()
