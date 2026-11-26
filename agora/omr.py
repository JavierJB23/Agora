"""Block 05: optical mark proposals for the supplied 120+9 A/B/C layout.
Blue ink is interpreted; clear results are proposed and the set is confirmed before scoring.
"""
from dataclasses import dataclass, replace
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
    quad: tuple[tuple[float,float],...] = ()  # ordered corners of the actual row

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

def _legacy_grid_positions(im,page):
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

def local_circle_positions(im):
    """Fit each of four printed columns independently, including smooth page curvature.
    Require evidence for the full 30-row lattice in every column; never infer numbering
    from an arbitrary subset of circles. Missing individual circles use local interpolation.
    """
    g=cv.GaussianBlur(cv.cvtColor(im,cv.COLOR_RGB2GRAY),(3,3),0)
    lo,hi=250,1580
    c=cv.HoughCircles(g[lo:hi],cv.HOUGH_GRADIENT,1,19,param1=60,param2=12,minRadius=6,maxRadius=18)
    if c is None: raise ValueError('No se reconocen los círculos.')
    found=c[0,:,:2].astype(float); found[:,1]+=lo
    groups=[]; first_span=None
    for col in range(4):
        mid=list(locations(0))[col*30][1][1]
        p=found[(abs(found[:,0]-mid)<115)]
        delta=p[:,None,:]-p[None,:,:]
        left=(delta[:,:,0]>23)&(delta[:,:,0]<47)&(abs(delta[:,:,1])<9)
        right=(delta[:,:,0]<-23)&(delta[:,:,0]>-47)&(abs(delta[:,:,1])<9)
        mids=p[left.any(1)&right.any(1)&(abs(p[:,0]-mid)<75)]
        if len(mids)<21: raise ValueError('No se reconoce una columna completa.')
        # Candidate first row and pitch. Use all triplets, not a single global paper warp.
        starts=np.arange(275,571,2.); pitches=np.arange(27,46.1,.5)
        s,step=np.meshgrid(starts,pitches); s=s.ravel(); step=step.ravel()
        row=np.arange(30); best_cost=np.inf; fit=None; candidates=[]
        for bend in np.arange(-.07,.071,.02):
            py=s[:,None]+step[:,None]*row+bend*row*(row-29)
            d=abs(py[:,:,None]-mids[None,None,:,1]); near=d.min(2); ids=d.argmin(2)
            cost=np.minimum(near,step[:,None]*.40).mean(1)+.012*abs(mids[ids,0]-mid).mean(1)
            valid=((near<step[:,None]*.24).sum(1)>=23)&(near[:,0]<step*.24)&(near[:,-1]<step*.24)
            if first_span is not None:
                valid &= (abs(s-first_span[0])<step*.85)&(abs(s+29*step-first_span[1])<step*.85)
            else:
                # Prefer a nominally aligned start only to break near-ties.
                cost -= .15*np.maximum(0,1-abs(s-359)/25)
            if not valid.any(): continue
            best=int(np.argmin(np.where(valid,cost,np.inf)))
            candidates.extend(zip(s[valid],(s+29*step)[valid],cost[valid]))
            if cost[best]<best_cost:
                best_cost=cost[best]; fit=(py[best],step[best],near[best],ids[best])
        if fit is None: raise ValueError('No se reconocen las 30 filas de una columna.')
        y,pitch,near,ids=fit
        if first_span is None:
            first_span=(y[0],y[-1])
            if any((start-y[0])*(end-y[-1])>0 and abs(start-y[0])>pitch*.6 and abs(end-y[-1])>pitch*.6 and cost<best_cost+.10 for start,end,cost in candidates): raise ValueError('Numeración de filas ambigua.')
        row=np.arange(30); good=near<pitch*.24; chosen=mids[ids]
        # Smooth quadratic follows bent pages while remaining monotonic.
        px=np.polyval(np.polyfit(row[good],chosen[good,0],2),row)
        yy=np.polyval(np.polyfit(row[good],chosen[good,1],2),row)
        # Initial horizontal pitch from triplet neighbors.
        gaps=[]
        for m in chosen[good]:
            diff=p-m; cand=abs(diff[:,0][(abs(diff[:,1])<9)&(abs(diff[:,0])>23)&(abs(diff[:,0])<47)])
            gaps.extend(cand.tolist())
        gap=float(np.median(gaps))
        pred=np.stack([np.column_stack([px+gap*j,yy]) for j in (-1,0,1)],axis=1)
        flat=pred.reshape(-1,2); dist=np.linalg.norm(flat[:,None,:]-p[None,:,:],axis=2); ix=dist.argmin(1); dd=dist.min(1).reshape(30,3)
        observed=p[ix].reshape(30,3,2); goodcells=dd<min(10,pitch*.30)
        if goodcells.sum()<64 or (goodcells.sum(1)>=2).sum()<25: raise ValueError('Alineación local insuficiente.')
        # Fit each option's curvature, then apply observed row offsets where supported.
        for j in range(3):
            keep=goodcells[:,j]
            if keep.sum()<17: raise ValueError('Casillas de una opción insuficientes.')
            for k in range(2): pred[:,j,k]=np.polyval(np.polyfit(row[keep],observed[keep,j,k],2),row)
        for i in range(30):
            ok=goodcells[i]
            if ok.sum()>=2:
                shift=np.median(observed[i,ok]-pred[i,ok],axis=0)
                if np.linalg.norm(shift)<pitch*.24: pred[i]+=shift
        if np.any(np.diff(pred[:,:,0],axis=1)<22) or np.any(np.diff(pred[:,:,0],axis=1)>48) or np.any(np.diff(pred[:,:,1],axis=0)<pitch*.65): raise ValueError('Separación de casillas no válida.')
        for i,pts in enumerate(pred): groups.append((str(col*30+i+1),[tuple(map(int,xy)) for xy in np.round(pts)]))
    return groups


def _shape_response(im):
    """Printed outline evidence, independent of the blue answer ink."""
    g=cv.cvtColor(im,cv.COLOR_RGB2GRAY).astype(np.float32)
    yy,xx=np.mgrid[-21:22,-21:22]
    maps=[]
    for radius in (np.hypot(xx,yy),np.maximum(abs(xx),abs(yy))):
        scores=[]
        for r in (6.5,8.,9.5,11.,12.5,14.):
            ring=np.exp(-.5*((radius-r)/1.1)**2)
            outside=np.exp(-.5*((radius-r-3.1)/1.15)**2)
            kernel=(outside/outside.sum()-ring/ring.sum()).astype(np.float32)
            scores.append(cv.filter2D(g,-1,kernel))
        maps.append(np.maximum.reduce(scores))
    return maps


def outline_circle_positions(im, evidence=None):
    """Recover the 30 rows in each column from actual printed three-circle outlines.

    A strong circle triplet is a row anchor, not just a match to a global warp.
    Compare complete row sequences, reject competing row numbering, interpolate
    missing weak outlines, and refine individual centers with bounded offsets.
    """
    ring,square=_shape_response(im) if evidence is None else evidence
    groups=[]; previous_span=None
    for col in range(4):
        mid=list(locations(0))[col*30][1][1]
        x=np.arange(max(50,mid-85),min(WIDTH-55,mid+95)); y=np.arange(250,1580)
        best=np.full((len(y),len(x)),-100.,np.float32); gapmap=np.zeros(best.shape,np.int16)
        for gap in range(26,46):
            a=ring[250:1580,x-gap]; b=ring[250:1580,x]; c=ring[250:1580,x+gap]
            score=(a+b+c)/3-.35*(np.maximum(np.maximum(a,b),c)-np.minimum(np.minimum(a,b),c))-.035*abs(gap-34)-.012*abs(x-mid)[None,:]
            choose=score>best; best[choose]=score[choose]; gapmap[choose]=gap
        # Restrict to the horizontal track with the most repeated strong triplets.
        profile=best.max(1); px=best.argmax(1)
        peaks=np.flatnonzero((profile>=cv.dilate(profile.reshape(-1,1),np.ones((19,1),np.uint8)).ravel())&(profile>9))
        if len(peaks)<25: raise ValueError('No se reconocen suficientes filas de círculos.')
        strong=peaks[np.argsort(profile[peaks])[-min(30,len(peaks)):]]
        center=float(np.median(x[px[strong]]))
        if np.sum(abs(x[px[strong]]-center)<32)<23: raise ValueError('Columna de círculos ambigua.')
        keep=abs(x-center)<40
        bx=best[:,keep]; xidx=np.flatnonzero(keep); ix=xidx[bx.argmax(1)]; prof=bx.max(1)
        peaks=np.flatnonzero((prof>=cv.dilate(prof.reshape(-1,1),np.ones((19,1),np.uint8)).ravel())&(prof>9))
        # Fit start/end anchors jointly. The second-order term follows page curvature.
        yp=y[peaks]; row=np.arange(30); fits=[]
        if len(peaks)<25: raise ValueError('Filas insuficientes en una columna.')
        for start in yp[(yp>=275)&(yp<=570)]:
            for end in yp:
                pitch=(end-start)/29
                if not 25<=pitch<=46.5: continue
                if previous_span is not None and (abs(start-previous_span[0])>pitch*.60 or abs(end-previous_span[1])>pitch*.60): continue
                for bend in np.arange(-.12,.121,.02):
                    pred=start+row*pitch+bend*row*(row-29)
                    delta=abs(pred[:,None]-yp[None,:]); ids=delta.argmin(1); dist=delta.min(1)
                    valid=dist<pitch*.26
                    if valid.sum()<26 or len(set(ids[valid]))!=valid.sum(): continue
                    sel=peaks[ids]; strength=prof[sel]
                    if min(strength[0],strength[-1])<max(10,.43*np.median(strength[valid])): continue
                    # Prefer the full sequence of strong outlines; weak/noisy header or footer cannot replace a row.
                    value=np.where(valid,np.minimum(strength,45)-1.25*dist,-8).mean()
                    value-=.04*np.mean(abs(x[ix[sel[valid]]]-center))
                    fits.append((float(value),pred,sel,valid,pitch))
        if not fits: raise ValueError('No se reconoce la secuencia completa de 30 filas.')
        fits.sort(key=lambda f:f[0],reverse=True)
        value,pred,sel,valid,pitch=fits[0]
        if any(v>value-.75 and abs(p[0]-pred[0])>pitch*.55 and abs(p[-1]-pred[-1])>pitch*.55 for v,p,_,_,_ in fits[1:]):
            raise ValueError('Numeración de filas ambigua.')
        previous_span=(pred[0],pred[-1])
        centers=x[ix[sel]].astype(float); gap=gapmap[sel,ix[sel]].astype(float)
        yy=y[sel].astype(float)
        # Interpolate only missing or unsupported row anchors. Never extrapolate a different number of rows.
        for arr in (centers,gap,yy):
            trend=np.polyval(np.polyfit(row[valid],arr[valid],2),row)
            limit=5 if arr is gap else 10
            ok=valid&(abs(arr-trend)<limit)
            arr[~ok]=trend[~ok]
        pts=np.stack([np.column_stack([centers+gap*j,yy]) for j in (-1,0,1)],axis=1)
        pts=np.rint(pts).astype(int)
        # Recover small differences in height within a row, without jumping to adjacent cells.
        for i in range(30):
            for j in range(3):
                xx0,yy0=pts[i,j]; rad=5
                patch=ring[yy0-rad:yy0+rad+1,xx0-rad:xx0+rad+1]
                gy,gx=np.mgrid[-rad:rad+1,-rad:rad+1]
                a,b=np.unravel_index(np.argmax(patch-.65*np.hypot(gx,gy)),patch.shape)
                pts[i,j]+=[b-rad,a-rad]
        xx,yy=pts[:,:,0],pts[:,:,1]; strength=ring[yy,xx]; shape=strength-square[yy,xx]
        if (np.median(strength)<12 or (strength>8).sum()<75 or ((strength>8).sum(1)>=2).sum()<28
                or np.median(shape)<.35 or (shape>0).sum()<48
                or np.any(np.diff(xx,axis=1)<20) or np.any(np.diff(xx,axis=1)>50)
                or np.any(np.diff(yy,axis=0)<pitch*.55) or np.any(np.diff(yy,axis=0)>pitch*1.5)):
            raise ValueError('No se confirma la forma o alineación de todos los círculos.')
        groups.extend((str(col*30+i+1),[tuple(map(int,p)) for p in pts[i]]) for i in range(30))
    return groups


def _verified_circle_positions(im, groups, evidence):
    """Validate every column of a fallback instead of accepting page-average support."""
    ring,square=evidence
    result=[]
    for col in range(4):
        block=groups[col*30:(col+1)*30]; pts=np.array([p for _,p in block],int)
        pitch=float(np.median(np.diff(pts[:,:,1],axis=0))); gap=float(np.median(np.diff(pts[:,:,0],axis=1)))
        dx=round(gap*.70); dy=round(pitch*.42)
        shifts=np.array([(x,y) for y in range(-dy,dy+1) for x in range(-dx,dx+1)])
        cand=pts[:,None,:,:]+shifts[None,:,None,:]
        vals=ring[np.clip(cand[...,1],0,HEIGHT-1),np.clip(cand[...,0],0,WIDTH-1)]
        score=vals.mean(2)-.35*np.ptp(vals,axis=2)-.04*np.linalg.norm(shifts,axis=1)
        ids=np.argsort(score,axis=1)[:,-60:]; offsets=shifts[ids]; val=np.take_along_axis(score,ids,axis=1)
        dp=val[0]; back=[]
        for i in range(1,30):
            cost=dp[:,None]-.9*np.linalg.norm(offsets[i-1,:,None,:]-offsets[i,None,:,:],axis=2)
            back.append(cost.argmax(0)); dp=val[i]+cost.max(0)
        k=dp.argmax(); track=[k]
        for b in reversed(back): k=b[k]; track.append(k)
        moved=offsets[np.arange(30),track[::-1]]; new=pts+moved[:,None,:]
        # A solution at the boundary is not a verified row match; it can mean an entire row was missed.
        if (abs(moved[:,1])>=dy-1).sum()>3 or (abs(moved[:,0])>=dx-1).sum()>3:
            raise ValueError('La alineación de una columna es insuficiente.')
        for i in range(30):
            for j in range(3):
                x,y=new[i,j]; r=4; patch=ring[y-r:y+r+1,x-r:x+r+1]
                gy,gx=np.mgrid[-r:r+1,-r:r+1]
                a,b=np.unravel_index(np.argmax(patch-.7*np.hypot(gx,gy)),patch.shape); new[i,j]+=[b-r,a-r]
        x,y=new[:,:,0],new[:,:,1]; strength=ring[y,x]; shape=strength-square[y,x]
        if (np.median(strength)<12 or (strength>8).sum()<75 or ((strength>8).sum(1)>=2).sum()<28
                or np.median(shape)<.35 or (shape>0).sum()<48
                or np.any(np.diff(y,axis=0)<pitch*.55) or np.any(np.diff(y,axis=0)>pitch*1.5)
                or np.any(np.diff(x,axis=1)<20) or np.any(np.diff(x,axis=1)>50)):
            raise ValueError('La alineación local no se ha podido verificar.')
        result.extend((block[i][0],[tuple(map(int,p)) for p in new[i]]) for i in range(30))
    return result


def grid_positions(im,page):
    if page!=0: return _legacy_grid_positions(im,page)
    evidence=_shape_response(im)
    # Prefer a full per-column outline lattice. The fallback is also checked and refined
    # per column; never silently accept the global warp on its own.
    try: return outline_circle_positions(im,evidence)
    except ValueError: pass
    for detector in (local_circle_positions,lambda a:_legacy_grid_positions(a,0)):
        try: return _verified_circle_positions(im,detector(im),evidence)
        except ValueError: pass
    raise ValueError('No se confirma la alineación de las cuatro columnas de círculos.')

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
            xy=cv.perspectiveTransform(bounds,inv)[0]
            crop,quad=row_geometry(xy)
            marks.append(Mark('',suggestion,status,tuple(scores),tuple(reds),crop,quad))
        blocks.append(((x,y,w,h),marks))
    if not blocks: raise ValueError('No se reconocen bloques de casillas cuadradas con suficiente seguridad.')
    # Sort groups left to right, then top to bottom for groups sharing the same column.
    blocks.sort(key=lambda b:(b[0][0]//35,b[0][1]))
    return blocks


def row_geometry(points):
    q=np.asarray(points,np.float32).reshape(4,2)
    q[:,0]=np.clip(q[:,0],0,WIDTH-1); q[:,1]=np.clip(q[:,1],0,HEIGHT-1)
    x1,y1=np.floor(q.min(0)).astype(int); x2,y2=np.ceil(q.max(0)).astype(int)+1
    crop=tuple(map(int,(x1,y1,x2,y2)))
    if not cv.isContourConvex(q) or cv.contourArea(q)<4: return crop,()
    return crop,tuple(tuple(float(v) for v in point) for point in q)


def crop_image(im,mark):
    """Display one row level, without borrowing pixels from adjacent rows."""
    if mark.quad:
        q=np.float32(mark.quad)
        w=max(2,round(max(np.linalg.norm(q[1]-q[0]),np.linalg.norm(q[2]-q[3]))))
        h=max(2,round(max(np.linalg.norm(q[3]-q[0]),np.linalg.norm(q[2]-q[1]))))
        dst=np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])
        return cv.warpPerspective(im,cv.getPerspectiveTransform(q,dst),(w,h),borderMode=cv.BORDER_REPLICATE)
    x,y,x2,y2=mark.crop
    return im[y:y2,x:x2]


def draw_mark(im,mark):
    if mark.quad:
        cv.polylines(im,[np.round(mark.quad).astype(np.int32)],True,(28,167,112),2)
    else:
        x,y,x2,y2=mark.crop; cv.rectangle(im,(x,y),(x2-1,y2-1),(28,167,112),2)


def original_canvas(im):
    """Fit the photo to archive dimensions without rotating or stretching it."""
    h,w=im.shape[:2]; scale=min(WIDTH/w,HEIGHT/h)
    dx=(WIDTH-w*scale)/2; dy=(HEIGHT-h*scale)/2
    mat=np.float32([[scale,0,dx],[0,scale,dy],[0,0,1]])
    return cv.warpPerspective(im,mat,(WIDTH,HEIGHT),borderValue=(255,255,255)),mat


def square_page(im,aligned=None):
    """Prefer the untouched photo geometry. Keep the existing rectified detector
    as a fallback, and map its rows back onto the original view if needed."""
    canvas,mat=original_canvas(im)
    if aligned is None: aligned=align(im)
    try: raw=square_blocks(canvas)
    except ValueError: raw=[]
    try: warped=square_blocks(aligned)
    except ValueError: warped=[]
    if not raw and not warped: raise ValueError('No se reconocen bloques de casillas cuadradas con suficiente seguridad.')
    def shape(blocks): return [(len(ms),len(ms[0].scores)) for _,ms in blocks]
    def readings(blocks): return [proposed(m) for _,ms in blocks for m in ms]
    # Preserve the proven reading if both candidates cover the same rows but disagree.
    if raw and (not warped or (shape(raw)==shape(warped) and readings(raw)==readings(warped))):
        return canvas,raw
    dst=np.float32([[0,0],[WIDTH-1,0],[WIDTH-1,HEIGHT-1],[0,HEIGHT-1]])
    back=mat @ cv.getPerspectiveTransform(dst,detect_corners(im))
    result=[]
    for (x,y,w,h),marks in warped:
        mapped=[]
        for m in marks:
            x1,y1,x2,y2=m.crop
            q=m.quad or ((x1,y1),(x2-1,y1),(x2-1,y2-1),(x1,y2-1))
            crop,quad=row_geometry(cv.perspectiveTransform(np.float32([q]),back)[0])
            mapped.append(replace(m,crop=crop,quad=quad))
        # Bounds for the numbering preview (not used for sampling).
        x1=min(m.crop[0] for m in mapped); y1=min(m.crop[1] for m in mapped)
        x2=max(m.crop[2] for m in mapped); y2=max(m.crop[3] for m in mapped)
        result.append(((x1,y1,x2-x1,y2-y1),mapped))
    return canvas,result


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
    for jrow,row in enumerate(centers):
        scores=[]; reds=[]
        for x,y in np.round(row).astype(int):
            sl=np.s_[max(0,y-r):y+r+1,max(0,x-r):x+r+1]; scores.append(int(blue[sl].sum())); reds.append(int(red[sl].sum()))
        high,second=sorted(range(options),key=lambda j:scores[j],reverse=True)[:2]; s=scores[high]
        suggestion='ABCDE'[high] if s>=12 and scores[second]<max(12,.35*s) else ''
        status='Azul detectado' if suggestion else 'Doble o dudosa' if s>=12 else 'Sin azul: revisar blanco u otra tinta'
        if suggestion and s<25: status='Azul débil: revisar'
        if max(reds)>20: status+=' · posible rojo'
        bounds=np.float32([[[-.46,jrow-.46],[options-1+.46,jrow-.46],[options-1+.46,jrow+.46],[-.46,jrow+.46]]])
        crop,quad=row_geometry(cv.perspectiveTransform(bounds,mat)[0])
        marks.append(Mark('',suggestion,status,tuple(scores),tuple(reds),crop,quad))
    return number_blocks([((0,0,0,0),marks)],[start])
