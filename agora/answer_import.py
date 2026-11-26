"""Strict text solution-key extraction; no guessing or OCR."""
from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
import re, unicodedata, zipfile
from xml.etree import ElementTree as ET

MAX_BYTES=100*1024*1024
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
    if not ordinary: raise ValueError('No se han encontrado soluciones de preguntas ordinarias. Si el PDF es una imagen escaneada, todavía no es compatible.')
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

def extract_key(data, filename):
    if not data or len(data)>MAX_BYTES: raise ValueError('El documento está vacío o supera 100 MB.')
    ext=Path(filename).suffix.lower()
    if ext=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(data))
        if reader.is_encrypted: raise ValueError('El PDF está protegido. Guarda una copia sin contraseña.')
        if len(reader.pages)>300: raise ValueError('El PDF supera 300 páginas. Importa solo el solucionario.')
        pages=[p.extract_text(extraction_mode='layout') or '' for p in reader.pages]
    elif ext=='.docx': pages=read_docx(data)
    else: raise ValueError('Usa un documento PDF o Word .docx. El formato .doc antiguo no está admitido.')
    return parse_pages(pages)
