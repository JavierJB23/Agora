"""One short-lived LAN session. Each batch is bound to the visible import destination."""
import json, queue, secrets, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote
from .transfer import PAGE
from .answer_import import MAX_BYTES

MOBILE_JS = r'''const f=document.querySelector('#file'),b=document.querySelector('#send'),s=document.querySelector('#status'),p=document.querySelector('#progress'),dest=document.querySelector('#destination'),clock=document.querySelector('#clock');
let target=null,selectedFor=null,sending=false,expires=0,limit=20,sequence=0;
f.addEventListener('change',()=>{selectedFor=target;});
function render(){let left=Math.max(0,Math.ceil((expires-Date.now())/1000));clock.textContent=expires?'Caduca en '+Math.floor(left/60)+':'+String(left%60).padStart(2,'0')+' · 15 min de conexión':'Conectando…';b.disabled=sending||!target||!left;f.disabled=sending||!target||!left;}
async function status(){const seq=++sequence;try{const r=await fetch(location.pathname+'status',{cache:'no-store'});if(!r.ok)throw Error();const v=await r.json();if(seq!==sequence)return;expires=Date.now()+v.remaining*1000;target=v.token;limit=v.max_files;dest.textContent=v.label;f.accept=v.extensions.join(',');f.multiple=limit>1;render();}catch(e){if(seq!==sequence)return;target=null;dest.textContent='Conexión no disponible. Abre Ágora o escanea un nuevo QR.';render();}}
b.onclick=()=>{const files=Array.from(f.files),token=target;if(!token||sending)return;if(files.length&&selectedFor!==token){f.value='';document.querySelector('#filename').textContent='Ningún archivo seleccionado';s.textContent='El destino ha cambiado. Selecciona de nuevo los archivos.';return}if(!files.length||files.length>limit){s.textContent='Selecciona entre 1 y '+limit+' archivo(s).';return}if(files.reduce((n,v)=>n+v.size,0)>104857600||files.some(v=>!v.size)){s.textContent='Máximo 100 MB por envío.';return}sending=true;render();p.value=0;s.textContent='Enviando…';const x=new XMLHttpRequest();x.open('POST',location.pathname+'batch');x.setRequestHeader('X-Destination',token);x.setRequestHeader('X-Files',encodeURIComponent(JSON.stringify(files.map(v=>[v.name,v.size]))));x.upload.onprogress=e=>{if(e.lengthComputable)p.value=e.loaded/e.total*100};x.onload=()=>{sending=false;s.textContent=x.status===200?'Archivos recibidos. Consulta Ágora para ver el resultado o confirmar una sustitución. Puedes enviar más.':(x.responseText||'No se pudo enviar.');if(x.status===200){f.value='';document.querySelector('#filename').textContent='Ningún archivo seleccionado';p.value=100}status();render()};x.onerror=()=>{sending=false;s.textContent='Conexión interrumpida. Comprueba el Wi-Fi.';status();render()};x.send(new Blob(files));};
status();setInterval(status,1000);setInterval(render,250);'''

def mobile_page():
    return (PAGE.split('<script>')[0].replace('Enviar documento al ordenador','<span id="clock">Conectando…</span><br><strong id="destination">Buscando destino…</strong>').replace('type="file"','type="file" multiple').replace('Enviar documento','Enviar archivos')+'<script>'+MOBILE_JS+'</script></html>')

class MobileSession:
    def __init__(self,host='0.0.0.0',duration=900):
        self.token=secrets.token_urlsafe(24); self.deadline=time.monotonic()+duration
        self.lock=threading.Lock(); self.closed=threading.Event(); self.items=queue.Queue(maxsize=1)
        self.route=None; self.receiving=False; owner=self
        class Handler(BaseHTTPRequestHandler):
            def setup(self): super().setup(); self.connection.settimeout(30)
            def log_message(self,*args): pass
            def reply(self,code,body,kind='text/plain; charset=utf-8'):
                data=body.encode(); self.send_response(code); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer'); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                if self.path==f'/{owner.token}/': self.reply(200,mobile_page(),'text/html; charset=utf-8'); return
                if self.path!=f'/{owner.token}/status': self.reply(404,'No disponible'); return
                self.reply(200,json.dumps(owner.status()),'application/json; charset=utf-8')
            def do_POST(self):
                if self.path!=f'/{owner.token}/batch': self.reply(404,'No disponible'); return
                if owner.remaining()<=0: self.reply(410,'El QR ha caducado.'); return
                with owner.lock:
                    route=owner.route
                    if not route or route[0]!=self.headers.get('X-Destination') or owner.receiving or owner.items.full(): self.reply(409,'El destino ha cambiado o Ágora está ocupado. Comprueba la pantalla y vuelve a enviar.'); return
                    owner.receiving=True
                try:
                    try:
                        size=int(self.headers.get('Content-Length','0')); files=json.loads(unquote(self.headers.get('X-Files','')))
                        if not isinstance(files,list) or not 1<=len(files)<=route[3] or not 0<size<=MAX_BYTES: raise ValueError()
                        clean=[]
                        for name,n in files:
                            name=name.replace(chr(92),'/').split('/')[-1]
                            if not name or len(name)>255 or Path(name).suffix.lower() not in route[2] or type(n)!=int or n<=0: raise ValueError()
                            clean.append((name,n))
                        if sum(n for _,n in clean)!=size: raise ValueError()
                    except (ValueError,TypeError,AttributeError): self.reply(400,'Archivos no válidos para el destino seleccionado.'); return
                    items=[]
                    try:
                        for name,n in clean:
                            data=self.rfile.read(n)
                            if len(data)!=n: self.reply(400,'Transferencia incompleta.'); return
                            items.append((name,data))
                    except OSError: return
                    with owner.lock:
                        if owner.remaining()<=0: self.reply(410,'El QR ha caducado.'); return
                        if owner.route!=route: self.reply(409,'El destino cambió durante el envío. Vuelve a enviar desde la pantalla correcta.'); return
                        owner.items.put_nowait((route[0],items))
                    self.reply(200,'Recibido')
                finally:
                    with owner.lock: owner.receiving=False
        self.server=ThreadingHTTPServer((host,0),Handler); self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.1},daemon=True); self.thread.start()
    def remaining(self): return 0 if self.closed.is_set() else max(0,self.deadline-time.monotonic())
    def status(self):
        with self.lock:
            r=self.route; left=self.remaining(); ready=bool(r and left>0 and not self.receiving and self.items.empty())
            return dict(token=r[0] if ready else None,label=r[1] if ready else ('Ágora está ocupado; espera a que termine.' if self.receiving or not self.items.empty() else 'Abre Soluciones, Respuestas automáticas o Mis plantillas en Ágora.' if left else 'Conexión caducada.'),extensions=list(r[2]) if r else [],max_files=r[3] if r else 1,remaining=left)
    def set_route(self,route):
        with self.lock: self.route=route
    def url(self,address): return f'http://{address}:{self.server.server_port}/{self.token}/'
    def close(self):
        if self.closed.is_set(): return
        self.closed.set(); self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=1)
