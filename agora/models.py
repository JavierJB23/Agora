"""Printable blank answer sheets; independent of solution keys and saved attempts."""
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from io import BytesIO
from datetime import datetime
import json, re, sqlite3, uuid, hashlib, math
from contextlib import closing
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, black, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
import qrcode

@dataclass(frozen=True)
class Model:
    name: str='Mi modelo'
    questions: int=120
    reserves: int=9
    options: int=3
    columns: int=4
    shape: str='circle'
    color: str='#A55379'
    orientation: str='portrait'
    size: int=5
    margin: int=12
    stripe: bool=True
    header: bool=True
    logo: bool=True
    notes: bool=False
    separate: bool=False
    title: str='HOJA DE RESPUESTAS'
    def __post_init__(self):
        for v,lo,hi in [(self.questions,1,500),(self.reserves,0,100),(self.options,2,5),(self.columns,1,4),(self.size,4,8),(self.margin,10,22)]:
            if type(v) is not int or not lo<=v<=hi: raise ValueError('Parámetros fuera de rango.')
        if self.shape not in ('circle','square','oval') or self.orientation not in ('portrait','landscape') or not re.fullmatch(r'#[0-9a-fA-F]{6}',self.color): raise ValueError('Diseño no válido.')
        if any(not isinstance(v,str) or not v.strip() or len(v)>100 or any(ord(c)<32 for c in v) for v in (self.name,self.title)): raise ValueError('Introduce un nombre y título de hasta 100 caracteres.')
    @property
    def letters(self): return 'ABCDE'[:self.options]

PRESETS=(Model('Ágora Clásico',separate=True),Model('Ágora Compacto',50,5,4,2,'square','#333333'),Model('Ágora Estándar',100,5,4,3,'oval','#315C83'),Model('Ágora Repaso',20,0,3,1,'circle','#333333'))

def layout(m):
    """Exact printable geometry in PDF points; each page includes independent IDs."""
    w,h=A4 if m.orientation=='portrait' else landscape(A4)
    margin=m.margin*mm; cell=m.size*mm; gap=4*mm; number=10*mm; step=cell+1.8*mm
    top=h-margin-(34*mm if m.header else 16*mm); bottom=margin+(45*mm if m.notes else 21*mm)
    # Never squeeze cells: reduce columns if chosen width cannot fit.
    cols=m.columns
    while cols>1 and (w-2*margin-(cols-1)*gap)/cols<number+m.options*(cell+1.5*mm)+3*mm: cols-=1
    cw=(w-2*margin-(cols-1)*gap)/cols
    rows=int((top-bottom-8*mm)//step)
    if rows<1 or cw<number+m.options*(cell+1.5*mm)+3*mm: raise ValueError('No cabe el diseño con estos márgenes y casillas.')
    ordinary=[str(i) for i in range(1,m.questions+1)]; reserves=[f'R{i}' for i in range(1,m.reserves+1)]
    groups=[ordinary,reserves] if m.separate else [ordinary+reserves]
    pages=[]
    for g in groups:
        for start in range(0,len(g),cols*rows):
            part=g[start:start+cols*rows]; rcount=min(rows,math.ceil(len(part)/cols)); blocks=[]
            for c in range(cols):
                ids=part[c*rcount:(c+1)*rcount]
                if not ids: continue
                x=margin+c*(cw+gap); space=(cw-number-2*mm)/m.options
                entries=[{'number':n,'y':top-8*mm-(r+.5)*step,'centers':[x+number+(j+.5)*space for j in range(m.options)]} for r,n in enumerate(ids)]
                blocks.append({'x':x,'width':cw,'rows':entries})
            pages.append({'width':w,'height':h,'top':top,'bottom':bottom,'margin':margin,'cell':cell,'step':step,'columns':cols,'blocks':blocks})
    return pages

def identifier(m):
    d=asdict(m); d.pop('name'); return hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()[:16]

def text_fit(c,text,x,y,limit,font='Helvetica-Bold',size=12):
    while size>6 and stringWidth(text,font,size)>limit: size-=.5
    while text and stringWidth(text,font,size)>limit: text=text[:-1]
    c.setFont(font,size); c.drawString(x,y,text)

def pdf_bytes(m):
    pages=layout(m); stream=BytesIO(); c=canvas.Canvas(stream,pagesize=(pages[0]['width'],pages[0]['height']),pageCompression=1)
    c.setTitle(m.name); c.setAuthor('Ágora'); color=HexColor(m.color); tint=Color(*(1-(1-v)*.09 for v in (color.red,color.green,color.blue)))
    # Ink must remain legible even when the selected accent is very pale.
    ink=color if .2126*color.red+.7152*color.green+.0722*color.blue<.68 else HexColor('#444444')
    for page_index,p in enumerate(pages,1):
        w,h,ma,top,cell,step=(p[k] for k in ('width','height','margin','top','cell','step')); c.setPageSize((w,h)); c.setFillColor(black)
        for x in (ma-5*mm,w-ma+1*mm):
            for y in (ma-5*mm,h-ma+1*mm): c.rect(x,y,4*mm,4*mm,stroke=0,fill=1)
        c.setFillColor(ink); tx=ma
        if m.logo:
            c.setStrokeColor(ink); c.setLineWidth(1); x=ma; y=h-ma-9*mm
            path=c.beginPath(); path.moveTo(x,y+7*mm); path.lineTo(x+7*mm,y+11*mm); path.lineTo(x+14*mm,y+7*mm); path.close(); c.drawPath(path)
            for i in (2,5,9,12): c.line(x+i*mm,y+1*mm,x+i*mm,y+6*mm)
            c.line(x,y,x+14*mm,y); c.setFont('Times-Bold',19); c.drawString(x+17*mm,y+1*mm,'ÁGORA'); tx=ma+49*mm
        title=m.title+(' · RESERVAS' if all(r['number'].startswith('R') for b in p['blocks'] for r in b['rows']) else '')
        text_fit(c,title,tx,h-ma-7*mm,w-ma-tx, size=14)
        if m.header:
            y=h-ma-30*mm; c.setStrokeColor(ink); c.setLineWidth(.5); c.rect(ma,y,w-2*ma,15*mm)
            fields=[('EXAMEN / TEMA',.39),('FECHA',.16),('ACIERTOS',.11),('ERRORES',.11),('BLANCOS',.11),('NOTA',.12)]; x=ma
            for i,(t,ratio) in enumerate(fields):
                if i: c.line(x,y,x,y+15*mm)
                c.setFillColor(ink); c.setFont('Helvetica',6.5); c.drawString(x+2*mm,y+11*mm,t); x+=(w-2*ma)*ratio
        for b in p['blocks']:
            x,cw=b['x'],b['width']; c.setFillColor(ink); c.roundRect(x,top-7*mm,cw,7*mm,2,stroke=0,fill=1); c.setFillColor(white); c.setFont('Helvetica-Bold',8); c.drawString(x+2*mm,top-4.7*mm,'Nº')
            for letter,cx in zip(m.letters,b['rows'][0]['centers']): c.drawCentredString(cx,top-4.7*mm,letter)
            for i,r in enumerate(b['rows']):
                y=r['y'];
                if m.stripe and i%2==0: c.setFillColor(tint); c.rect(x,y-step/2,cw,step,stroke=0,fill=1)
                c.setFillColor(ink); c.setFont('Helvetica',8.5); c.drawString(x+2*mm,y-3,r['number']); c.setStrokeColor(ink); c.setLineWidth(.75)
                for cx in r['centers']:
                    if m.shape=='circle': c.circle(cx,y,cell/2,stroke=1,fill=0)
                    elif m.shape=='square': c.rect(cx-cell/2,y-cell/2,cell,cell,stroke=1,fill=0)
                    else: c.ellipse(cx-cell/2,y-cell*.36,cx+cell/2,y+cell*.36,stroke=1,fill=0)
        if m.notes:
            c.setFillColor(ink); c.setFont('Helvetica-Bold',8); c.drawString(ma,ma+39*mm,'OBSERVACIONES'); c.setStrokeColor(ink); c.setLineWidth(.5); c.rect(ma,ma+19*mm,w-2*ma,18*mm)
            for i in (1,2): c.line(ma,ma+(19+6*i)*mm,w-ma,ma+(13+6*i)*mm)
        # Compact machine-readable ID; future recognition uses exact geometry.
        qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=1,border=4); qr.add_data(f'AGORA1:{identifier(m)}:{page_index}:{len(pages)}'); qr.make(fit=True); matrix=qr.get_matrix(); scale=19*mm/len(matrix); qx=w-ma-19*mm; qy=ma-2*mm
        # QR sits in footer; reserve its full height in layout when necessary.
        c.setFillColor(white); c.rect(qx,qy,19*mm,19*mm,stroke=0,fill=1); c.setFillColor(black)
        for i,row in enumerate(matrix):
            for j,v in enumerate(row):
                if v: c.rect(qx+j*scale,qy+(len(matrix)-i-1)*scale,scale,scale,stroke=0,fill=1)
        c.setFillColor(ink); text_fit(c,m.name,ma,ma+2*mm,w-2*ma-24*mm,'Helvetica',8); c.setFont('Helvetica',7); c.drawString(ma,ma-2*mm,f'{page_index}/{len(pages)}  |  {identifier(m)}'); c.showPage()
    c.save(); return stream.getvalue()

class ModelLibrary:
    """Separate database so a rollback to 06B leaves both libraries intact."""
    def __init__(self,directory):
        self.path=Path(directory)/'models.sqlite3'
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS models (id TEXT PRIMARY KEY, created TEXT NOT NULL, payload TEXT NOT NULL)')
    def entries(self):
        with closing(sqlite3.connect(self.path)) as db:
            return [(i,Model(**json.loads(p)),d) for i,d,p in db.execute('SELECT id,created,payload FROM models ORDER BY created DESC,id')]
    def save(self,m,mid=None):
        mid=mid or uuid.uuid4().hex
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT INTO models VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(mid,datetime.now().isoformat(timespec='seconds'),json.dumps(asdict(m),ensure_ascii=False)))
        return mid
    def delete(self,mid):
        with closing(sqlite3.connect(self.path)) as db, db: db.execute('DELETE FROM models WHERE id=?',(mid,))
