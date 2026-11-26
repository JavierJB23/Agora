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

def geometry_gray(im):
    """A geometry-only channel: darken saturated printing even on pale paper."""
    gray=cv.cvtColor(im,cv.COLOR_RGB2GRAY)
    return np.minimum(gray, im.min(axis=2))


def remove_print_ink(im, blue, red, rows, radius):
    """Exclude a repeated printed hue from mark masks, not the original pixels.

    A genuine single-answer mark cannot occupy most of all printed cells.
    Preserve substantially darker pixels of the same hue (e.g. dark pen on a
    pale blue template). Colors indistinguishable from printing remain a limit.
    """
    hsv=cv.cvtColor(im,cv.COLOR_RGB2HSV); hue,sat,val=hsv.transpose(2,0,1)
    cells=[]; h,w=im.shape[:2]
    for row in rows:
        for x,y in row:
            x,y=round(x),round(y)
            sl=np.s_[max(0,y-radius):min(h,y+radius+1),max(0,x-radius):min(w,x+radius+1)]
            if hue[sl].size: cells.append(sl)
    if len(cells)<8: return blue,red
    for center in range(0,180,10):
        distance=abs(hue.astype(np.int16)-center); near=(np.minimum(distance,180-distance)<=8)&(sat>=40)
        counts=np.array([near[sl].sum() for sl in cells]); supported=counts>=max(3,radius*.35)
        if supported.mean()<.60: continue
        values=np.concatenate([val[sl][near[sl]] for sl,ok in zip(cells,supported) if ok])
        if not len(values): continue
        cutoff=max(0,int(np.percentile(values,12))-35)
        printed=near&(val>=cutoff)
        blue=blue&~printed; red=red&~printed
    return blue,red


def red_strike(im, mark, blue_ink=False):
    """Detect a long red stroke across a row, not an isolated red correction X.
    Work in the same horizontal row crop shown to the user, including gaps.
    """
    a=crop_image(im,mark).astype(np.int16)
    h,w=a.shape[:2]
    if h<6 or w<20: return False
    r,g,b=a.transpose(2,0,1)
    # Reject pink/magenta printing and broad tinted backgrounds; a pen stroke
    # must be locally darker than its surroundings.
    gray=cv.cvtColor(a.astype(np.uint8),cv.COLOR_RGB2GRAY).astype(np.int16)
    k=max(5, min(15, (h//3)|1))
    background=cv.medianBlur(gray.astype(np.uint8),k).astype(np.int16)
    mask=((r-g>=9)&(r-b>=8)&(g<225)&(r<252)&(r-b>=1.25*np.maximum(b-g,0))&((background-gray)>=5)).astype(np.uint8)
    if blue_ink:
        mask=((b-r>=4)&(b-g>=6)&(r<190)&((background-gray)>=5)).astype(np.uint8)
    # A stroke may be interrupted by dark printed outlines. Vote along near-horizontal lines.
    yy,xx=np.nonzero(mask)
    if len(xx)<w*.35: return False
    for slope in np.linspace(-.20,.20,17):
        intercept=np.round(yy-slope*(xx-w/2)).astype(int)
        for center in range(round(h*.20),round(h*.80)+1):
            take=np.abs(intercept-center)<=max(1,round(h*.065))
            cols=np.unique(xx[take]); bins=np.unique(np.minimum(9,cols*10//w))
            # Ink must cross the empty gaps between adjacent printed outlines.
            n=len(mark.scores); gaps=[(j+1)/n for j in range(n-1)]
            bridges=all(sum(abs(cols/w-gap)<.035)>=max(2,round(w*.028)) for gap in gaps)
            if bridges and len(cols)>=w*.48 and len(bins)>=8 and bins[0]<=1 and bins[-1]>=8:
                return True
    return False


def flag_strikes(im, marks):
    return [replace(m,status='Posible anulada · tachadura roja · revisar') if red_strike(im,m) else m for m in marks]


def proposed(mark):
    if 'Posible anulada' in mark.status: return ''
    if mark.suggestion and 'débil' not in mark.status: return mark.suggestion
    if not mark.suggestion and max(mark.scores)<5 and max(mark.red)<=20: return '-'
    return ''

def scan(im,page,positions=None):
    if page not in (0,1) or im.shape[:2]!=(HEIGHT,WIDTH): raise ValueError('Página no válida.')
    a=im.astype(np.int16); R,G,B=a.transpose(2,0,1)
    blue=(B-R>5)&(B-G>7)&(B<220)&(R<180)
    red=(R-B>18)&(R-G>18)&(G<180)&(B-G<35)&(R<205)
    gray=geometry_gray(im)
    out=[]; present=0
    positions=centers(im,page) if positions is None else positions
    blue,red=remove_print_ink(im,blue,red,[pts for _,pts in positions],14)
    for number,points in positions:
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
    return flag_strikes(im,out)

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
    g=geometry_gray(im)
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
        a=cv.warpPerspective(im,mat,(w,h)); gray=geometry_gray(a)
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
        blue,red=remove_print_ink(a,blue,red,rows,max(3,round(size*.32)))
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
        blocks.append(((x,y,w,h),flag_strikes(im,marks)))
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


def flexible_outline_blocks(im, minimum_options=2):
    """Fallback for unboxed regular rows of circles or squares at new positions.

    Find repeated closed outlines, then group tracks with similar horizontal
    spacing and shared row heights. Only accept a complete, regular lattice.
    """
    gray=geometry_gray(im)
    mask=cv.adaptiveThreshold(gray,255,cv.ADAPTIVE_THRESH_GAUSSIAN_C,cv.THRESH_BINARY_INV,31,7)
    contours,_=cv.findContours(mask,cv.RETR_LIST,cv.CHAIN_APPROX_SIMPLE)
    pts=[]
    for c in contours:
        x,y,w,h=cv.boundingRect(c); area=cv.contourArea(c); perimeter=cv.arcLength(c,True)
        if not (10<=w<=43 and 10<=h<=43 and .72<=w/h<=1.39 and .50<=area/(w*h)<=1 and perimeter>0 and 4*np.pi*area/perimeter**2>.55): continue
        pts.append((x+w/2,y+h/2,(w+h)/2))
    if len(pts)<12: raise ValueError('No se encuentran suficientes contornos impresos.')
    # Deduplicate inner and outer contours, keeping the larger outline.
    keep=[]
    for p in sorted(pts,key=lambda v:-v[2]):
        if not any(abs(p[0]-q[0])<5 and abs(p[1]-q[1])<5 for q in keep): keep.append(p)
    p=np.array(keep); size=float(np.median(p[:,2])); tol=max(4,size*.40)
    peaks=[(x,n) for x,n in _clusters(p[:,0],tol) if n>=max(3,min(8,len(p)*.025))]
    if len(peaks)<minimum_options: raise ValueError('No se reconocen columnas repetidas.')
    # Partition x tracks where a large gap separates columns of answers.
    tracks=[]
    for x,n in peaks:
        if not tracks or x-tracks[-1][-1]>size*2.9: tracks.append([x])
        else: tracks[-1].append(x)
    blocks=[]
    for xs in tracks:
        if not minimum_options<=len(xs)<=5: continue
        gaps=np.diff(xs); step=float(np.median(gaps))
        if not size*.85<=step<=size*2.9 or np.max(abs(gaps-step))>step*.24: continue
        ys=[]; columns=[]
        for x in xs:
            col=p[abs(p[:,0]-x)<tol*1.5]; columns.append(col)
            ys.extend(col[:,1])
        rows=[]
        for y,n in _clusters(ys,max(4,size*.48)):
            row=[]
            for x,col in zip(xs,columns):
                near=col[abs(col[:,1]-y)<size*.48]
                if len(near):
                    v=near[np.argmin(abs(near[:,1]-y)+abs(near[:,0]-x))]; row.append((v[0],v[1]))
                else: row.append(None)
            if sum(v is not None for v in row)>=max(2,len(xs)-1): rows.append((y,row))
        if not 3<=len(rows)<=120: continue
        # Split separate vertically stacked blocks by gaps; reject missing internal rows.
        pitch=float(np.median(np.diff([y for y,_ in rows])))
        if not size*.85<=pitch<=size*3.5: continue
        runs=[]
        for y,row in rows:
            if not runs or y-runs[-1][-1][0]>pitch*1.7: runs.append([])
            runs[-1].append((y,row))
        for run in runs:
            if len(run)<3 or np.any(abs(np.diff([y for y,_ in run])-pitch)>pitch*.32): continue
            if sum(v is not None for _,row in run for v in row)<len(run)*len(xs)*.85: continue
            # Sample each row independently; use actual centers where available.
            marks=[]; radius=max(3,min(14,round(min(step,pitch)*.29)))
            centers=[[(x,y) if v is None else v for x,v in zip(xs,row)] for y,row in run]
            rgb=im.astype(np.int16); R,G,B=rgb.transpose(2,0,1)
            blue=(B-R>5)&(B-G>7)&(B<225)&(R<190); red=(R-B>18)&(R-G>18)&(G<180)&(B-G<35)&(R<205)
            blue,red=remove_print_ink(im,blue,red,centers,radius)
            for row in centers:
                scores=[]; reds=[]
                for x,y in row:
                    x,y=round(x),round(y); sl=np.s_[max(0,y-radius):y+radius+1,max(0,x-radius):x+radius+1]
                    scores.append(int(blue[sl].sum())); reds.append(int(red[sl].sum()))
                high,second=sorted(range(len(xs)),key=lambda j:scores[j],reverse=True)[:2]; score=scores[high]
                minimum=max(5,round(radius*.9)); strong=max(12,round(radius*2))
                suggestion='ABCDE'[high] if score>=minimum and scores[second]<max(minimum,.35*score) else ''
                status='Azul detectado' if suggestion else 'Doble o dudosa' if score>=minimum else 'Sin azul: revisar blanco u otra tinta'
                if suggestion and score<strong: status='Azul débil: revisar'
                if max(reds)>8: status+=' · posible rojo'
                x1,y1=row[0]; x2,y2=row[-1]; margin=size*.65
                crop,quad=row_geometry([(x1-margin,y1-pitch*.43),(x2+margin,y2-pitch*.43),(x2+margin,y2+pitch*.43),(x1-margin,y1+pitch*.43)])
                marks.append(Mark('',suggestion,status,tuple(scores),tuple(reds),crop,quad))
            x1=min(m.crop[0] for m in marks); y1=min(m.crop[1] for m in marks); x2=max(m.crop[2] for m in marks); y2=max(m.crop[3] for m in marks)
            blocks.append(((x1,y1,x2-x1,y2-y1),flag_strikes(im,marks)))
    if not blocks: raise ValueError('No se reconoce una cuadrícula regular de casillas.')
    return sorted(blocks,key=lambda b:(b[0][0],b[0][1]))


def automatic_numbering(blocks, questions, reserves=0, previous=None):
    """Use saved numbering if geometry matches; otherwise standard column order.

    A complete ordinary page may have unused trailing printed rows. Never infer
    reserve labels merely from those extra rows. Distinct reserve blocks are
    recognized only when the configured counts match their separate geometry.
    """
    sizes=[len(ms) for _,ms in blocks]
    if not sizes or any(n<1 for n in sizes): raise ValueError('No hay bloques completos.')
    if previous:
        old=reading_blocks(previous)
        if [(len(b),len(b[0].scores)) for b in old]==[(len(ms),len(ms[0].scores)) for _,ms in blocks]:
            return number_blocks(blocks,[b[0].number for b in old])
    if sum(sizes)<questions:
        raise ValueError('La hoja no cubre todas las preguntas ordinarias. No se puede verificar su numeración automáticamente.')
    starts=[]; n=1; r=1
    # Infer reserves only when separate blocks start exactly at the configured
    # boundary and their sizes are clearly distinct from the ordinary columns.
    split=next((i for i in range(1,len(sizes)) if sum(sizes[:i])==questions and sum(sizes[i:])==reserves and max(sizes[i:])<max(sizes[:i])),None) if reserves else None
    for i,size in enumerate(sizes):
        if split is not None and i>=split: starts.append('R'+str(r)); r+=size
        else: starts.append(str(n)); n+=size
    return number_blocks(blocks,starts)


def header_end(gray, x, half=34):
    """Locate a broad printed header locally, independent of hue or tilt.
    Unlike isolated letters or marks, the dark bar covers most of the strip.
    Return its lower edge, or None when there is no reliable header."""
    x=int(x); a=max(0,x-half); b=min(gray.shape[1],x+half+1)
    profile=np.median(gray[:,a:b],axis=1).astype(np.float32)
    base=cv.dilate(profile[:,None],np.ones((81,1),np.uint8)).ravel()
    dark=(base-profile>48)&(profile<160)
    dark[:260]=False; dark[620:]=False
    runs=np.split(np.flatnonzero(dark),np.where(np.diff(np.flatnonzero(dark))>1)[0]+1)
    candidates=[r for r in runs if 10<=len(r)<=55 and r[-1]<619]
    if not candidates: return None
    best=max(candidates,key=lambda r:float(np.mean(base[r]-profile[r]))*min(len(r),22))
    return int(best[-1])


def repeated_circle_rows(im):
    """Find complete tracks of repeated printed triplets, using geometry alone.
    Missing/tachured rows are interpolated, never removed from numbering."""
    gray=geometry_gray(im)
    mask=cv.adaptiveThreshold(gray,255,cv.ADAPTIVE_THRESH_GAUSSIAN_C,cv.THRESH_BINARY_INV,31,8)
    mask=cv.morphologyEx(mask,cv.MORPH_CLOSE,np.ones((3,21),np.uint8))
    mask=cv.morphologyEx(mask,cv.MORPH_OPEN,np.ones((3,45),np.uint8))
    contours,_=cv.findContours(mask,cv.RETR_EXTERNAL,cv.CHAIN_APPROX_SIMPLE)
    boxes=np.array([b for c in contours if 48<(b:=cv.boundingRect(c))[2]<130 and 5<b[3]<30 and 270<b[1]<1580 and b[2]/b[3]>3])
    if len(boxes)<64: raise ValueError('No hay cuatro secuencias de filas completas.')
    pts=np.column_stack([boxes[:,0]+boxes[:,2]/2,boxes[:,1]+boxes[:,3]/2,boxes[:,2],boxes[:,3]])
    tracks=[]
    for _ in range(4):
        if len(pts)<16: raise ValueError('Faltan columnas.')
        xs=pts[:,0]; best=xs[np.argmax((abs(xs[:,None]-xs)<45).sum(0))]
        group=pts[abs(xs-best)<55]; pts=pts[abs(xs-best)>=90]
        if len(group)<16: raise ValueError('Columna incompleta.')
        tracks.append(group)
    tracks.sort(key=lambda g:np.median(g[:,0]))
    gaps=np.diff([np.median(g[:,0]) for g in tracks]);
    if min(gaps)<120 or max(gaps)>min(gaps)*1.4: raise ValueError('Separación de columnas irregular.')
    # Fit all 30 row indices, including missing rows, with a quadratic pitch model.
    ring,square=_shape_response(np.repeat(gray[...,None],3,axis=2)); output=[]; span=None
    headers=[header_end(gray,np.median(g[:,0])) for g in tracks]
    anchored=all(h is not None for h in headers) and max(headers)-min(headers)<160
    for col,g in enumerate(tracks):
        med=np.median(g,axis=0); rr=np.arange(30)
        # The horizontal morphology is only a coarse seed. Find triplets by
        # their real outlines, including rows whose ink hides a component.
        xs=np.arange(max(60,round(med[0]-55)),min(WIDTH-60,round(med[0]+56)))
        ys=np.arange(270,1580); gap0=med[2]/2.67
        best=np.full((len(ys),len(xs)),-100.,np.float32); steps=np.zeros(best.shape,np.int16)
        for gap in range(max(18,round(gap0-7)),min(45,round(gap0+8))):
            l=ring[270:1580,xs-gap]; c=ring[270:1580,xs]; r=ring[270:1580,xs+gap]
            score=(l+c+r)/3-.30*(np.maximum(np.maximum(l,c),r)-np.minimum(np.minimum(l,c),r))-.10*abs(gap-gap0)
            choose=score>best; best[choose]=score[choose]; steps[choose]=gap
        prof=best.max(1); ix=best.argmax(1)
        peaks=np.flatnonzero((prof>=cv.dilate(prof[:,None],np.ones((17,1),np.uint8)).ravel())&(prof>6))
        if len(peaks)<25: raise ValueError('Filas insuficientes.')
        # A header may produce strong pseudo-circles from its lettering. Unlike
        # a real answer row, its entire left-hand gap is filled with printing.
        # Compare that strip against nearby paper, not against an absolute hue.
        def is_header(k):
            cy=int(ys[k]); cx=int(xs[ix[k]]); gap=int(steps[k,ix[k]])
            x1=max(0,cx-round(3.4*gap)); x2=max(x1+1,cx-round(1.65*gap))
            strip=gray[cy-4:cy+5,x1:x2]; context=gray[max(0,cy-36):cy+37,x1:x2]
            return float(np.median(strip))+27<float(np.percentile(context,75))
        peaks=np.array([k for k in peaks if not is_header(k)],dtype=int)
        if len(peaks)<25: raise ValueError('Filas insuficientes tras excluir cabeceras.')
        y=ys[peaks]; strengths=prof[peaks]
        anchor=headers[col] if anchored else None
        if anchor is not None:
            starts=np.arange(anchor+5,anchor+40,1)
        else:
            starts=np.arange(290,570,2) if span is None else np.arange(max(270,span[0]-25),span[0]+26,2)
        pitch=np.arange(24,45,.5); bend=np.arange(-.14,.141,.025)
        s,p,b=np.meshgrid(starts,pitch,bend,indexing='ij'); s,p,b=s.ravel(),p.ravel(),b.ravel()
        pred=s[:,None]+p[:,None]*rr+b[:,None]*rr*(rr-29)
        if span is not None and not anchored:
            keep=(abs(pred[:,-1]-span[1])<45); pred=pred[keep]; p=p[keep]
        if not len(pred): raise ValueError('No coincide la numeración de columnas.')
        jj=np.searchsorted(y,pred); l=np.clip(jj-1,0,len(y)-1); r=np.clip(jj,0,len(y)-1); ids=np.where(abs(y[l]-pred)<=abs(y[r]-pred),l,r)
        d=abs(y[ids]-pred); valid=d<p[:,None]*.27
        score=np.where(valid,np.minimum(strengths[ids],45)-1.3*d,-8).sum(1)
        if anchor is not None:
            offset=(pred[:,0]-anchor)/p
            score-=np.abs(offset-.50)*35
            score[(offset<.24)|(offset>.90)]=-1e6
        elif span is not None: score-=.45*(abs(pred[:,0]-span[0])+abs(pred[:,-1]-span[1]))
        score[(valid.sum(1)<25)|~valid[:,0]|~valid[:,-1]]=-1e6
        k=int(score.argmax())
        if score[k]<200: raise ValueError('Secuencia de filas no verificada.')
        sel=peaks[ids[k]]; good=valid[k]; py=pred[k]; span=(py[0],py[-1]) if span is None else span
        xx=xs[ix[sel]].astype(float); yy=ys[sel].astype(float); widths=steps[sel,ix[sel]].astype(float)
        for arr,limit in [(xx,10),(yy,8),(widths,5)]:
            trend=np.polyval(np.polyfit(rr[good],arr[good],2),rr)
            ok=good&(abs(arr-trend)<limit); arr[~ok]=trend[~ok]
        for i in range(30):
            row=[]
            for j in (-1,0,1):
                x0,y0=round(xx[i]+j*widths[i]),round(yy[i]); rad=5
                patch=ring[y0-rad:y0+rad+1,x0-rad:x0+rad+1]; gy,gx=np.mgrid[-rad:rad+1,-rad:rad+1]
                a,b=np.unravel_index(np.argmax(patch-.65*np.hypot(gx,gy)),patch.shape); row.append((x0+b-rad,y0+a-rad))
            output.append(row)
    pp=np.array(output); xx,yy=pp[:,:,0],pp[:,:,1]; strengths=ring[yy,xx]; shapes=strengths-square[yy,xx]
    if any((strengths[i:i+30]>7).sum()<65 or np.median(shapes[i:i+30])<.2 for i in range(0,120,30)):
        raise ValueError('No se confirman los contornos circulares.')
    return [(str(i+1),[tuple(map(int,p)) for p in row]) for i,row in enumerate(pp)]


def extended_strike(im,row):
    """Find a crossing pen line in the normally empty gap before the first option.
    This gap contains no colored outlines, unlike the answer cells themselves.
    Work in row-relative coordinates to tolerate skew, and require continuity
    both across the gap and into the answer area. Return ink color or None."""
    a,b=np.asarray(row[0],float),np.asarray(row[-1],float)
    v=(b-a)/2; gap=float(np.linalg.norm(v)); normal=np.array([-v[1],v[0]])/gap
    q=np.float32([a-v*2.25-normal*gap*.55,b+v*.50-normal*gap*.55,b+v*.50+normal*gap*.55,a-v*2.25+normal*gap*.55])
    if np.any(q<0) or np.any(q[:,0]>=im.shape[1]) or np.any(q[:,1]>=im.shape[0]): return None
    w,h=190,44
    view=cv.warpPerspective(im,cv.getPerspectiveTransform(q,np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]])),(w,h))
    g=cv.cvtColor(view,cv.COLOR_RGB2GRAY).astype(np.int16)
    # Vertical background subtraction: broad printed shading does not vote.
    background=cv.medianBlur(g.astype(np.uint8),11).astype(np.int16)
    R,G,B=view.astype(np.int16).transpose(2,0,1)
    # A narrow dark line in the empty gap is evidence even for a desaturated pen.
    dark=(background-g>=10)&(g<205)
    yy,xx=np.nonzero(dark)
    if not len(xx): return None
    for slope in np.linspace(-.18,.18,19):
        intercept=yy-slope*(xx-90)
        for center in range(14,31):
            take=abs(intercept-center)<=2
            x=xx[take]; y=yy[take]
            left=(x>=8)&(x<=67); across=(x>=82)&(x<=176)
            if len(np.unique(x[left]))<36 or len(np.unique(x[across]))<33: continue
            # Require presence in each of three subdivisions of the empty gap.
            if any(len(np.unique(x[(x>=lo)&(x<hi)]))<8 for lo,hi in [(8,28),(28,48),(48,68)]): continue
            r,g,b=R[y[left],x[left]],G[y[left],x[left]],B[y[left],x[left]]
            if np.median(b-r)>2 and np.median(b-g)>3: return 'azul'
            if np.median(r-b)>3 and np.median(r-g)>5: return 'roja'
            return 'manuscrita'
    return None


def scan_repeated_rows(im, positions, extended=True):
    """Sample within real cells; don't let the printed rim vote for a pen mark."""
    marks=[]; rows=[np.array(p,float) for _,p in positions]
    # Adaptive cell radius from printed pitch; use central region only.
    a=im.astype(np.int16); R,G,B=a.transpose(2,0,1)
    blue=(B-R>3)&(B-G>5)&(B<225)&(R<190)
    red=(R-B>18)&(R-G>18)&(G<190)&(R-B>1.6*np.maximum(B-G,0)+8)&(R<225)
    rad=max(4,round(np.median([np.linalg.norm(np.diff(p,axis=0),axis=1).mean() for p in rows])*.29))
    blue,red=remove_print_ink(im,blue,red,rows,rad)
    for (number,_),row in zip(positions,rows):
        dx=np.linalg.norm(row[-1]-row[0])/2; pitch=dx*1.15; margin=dx*.48
        scores=[]; reds=[]
        for x,y in np.round(row).astype(int):
            sl=np.s_[y-rad:y+rad+1,x-rad:x+rad+1]; scores.append(int(blue[sl].sum())); reds.append(int(red[sl].sum()))
        hi,second=sorted(range(3),key=lambda j:scores[j],reverse=True)[:2]; s=scores[hi]; low=max(6,round(rad*1.3)); strong=max(12,round(rad*1.8))
        suggestion='ABC'[hi] if s>=low and scores[second]<max(low,.40*s) else ''
        status='Azul detectado' if suggestion else 'Doble o dudosa' if s>=low else 'Sin azul: revisar blanco u otra tinta'
        if suggestion and s<strong: status='Azul débil: revisar'
        if max(reds)>max(12,rad*2): status+=' · posible rojo'
        x1,y1=row[0]; x2,y2=row[-1]
        crop,quad=row_geometry([(x1-margin,y1-pitch*.39),(x2+margin,y2-pitch*.39),(x2+margin,y2+pitch*.39),(x1-margin,y1+pitch*.39)])
        m=Mark(number,suggestion,status,tuple(scores),tuple(reds),crop,quad)
        strike=extended_strike(im,row) if extended else None
        if strike: m=replace(m,status=f'Posible anulada · tachadura {strike} · revisar')
        elif red_strike(im,m): m=replace(m,status='Posible anulada · tachadura roja · revisar')
        elif red_strike(im,m,True): m=replace(m,status='Posible anulada · tachadura azul · revisar')
        marks.append(m)
    return marks

def verify_numbered_rows(im, marks):
    """Never accept a dark printed header as an answer or a broken column.
    For the recognizable four-column 30-row family, require full columns and
    validate their starts against the printed headers if present."""
    gray=geometry_gray(im)
    blocks=reading_blocks(marks)
    for m in marks:
        crop=crop_image(im,m)
        if crop.size and min(crop.shape[:2])>=4:
            g=geometry_gray(crop)
            # A filled header has dark ink throughout the crop, unlike bubbles.
            if np.mean(g<150)>.65 and np.median(g)<120 and np.mean((g<150).mean(axis=0)>.70)>.66:
                raise ValueError('Se ha detectado una cabecera como posible respuesta.')
    if len(marks)>=100 and all(len(m.scores)==3 and not m.number.startswith('R') for m in marks):
        # Group by physical x position as well as consecutive numbering. A
        # missed row may split one logical block into multiple fragments.
        centers=[(m.crop[0]+m.crop[2])/2 for m in marks]
        width=float(np.median([m.crop[2]-m.crop[0] for m in marks]))
        groups=[]
        for x,m in sorted(zip(centers,marks),key=lambda t:t[0]):
            if not groups or x-np.median([a for a,_ in groups[-1]])>width*.85: groups.append([])
            groups[-1].append((x,m))
        if len(groups)==4:
            headers=[header_end(gray,np.median([x for x,_ in g])) for g in groups]
            if all(h is not None for h in headers):
                if len(blocks)!=4 or max(map(len,groups))-min(map(len,groups))>1:
                    raise ValueError('No se ha podido verificar la numeración completa de las columnas.')
                for b,h in zip(groups,headers):
                    ys=np.sort([(m.crop[1]+m.crop[3])/2 for _,m in b]); pitch=float(np.median(np.diff(ys)))
                    if pitch<=0 or not .15*pitch<ys[0]-h<1.1*pitch or np.any(abs(np.diff(ys)-pitch)>.48*pitch):
                        raise ValueError('La primera fila o la secuencia de preguntas no coincide con la cabecera.')
    return marks


def automatic_page(im, questions, reserves=0, options=3, previous=None):
    """Try independent normalizations; only install a verified row sequence."""
    aligned=align(im)
    raw=original_canvas(im)[0]
    errors=[]
    if options<=3 and questions<=120:
        # Preserve the actual camera aspect ratio first; a global paper warp
        # can introduce artifacts when the photographed page is curved.
        for candidate in (raw,aligned):
            try:
                positions=repeated_circle_rows(candidate)
                marks=scan_repeated_rows(candidate,positions)
                return candidate,verify_numbered_rows(candidate,marks)
            except ValueError as e: errors.append(str(e))
    for candidate in (aligned,raw):
        try:
            slot=identify(candidate)
            if options>3 or (slot==0 and questions>120): raise ValueError('Geometría distinta de la plantilla conocida.')
            positions=grid_positions(candidate,slot)
            marks=scan_repeated_rows(candidate,positions) if slot==0 else scan(candidate,slot,positions)
            return candidate,verify_numbered_rows(candidate,marks)
        except ValueError as e: errors.append(str(e))
        contrast=geometry_gray(candidate); gray=cv.cvtColor(candidate,cv.COLOR_RGB2GRAY)
        if float(np.mean(abs(contrast.astype(float)-gray)))>1.5 and options<=3 and questions<=120:
            geom=np.repeat(contrast[...,None],3,axis=2)
            try:
                slot=identify(geom); positions=grid_positions(geom,slot)
                marks=scan_repeated_rows(candidate,positions) if slot==0 else scan(candidate,slot,positions)
                return candidate,verify_numbered_rows(candidate,marks)
            except ValueError as e: errors.append(str(e))
    for detector in (lambda:square_page(im,aligned),lambda:(aligned,flexible_outline_blocks(aligned,options)),lambda:(raw,flexible_outline_blocks(raw,options))):
        try:
            canvas,blocks=detector()
            if any(len(ms[0].scores)<options for _,ms in blocks): raise ValueError('Faltan opciones impresas.')
            marks=automatic_numbering(blocks,questions,reserves,previous)
            return canvas,verify_numbered_rows(canvas,marks)
        except ValueError as e: errors.append(str(e))
    raise ValueError('No se ha podido verificar la estructura y numeración de la hoja. Prueba con otra fotografía o introduce las respuestas manualmente.')


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
    horizontal=np.linalg.norm(np.diff(centers,axis=1),axis=2)
    vertical=np.linalg.norm(np.diff(centers,axis=0),axis=2)
    ratio=float(np.median(horizontal)/max(1.,np.median(vertical)))
    if not .45<=ratio<=2.6:
        raise ValueError('El encuadre no corresponde a una sola columna. Marca únicamente las casillas de un bloque de preguntas.')
    if min(dx,dy)<10: raise ValueError('Las casillas son demasiado pequeñas o la cantidad de filas es incorrecta.')
    r=max(3,min(15,round(min(dx,dy)*.29)))
    a=im.astype(np.int16); R,G,B=a.transpose(2,0,1)
    blue=(B-R>5)&(B-G>7)&(B<225)&(R<190); red=(R-B>18)&(R-G>18)&(G<180)&(B-G<35)&(R<205)
    blue,red=remove_print_ink(im,blue,red,centers,r)
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
    if options==3:
        sampled=scan_repeated_rows(im,[('',row) for row in centers],extended=False)
        marks=[replace(m,suggestion=n.suggestion,status=n.status,scores=n.scores,red=n.red) for m,n in zip(marks,sampled)]
    else:
        marks=flag_strikes(im,marks)
    return number_blocks([((0,0,0,0),marks)],[start])


def reading_blocks(marks):
    """Split numbered rows into contiguous vertical columns on the saved canvas."""
    blocks=[]
    for m in marks:
        if not blocks: blocks.append([m]); continue
        prev=blocks[-1][-1]
        x,y,x2,y2=m.crop; a,b,a2,b2=prev.crop
        height=max(y2-y,b2-b); width=max(x2-x,a2-a)
        consecutive=(m.number.startswith('R')==prev.number.startswith('R') and int(m.number.lstrip('R'))==int(prev.number.lstrip('R'))+1)
        if (consecutive and len(m.scores)==len(prev.scores) and abs((x+x2-a-a2)/2)<width*.45 and 0<(y+y2-b-b2)/2<height*2.5):
            blocks[-1].append(m)
        else: blocks.append([m])
    return blocks


def replace_reading_block(marks, old, new):
    """Adjust just the chosen block; other columns keep their exact readings."""
    if [m.number for m in old]!=[m.number for m in new]: raise ValueError('La numeración del bloque ha cambiado.')
    if any(len(a.scores)!=len(b.scores) for a,b in zip(old,new)): raise ValueError('Las opciones impresas no coinciden.')
    replacements={m.number:m for m in new}
    # Reject a block drawn across other columns, even if its aspect ratio looks plausible.
    others=[m for m in marks if m.number not in replacements]
    for m in new:
        x,y,x2,y2=m.crop
        for n in others:
            a,b,a2,b2=n.crop
            area=max(0,min(x2,a2)-max(x,a))*max(0,min(y2,b2)-max(y,b))
            if area>.25*min((x2-x)*(y2-y),(a2-a)*(b2-b)):
                raise ValueError('El bloque se solapa con otras preguntas. Selecciona solo su columna.')
    return [replacements.get(m.number,m) for m in marks]
