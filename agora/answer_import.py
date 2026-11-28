"""Strict solution-key extraction, including locally OCR-read images."""
from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
import re, unicodedata, zipfile
from xml.etree import ElementTree as ET

MAX_BYTES=100*1024*1024
IMAGE_EXTENSIONS=('.jpg','.jpeg','.png')
KEY_EXTENSIONS=('.pdf','.docx',*IMAGE_EXTENSIONS)
PAIR=re.compile(r'(?<![\w])(?:(R(?:ESERVA)?)[ \t]*-?[ \t]*)?(\d{1,3})[ \t]*[.):\-]?[ \t]*(ANULAD[AO]|[A-EX])(?=$|[\s,;|])',re.I)
TITLE=re.compile(r'^\s*(?:respuestas\s+correctas|soluciones(?:\s+correctas)?|solucionario|plantilla\s+de\s+(?:respuestas|soluciones)(?:\s+correctas)?)\b',re.I)
RES=re.compile(r'(?:preguntas\s+de\s+reserva|preguntas\s+reserva|reservas?|respuestas\s+de\s+reserva)\s*:',re.I)

@dataclass(frozen=True)
class ImportedKey:
    ordinary: tuple
    reserves: tuple
    @property
    def key(self): return list(self.ordinary+self.reserves)
    @property
    def options(self): return max(2,max((ord(v)-64 for v in self.key if v!='X'),default=2))

def parse_pages(pages):
    pages=[unicodedata.normalize('NFKC',p).replace('\u200b','').replace('\ufeff','').replace('\xa0',' ') for p in pages]
    lines=[line for page in pages for line in page.splitlines()]
    headings=[i for i,line in enumerate(lines) if TITLE.match(line)]
    # A questionnaire may precede its explicit answer section. Use the final heading.
    if headings: lines=lines[headings[-1]+1:]
    ordinary={}; reserves={}; reserve_x=None; global_reserve=False
    for raw in lines:
        if not raw.strip(): continue
        if TITLE.match(raw): continue
        heading=RES.search(raw)
        if heading:
            before=raw[:heading.start()]; after=raw[heading.end():]
            # A heading in a later column applies only to that column.
            if before.strip(): reserve_x=max(0,heading.start()-5)
            elif heading.start()>20: reserve_x=max(0,heading.start()-5)
            else: global_reserve=True; reserve_x=None
            raw=before+' '*(heading.end()-heading.start())+after
        matches=list(PAIR.finditer(raw))
        residue=PAIR.sub('',raw).strip(' \t,;|')
        if residue:
            # Reject arbitrary prose rather than interpreting fragments of questions.
            raise ValueError('Texto no reconocido en el solucionario: '+residue[:100]+'. Usa un listado de número y letra o un apartado «Respuestas correctas».')
        for m in matches:
            n=int(m[2]); v=m[3].upper(); v='X' if v.startswith('ANULAD') else v
            target=reserves if m[1] or global_reserve or (reserve_x is not None and m.start()>=reserve_x) else ordinary
            if n<1 or n>(100 if target is reserves else 500): raise ValueError('Numeración fuera de rango: '+str(n))
            if n in target: raise ValueError(f'Numeración duplicada: {"R" if target is reserves else ""}{n}. Revisa el documento.')
            target[n]=v
    if not ordinary: raise ValueError('No se han encontrado soluciones de preguntas ordinarias. Comprueba que el listado de números y letras sea legible.')
    for d,prefix in [(ordinary,''),(reserves,'R')]:
        missing=[prefix+str(n) for n in range(1,max(d,default=0)+1) if n not in d]
        if missing: raise ValueError('Faltan soluciones: '+', '.join(missing[:25])+'. No se ha importado ninguna respuesta.')
    return ImportedKey(tuple(ordinary[n] for n in sorted(ordinary)),tuple(reserves[n] for n in sorted(reserves)))

def read_docx(data):
    ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with zipfile.ZipFile(BytesIO(data)) as z:
        info=z.getinfo('word/document.xml')
        if info.file_size>MAX_BYTES: raise ValueError('Documento Word demasiado grande.')
        root=ET.fromstring(z.read(info))
    def paragraph(p):
        return ''.join(e.text or '' if e.tag==ns+'t' else '\t' if e.tag==ns+'tab' else '\n' if e.tag==ns+'br' else '' for e in p.iter())
    lines=[]
    body=root.find(ns+'body')
    for el in body:
        if el.tag==ns+'p': lines.append(paragraph(el))
        elif el.tag==ns+'tbl':
            for row in el.findall(ns+'tr'):
                lines.append('    '.join(' '.join(paragraph(p) for p in c.iter(ns+'p')) for c in row.findall(ns+'tc')))
    return ['\n'.join(lines)]

def _ocr_image(gray, psm=6, whitelist=None):
    import os, subprocess, cv2 as cv
    from .number_ocr import engine
    exe,extra=engine()
    if not exe: raise ValueError('Motor OCR local no disponible.')
    ok,png=cv.imencode('.png',gray)
    if not ok: raise ValueError('No se pudo preparar la imagen.')
    cmd=[exe,'stdin','stdout',*extra,'-l','eng','--psm',str(psm),'-c','preserve_interword_spaces=1']
    if whitelist: cmd+=['-c','tessedit_char_whitelist='+whitelist]
    r=subprocess.run(cmd,input=png.tobytes(),capture_output=True,timeout=45,env=dict(os.environ,OMP_THREAD_LIMIT='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if r.returncode: raise ValueError('No se pudo leer el texto de la imagen.')
    return r.stdout.decode('utf-8',errors='replace')


def _column_ocr(gray, initial):
    """Fallback for printed multi-column keys. Check geometry and actual digits;
    never fill missing answers from a presumed sequence or the exam configuration."""
    import cv2 as cv, numpy as np
    _,ink=cv.threshold(gray,0,255,cv.THRESH_BINARY_INV+cv.THRESH_OTSU)
    _,_,stats,_=cv.connectedComponentsWithStats(ink)
    heights=[int(h) for x,y,w,h,area in stats[1:] if 5<h<60 and 3<w<50 and area>12]
    if len(heights)<20: raise ValueError('No se distinguen las columnas del solucionario.')
    h=max(8,int(np.median(heights))); xs=np.flatnonzero((ink>0).sum(0)>3*h)
    bands=[b for b in np.split(xs,np.where(np.diff(xs)>5*h)[0]+1) if len(b)>h]
    if not 2<=len(bands)<=8: raise ValueError('No se distinguen las columnas del solucionario.')
    # A recognized global title is allowed above the answer columns, not arbitrary prose.
    title=next((v for v in initial.splitlines() if v.strip()),'')
    has_title=bool(TITLE.match(title))
    def runs(mask):
        ys=np.flatnonzero((mask>0).sum(1)>2)
        return [(int(r[0]),int(r[-1])+1) for r in np.split(ys,np.where(np.diff(ys)>max(2,h//4))[0]+1) if len(r) and r[-1]-r[0]>=h*.48]
    def prep(a):
        a=cv.resize(a,None,fx=2,fy=2,interpolation=cv.INTER_CUBIC)
        _,a=cv.threshold(a,0,255,cv.THRESH_BINARY+cv.THRESH_OTSU)
        return cv.copyMakeBorder(a,15,15,15,15,cv.BORDER_CONSTANT,value=255)
    bounds=[(max(0,int(b[0])-3*h),min(gray.shape[1],int(b[-1])+4*h)) for b in bands]
    layouts=[runs(ink[:,l:r]) for l,r in bounds]
    # All initial text above a shared first data row must be a single title line.
    starts=[]
    for rr in layouts:
        if len(rr)<4: raise ValueError('Columna incompleta.')
        if has_title and rr[1][0]-rr[0][1]>3*h: starts.append(rr[1][0])
    cutoff=min(starts)-h if starts else 0
    if cutoff and any(sum(y<cutoff for y,_ in rr)>1 for rr in layouts): raise ValueError('Texto adicional antes de las columnas.')
    ordinary=[]; reserve=[]; reserve_seen=False
    for (l,r),rr in zip(bounds,layouts):
        rr=[(y,z) for y,z in rr if y>=cutoff]
        if not rr: raise ValueError('Columna vacía.')
        segments=[]; current=[]; is_reserve=False
        for y,z in rr:
            row=ink[y:z,l:r]
            # A wide text line may be an explicit reserve heading. Verify its text.
            if np.count_nonzero(row.any(axis=0))>5*h:
                heading=_ocr_image(prep(gray[max(0,y-2):z+2,max(0,l-2*h):min(gray.shape[1],r+5*h)]),7).strip()
                if not RES.fullmatch(heading): raise ValueError('Texto no reconocido entre las respuestas: '+heading[:80])
                if current: segments.append((is_reserve,current)); current=[]
                is_reserve=True; reserve_seen=True; continue
            current.append((y,z))
        if current: segments.append((is_reserve,current))
        for is_reserve,rows in segments:
            y0,y1=rows[0][0],rows[-1][1]
            text=_ocr_image(prep(gray[max(0,y0-h//2):y1+h//2,l:r]),6,'0123456789.ABCDEXabcdeRr ')
            lines=[v.strip() for v in text.splitlines() if v.strip()]
            if len(lines)!=len(rows): raise ValueError('No coincide el número de filas de la columna.')
            previous=None
            for line,(y,z) in zip(lines,rows):
                m=PAIR.fullmatch(line)
                if not m:
                    # Retry only a damaged answer glyph, with its own alphabet.
                    n=re.fullmatch(r'(R?)[ ]*(\d{1,3})[.]\s*(.*)',line,re.I)
                    if not n: raise ValueError('Número o letra dudosos: '+line)
                    row=ink[max(0,y-2):z+2,l:r]
                    xx=np.flatnonzero(row.any(axis=0)); pieces=np.split(xx,np.where(np.diff(xx)>max(2,h//3))[0]+1)
                    if len(pieces)<2: raise ValueError('No se distingue la letra: '+line)
                    a,b=int(pieces[-1][0]),int(pieces[-1][-1])+1
                    # The column OCR may emit only '3.'. A separate, letter-sized
                    # ink component must actually exist to retry; never turn a
                    # period or an empty answer into a guessed letter.
                    glyph_ink=row[:,a:b]
                    yy=np.flatnonzero(glyph_ink.any(axis=1))
                    if not len(yy) or yy[-1]-yy[0]+1<.35*h or b-a<.22*h:
                        raise ValueError('No se distingue la letra: '+line)
                    for scale in (2,4,5):
                        glyph=cv.resize(gray[max(0,y-3):z+3,max(0,l+a-2):l+b+2],None,fx=scale,fy=scale,interpolation=cv.INTER_CUBIC)
                        glyph=cv.copyMakeBorder(glyph,12,12,12,12,cv.BORDER_CONSTANT,value=255)
                        v=_ocr_image(glyph,10,'ABCDEXabcde').strip().upper()
                        if len(v)==1 and v in 'ABCDEX': break
                    if len(v)!=1 or v not in 'ABCDEX':
                        for mode in (7,13,8):
                            v=_ocr_image(glyph,mode,'ABCDEXabcde').strip().upper()
                            if len(v)==1 and v in 'ABCDEX': break
                    if len(v)!=1 or v not in 'ABCDEX': raise ValueError('Letra dudosa: '+line)
                    line=n[1]+n[2]+v; m=PAIR.fullmatch(line)
                number=int(m[2])
                if previous is not None and number!=previous+1:
                    row=ink[max(0,y-2):z+2,l:r]
                    xx=np.flatnonzero(row.any(axis=0)); pieces=np.split(xx,np.where(np.diff(xx)>max(2,h//3))[0]+1)
                    if len(pieces)<2: raise ValueError('Número dudoso: '+line)
                    a,b=int(xx[0]),int(pieces[-2][-1])+1
                    digits=prep(gray[max(0,y-3):z+3,max(0,l+a-2):l+b+2])
                    read=_ocr_image(digits,7,'0123456789.').strip().rstrip('.')
                    if not read.isdigit() or int(read)!=previous+1: raise ValueError('Numeración dudosa: '+line)
                    number=int(read)
                previous=number
                target=reserve if is_reserve or m[1] else ordinary
                target.append(('R' if target is reserve else '')+str(number)+m[3].upper())
    if reserve_seen and not reserve: raise ValueError('No se han leído las reservas.')
    result='\n'.join(ordinary+reserve)
    parse_pages([result])  # verify duplicates and gaps before proposing any solution
    return result


def ocr_text(image):
    import cv2 as cv
    gray=cv.cvtColor(image,cv.COLOR_RGB2GRAY)
    if max(gray.shape)<1600: gray=cv.resize(gray,None,fx=2,fy=2,interpolation=cv.INTER_CUBIC)
    text=_ocr_image(gray)
    text=re.sub(r'(?<![\w])R[ \t]*[Il](?=[ \t]*[A-EX](?:$|[\s,;|]))','R1',text)
    try: parse_pages([text]); return text
    except ValueError:
        # A page containing only explicitly labeled reserves can be parsed with other pages.
        if re.search(r'(?im)^\s*(?:R\s*[- ]?\d|preguntas de reserva)',text) and not TITLE.search(text):
            return text
        try: return _column_ocr(gray,text)
        except ValueError: return text


def extract_key(data, filename):
    if not data or len(data)>MAX_BYTES: raise ValueError('El documento está vacío o supera 100 MB.')
    ext=Path(filename).suffix.lower()
    if ext=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(data))
        if reader.is_encrypted: raise ValueError('El PDF está protegido. Guarda una copia sin contraseña.')
        if len(reader.pages)>300: raise ValueError('El PDF supera 300 páginas. Importa solo el solucionario.')
        pages=[p.extract_text(extraction_mode='layout') or '' for p in reader.pages]
        if any(not p.strip() for p in pages):
            if len(pages)>20: raise ValueError('Importa un máximo de 20 páginas escaneadas.')
            from .omr import decode
            images=decode(filename,data); pages=[p if p.strip() else ocr_text(im) for p,im in zip(pages,images)]
    elif ext=='.docx':
        pages=read_docx(data)
        if not any(p.strip() for p in pages):
            from .omr import decode
            pages=[ocr_text(im) for name,blob in docx_images(data) for im in decode(name,blob)]
    elif ext in IMAGE_EXTENSIONS:
        from .omr import decode
        pages=[ocr_text(im) for im in decode(filename,data)]
    else: raise ValueError('Usa PDF, Word .docx o una imagen JPG/PNG.')
    return parse_pages(pages)


def docx_images(data):
    import posixpath
    from zipfile import ZipFile
    rns='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    ans=[]
    with ZipFile(BytesIO(data)) as z:
        for name in ('word/document.xml','word/_rels/document.xml.rels'):
            if name not in z.namelist() or z.getinfo(name).file_size>MAX_BYTES: return []
        root=ET.fromstring(z.read('word/document.xml')); rels=ET.fromstring(z.read('word/_rels/document.xml.rels'))
        targets={e.get('Id'):e.get('Target','') for e in rels if e.get('Type','').endswith('/image') and e.get('TargetMode')!='External'}
        total=0
        for e in root.iter():
            target=targets.get(e.get(rns+'embed'))
            if not target: continue
            name=posixpath.normpath(posixpath.join('word',target))
            if not name.startswith('word/media/') or name not in z.namelist() or Path(name).suffix.lower() not in IMAGE_EXTENSIONS: continue
            total+=z.getinfo(name).file_size
            if total>MAX_BYTES or len(ans)>=20: raise ValueError('Word: máximo 20 imágenes y 100 MB.')
            ans.append((name,z.read(name)))
    return ans


RESPONSE_PAIR=re.compile(r'(?<![\w])(?:(R(?:ESERVA)?)[ \t]*-?[ \t]*)?(\d{1,3})[ \t]*[.):]?[ \t]*(EN[ \t]+BLANCO|BLANCO|ANULAD[AO]|[A-EX]|[-—])(?=$|[\s,;|])',re.I)

def parse_response_list(pages, config):
    result={}; reserve_section=False
    for page in pages:
        for raw in unicodedata.normalize('NFKC',page).splitlines():
            line=raw.strip()
            if not line or re.fullmatch(r'(?:mis )?respuestas(?: del (?:examen|simulacro))?:?',line,re.I): continue
            if re.fullmatch(r'(?:preguntas (?:de )?reserva|reservas|respuestas de reserva):?',line,re.I): reserve_section=True; continue
            if RESPONSE_PAIR.sub('',line).strip(' \t,;|'): raise ValueError('El documento de respuestas debe contener números y letras, o indicar En blanco/Anulada.')
            for m in RESPONSE_PAIR.finditer(line):
                n=int(m[2]); reserve=bool(m[1]) or reserve_section
                if not reserve and config.questions<n<=config.size: n-=config.questions; reserve=True
                if not 1<=n<=(config.reserves if reserve else config.questions): raise ValueError('Pregunta fuera del examen: '+m[0])
                i=config.questions+n-1 if reserve else n-1; v=m[3].upper()
                v='-' if 'BLANCO' in v or v in ('-','—') else 'X' if v.startswith('ANULAD') else v
                if v not in (*config.letters,'-','X') or i in result: raise ValueError('Respuesta repetida o no válida: '+m[0])
                result[i]=v
    if not result: raise ValueError('No se han encontrado respuestas numeradas.')
    return result
