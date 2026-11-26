"""Temporary local HTTP upload, scoped by an unpredictable session token."""
import html, json, queue, secrets, socket, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from .answer_import import MAX_BYTES

PAGE='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ágora</title><style>body{font:17px system-ui;background:#fff7fa;color:#75405b;margin:24px}main{max-width:520px;margin:auto;padding:24px;background:white;border-radius:20px}button{background:#a55379;color:white;border:0;border-radius:12px;padding:14px;width:100%;font:inherit}h1{display:flex;align-items:center;gap:12px;font-family:Georgia,serif}h1 svg{width:48px;height:48px;flex:none}.pick{display:block;box-sizing:border-box;text-align:center;background:#f1d0df;color:#75405b;border-radius:12px;padding:14px;width:100%;font:inherit;margin:18px 0 10px;cursor:pointer}.pick:focus-within{outline:2px solid #a55379}.pick input{position:absolute;opacity:0;width:1px;height:1px}#filename{overflow-wrap:anywhere;font-size:14px;margin:0 0 14px;text-align:center}progress{width:100%}</style><main><h1><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect x="2" y="2" width="96" height="96" rx="25" fill="#F1D0DF"/><g fill="none" stroke="#A35B7C" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"><path d="M19 35L50 18 81 35Z M26 43V69 M42 43V69 M58 43V69 M74 43V69 M20 77H80 M15 84H85"/></g></svg>ÁGORA</h1><p>Enviar documento al ordenador</p><label class="pick">Seleccionar archivos<input id="file" type="file" accept=".pdf,.docx" onchange="document.getElementById('filename').textContent=Array.from(this.files).map(f=>f.name).join(', ')||'Ningún archivo seleccionado'"/></label><p id="filename">Ningún archivo seleccionado</p><button id="send">Enviar documento</button><p id="status" role="status"></p><progress id="progress" max="100" value="0"></progress></main><script>const f=document.querySelector('#file'),b=document.querySelector('#send'),s=document.querySelector('#status'),p=document.querySelector('#progress');b.onclick=()=>{if(!f.files.length){s.textContent='Selecciona un documento.';return}const file=f.files[0];if(file.size>104857600){s.textContent='Máximo 100 MB.';return}b.disabled=true;s.textContent='Enviando…';const x=new XMLHttpRequest();x.open('POST',location.pathname+'upload');x.setRequestHeader('X-File-Name',encodeURIComponent(file.name));x.upload.onprogress=e=>{if(e.lengthComputable)p.value=e.loaded/e.total*100};x.onload=()=>{s.textContent=x.status===200?'Documento recibido. Ya puedes volver al ordenador.':'No se pudo enviar ('+x.status+').';b.disabled=x.status===200};x.onerror=()=>{s.textContent='Conexión interrumpida. Comprueba el Wi-Fi.';b.disabled=false};x.send(file)};</script></html>'''

def local_addresses():
    addresses=[]
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            # Determines the selected network interface; no data is sent.
            s.connect(('192.0.2.1',9)); addresses.append(s.getsockname()[0])
    except OSError: pass
    try: addresses.extend(x[4][0] for x in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET))
    except OSError: pass
    return list(dict.fromkeys(a for a in addresses if not a.startswith(('127.','169.254.','0.'))))

# A batch travels as one request; no partially received set is published.
MULTI_JS="""const f=document.querySelector('#file'),b=document.querySelector('#send'),s=document.querySelector('#status'),p=document.querySelector('#progress');b.onclick=()=>{const files=Array.from(f.files);if(!files.length||files.length>2){s.textContent='Selecciona una o dos hojas.';return}const total=files.reduce((n,v)=>n+v.size,0);if(total>104857600||files.some(v=>!v.size)){s.textContent='Máximo 100 MB en total.';return}b.disabled=true;s.textContent='Enviando…';const x=new XMLHttpRequest();x.open('POST',location.pathname+'batch');x.setRequestHeader('X-Files',encodeURIComponent(JSON.stringify(files.map(v=>[v.name,v.size]))));x.upload.onprogress=e=>{if(e.lengthComputable)p.value=e.loaded/e.total*100};x.onload=()=>{s.textContent=x.status===200?'Hojas recibidas. Vuelve al ordenador.':'No se pudo enviar ('+x.status+').';b.disabled=x.status===200};x.onerror=()=>{s.textContent='Conexión interrumpida.';b.disabled=false};x.send(new Blob(files));};"""

class UploadSession:
    def __init__(self, host='0.0.0.0', extensions=('.pdf','.docx'), multiple=False, max_files=2):
        self.token=secrets.token_urlsafe(24); self.items=queue.Queue(maxsize=1); self.lock=threading.Lock(); self.accepted=False
        self.extensions=tuple(extensions); self.multiple=multiple; self.max_files=max(2,min(20,int(max_files))); owner=self
        class Handler(BaseHTTPRequestHandler):
            def setup(self): super().setup(); self.connection.settimeout(30)
            def log_message(self,*args): pass
            def reply(self,code,body,kind='text/plain; charset=utf-8'):
                data=body.encode('utf-8'); self.send_response(code); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer'); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                if self.path!=f'/{owner.token}/': self.reply(404,'No disponible'); return
                page=PAGE.replace('accept=".pdf,.docx"','accept="'+html.escape(','.join(owner.extensions))+'"')
                if owner.multiple: page=page.split('<script>')[0].replace('type="file"','type="file" multiple').replace('Enviar documento','Enviar hojas')+'<script>'+MULTI_JS.replace('files.length>2',f'files.length>{owner.max_files}').replace('Selecciona una o dos hojas.',f'Selecciona hasta {owner.max_files} archivos.')+'</script></html>'
                self.reply(200,page,'text/html; charset=utf-8')
            def do_POST(self):
                if owner.multiple and self.path==f'/{owner.token}/batch': return self.batch()
                if owner.multiple or self.path!=f'/{owner.token}/upload': self.reply(404,'No disponible'); return
                try: size=int(self.headers.get('Content-Length','0'))
                except ValueError: self.reply(400,'Tamaño incorrecto'); return
                if not 0<size<=MAX_BYTES: self.reply(413,'Máximo 100 MB'); return
                name=unquote(self.headers.get('X-File-Name','')).replace('\\','/').split('/')[-1]
                if not name or len(name)>255 or Path(name).suffix.lower() not in owner.extensions: self.reply(415,'Formato no admitido'); return
                with owner.lock:
                    if owner.accepted: self.reply(409,'Ya recibido'); return
                    try: data=self.rfile.read(size)
                    except (OSError,TimeoutError): return
                    if len(data)!=size: self.reply(400,'Transferencia incompleta'); return
                    owner.accepted=True; owner.items.put_nowait((name,data)); self.reply(200,'Recibido')
            def batch(self):
                try:
                    size=int(self.headers.get('Content-Length','0')); files=json.loads(unquote(self.headers.get('X-Files','')))
                    if not isinstance(files,list) or not 1<=len(files)<=owner.max_files or not 0<size<=MAX_BYTES: raise ValueError()
                    clean=[]
                    for name,n in files:
                        name=name.replace(chr(92),'/').split('/')[-1]
                        if not name or len(name)>255 or Path(name).suffix.lower() not in owner.extensions or type(n)!=int or n<=0: raise ValueError()
                        clean.append((name,n))
                    if sum(n for _,n in clean)!=size: raise ValueError()
                except (ValueError,TypeError,AttributeError): self.reply(400,'Archivos no válidos'); return
                with owner.lock:
                    if owner.accepted: self.reply(409,'Ya recibido'); return
                    items=[]
                    try:
                        for name,n in clean:
                            data=self.rfile.read(n)
                            if len(data)!=n: self.reply(400,'Transferencia incompleta'); return
                            items.append((name,data))
                    except (OSError,TimeoutError): return
                    owner.accepted=True; owner.items.put_nowait(items); self.reply(200,'Recibido')
        self.server=ThreadingHTTPServer((host,0),Handler); self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.1},daemon=True); self.thread.start()
    def url(self,address): return f'http://{address}:{self.server.server_port}/{self.token}/'
    def close(self): self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=1)
