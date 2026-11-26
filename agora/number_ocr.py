"""Local OCR of printed row identifiers, independent from ink classification."""
import csv, os, re, shutil, subprocess, sys
from dataclasses import replace
from io import StringIO
from pathlib import Path
from collections import Counter
from math import ceil
import cv2 as cv
import numpy as np

def engine():
    base=Path(__file__).resolve().parent.parent/'assets'/'ocr'
    bundled=base/'tesseract.exe'
    if bundled.is_file(): return str(bundled), ['--tessdata-dir',str(base/'tessdata')]
    return (None if getattr(sys,'frozen',False) else shutil.which('tesseract')), []

def recognize(image, psm=11):
    exe,extra=engine()
    if not exe: raise RuntimeError('Motor OCR local no disponible.')
    ok,png=cv.imencode('.png',image)
    if not ok: raise RuntimeError('No se pudo preparar el OCR.')
    cmd=[exe,'stdin','stdout',*extra,'-l','eng','--psm',str(psm),'-c','tessedit_char_whitelist=0123456789R-','-c','tessedit_create_tsv=1']
    result=subprocess.run(cmd,input=png.tobytes(),capture_output=True,timeout=25,env=dict(os.environ,OMP_THREAD_LIMIT='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode: raise RuntimeError('No se pudo ejecutar el OCR local.')
    out=[]
    for row in csv.DictReader(StringIO(result.stdout.decode('utf-8',errors='replace')),delimiter='\t'):
        try:
            text=row['text'].strip().replace('-','')
            if row['level']=='5' and re.fullmatch(r'R?[1-9][0-9]{0,2}',text): out.append((text,float(row['conf']),int(row['left']),int(row['top']),int(row['width']),int(row['height'])))
        except (TypeError,ValueError,KeyError): continue
    return out

def label_crop(im,m):
    x,y,x2,y2=m.crop
    q=np.float32(m.quad or [(x,y),(x2,y),(x2,y2),(x,y2)])
    left=(q[0]+q[3])/2; right=(q[1]+q[2])/2
    v=right-left; width=float(np.linalg.norm(v)); v/=max(1,width)
    h=max(5,float((np.linalg.norm(q[3]-q[0])+np.linalg.norm(q[2]-q[1]))/2))
    down=np.array([-v[1],v[0]],np.float32)
    a=left-v*min(width*.90,h*4.0); b=left+v*min(2,h*.08); half=h*.43
    src=np.float32([a-down*half,b-down*half,b+down*half,a+down*half])
    w=max(10,round(np.linalg.norm(b-a)*3)); hh=max(16,round(half*6))
    crop=cv.warpPerspective(im,cv.getPerspectiveTransform(src,np.float32([[0,0],[w-1,0],[w-1,hh-1],[0,hh-1]])),(w,hh),borderValue=(255,255,255))
    g=np.max(crop,axis=2).astype(np.uint8)
    # Suppress framing strokes and grid edges. Printed glyphs are disconnected
    # from the surrounding oval / table in a usable image.
    threshold,_=cv.threshold(g,0,255,cv.THRESH_BINARY+cv.THRESH_OTSU)
    mask=(g<min(200,threshold+12)).astype(np.uint8)
    _,cc,stats,_=cv.connectedComponentsWithStats(mask,8)
    h,w=g.shape; parts=[]
    for idx,(x,y,ww,hh,area) in enumerate(stats[1:],1):
        if x<=0 or y<=0 or x+ww>=w or y+hh>=h: continue
        if not .24*h<=hh<=.86*h or not .07*h<=ww<=1.5*h or area<.018*h*h: continue
        parts.append((x,y,ww,hh,idx))
    if not parts: return np.full((35,60),255,np.uint8)
    groups=[]
    for part in sorted(parts):
        if not groups or part[0]-max(v[0]+v[2] for v in groups[-1])>.4*h: groups.append([])
        groups[-1].append(part)
    # Numeric labels are the rightmost plausible cluster before the first option.
    group=groups[-1]; x=min(v[0] for v in group); y=min(v[1] for v in group); x2=max(v[0]+v[2] for v in group); y2=max(v[1]+v[3] for v in group)
    if x2-x>2.6*h or len(group)>4: return np.full((35,60),255,np.uint8)
    out=np.full(g.shape,255,np.uint8)
    for *_,idx in group: out[cc==idx]=0
    return cv.copyMakeBorder(out[y:y2,x:x2],5,5,5,5,cv.BORDER_CONSTANT,value=255)

def make_sheet(im,marks):
    w,h,cols=250,80,4
    sheet=np.full((max(1,(len(marks)+cols-1)//cols)*h,cols*w),255,np.uint8)
    for i,m in enumerate(marks):
        g=label_crop(im,m); scale=min((w-30)/g.shape[1],(h-22)/g.shape[0]); g=cv.resize(g,None,fx=scale,fy=scale,interpolation=cv.INTER_CUBIC)
        yy=i//cols*h+(h-g.shape[0])//2; xx=(i%cols+1)*w-15-g.shape[1]
        sheet[yy:yy+g.shape[0],xx:xx+g.shape[1]]=g
    return sheet,w,h,cols

def read_labels(im,marks):
    if not marks: return {}
    sheet,w,h,cols=make_sheet(im,marks); found={}
    for label,conf,x,y,ww,hh in recognize(sheet,6):
        i=int((y+hh/2)//h)*cols+int((x+ww/2)//w)
        if i>=len(marks) or conf<65 or x//w!=(x+ww-1)//w or y//h!=(y+hh-1)//h: continue
        if i not in found or conf>found[i][1]: found[i]=(label,conf)
    return found

def reconcile(marks,blocks,labels):
    """Require several independent consistent anchors; never guess from one character."""
    result=[]; offset=0; verified=0; changed=0; conflicts=[]
    for block in blocks:
        anchors=[]
        for j,m in enumerate(block):
            if offset+j not in labels: continue
            label,conf=labels[offset+j]
            if conf>=80: anchors.append((label.startswith('R'),int(label.lstrip('R'))-j,j))
        expected=(block[0].number.startswith('R'),int(block[0].number.lstrip('R')))
        votes=Counter((r,start) for r,start,j in anchors if start>0)
        if votes:
            best,n=votes.most_common(1)[0]; support=[j for r,start,j in anchors if (r,start)==best]
            strong=n>=max(3,ceil(len(block)*.20)) and n>=.8*len(anchors) and max(support)-min(support)>=min(5,len(block)-1)
            # A missing OCR prefix is not evidence that a reserve is ordinary.
            if expected[0] and not best[0]: strong=False
            if strong and best!=expected and n<max(3,ceil(len(block)*.33)): strong=False
            if strong and best!=expected:
                if best[1]+len(block)-1>999: raise ValueError('Numeración OCR fuera de rango.')
                block=[replace(m,number=('R' if best[0] else '')+str(best[1]+j)) for j,m in enumerate(block)]; changed+=len(block)
            if strong:
                verified+=len(block)
                block=[replace(m,number_check=('OCR' if labels.get(offset+j,('',0))[0]==m.number and labels.get(offset+j,('',0))[1]>=80 else 'sequence')) for j,m in enumerate(block)]
            elif len(votes)>=2 and votes.most_common(2)[1][1]>=3 and n>=3 and not expected[0]: conflicts.append(block[0].number)
        block=[replace(m,number_check=m.number_check or ('OCR' if labels.get(offset+j,('',0))[0]==m.number and labels.get(offset+j,('',0))[1]>=80 else 'geometry')) for j,m in enumerate(block)]
        result.extend(block); offset+=len(block)
    nums=[m.number for m in result]
    if len(set(nums))!=len(nums): raise ValueError('La numeración impresa se solapa con otra columna. Revisa la hoja.')
    return result,verified,changed,conflicts

def verify(im,marks):
    from .omr import reading_blocks
    return reconcile(marks,reading_blocks(marks),read_labels(im,marks))
