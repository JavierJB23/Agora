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

def ocr_text(image):
    import os, subprocess, cv2 as cv
    from .number_ocr import engine
    exe,extra=engine()
    if not exe: raise ValueError('Motor OCR local no disponible.')
    gray=cv.cvtColor(image,cv.COLOR_RGB2GRAY)
    if max(gray.shape)<1600: gray=cv.resize(gray,None,fx=2,fy=2,interpolation=cv.INTER_CUBIC)
    ok,png=cv.imencode('.png',gray)
    if not ok: raise ValueError('No se pudo preparar la imagen.')
    cmd=[exe,'stdin','stdout',*extra,'-l','eng','--psm','6','-c','preserve_interword_spaces=1']
    r=subprocess.run(cmd,input=png.tobytes(),capture_output=True,timeout=45,env=dict(os.environ,OMP_THREAD_LIMIT='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if r.returncode: raise ValueError('No se pudo leer el texto de la imagen.')
    # Correct an OCR-only glyph ambiguity in the numeric part of R1, never a response letter.
    text=r.stdout.decode('utf-8',errors='replace')
    return re.sub(r'(?<![\w])R[ \t]*[Il](?=[ \t]*[A-EX](?:$|[\s,;|]))','R1',text)


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
