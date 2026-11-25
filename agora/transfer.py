"""Temporary local HTTP upload, scoped by an unpredictable session token."""
import html, json, queue, secrets, socket, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from .answer_import import MAX_BYTES

PAGE='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ágora</title><style>body{font:17px system-ui;background:#fff7fa;color:#75405b;margin:24px}main{max-width:520px;margin:auto;padding:24px;background:white;border-radius:20px}button{background:#a55379;color:white;border:0;border-radius:12px;padding:14px;width:100%;font:inherit}input{max-width:100%;margin:18px 0}progress{width:100%}</style><main><h1>ÁGORA</h1><p>Enviar documento al ordenador</p><input id="file" type="file" accept=".pdf,.docx"/><button id="send">Enviar documento</button><p id="status" role="status"></p><progress id="progress" max="100" value="0"></progress></main><script>const f=document.querySelector('#file'),b=document.querySelector('#send'),s=document.querySelector('#status'),p=document.querySelector('#progress');b.onclick=()=>{if(!f.files.length){s.textContent='Selecciona un documento.';return}const file=f.files[0];if(file.size>104857600){s.textContent='Máximo 100 MB.';return}b.disabled=true;s.textContent='Enviando…';const x=new XMLHttpRequest();x.open('POST',location.pathname+'upload');x.setRequestHeader('X-File-Name',encodeURIComponent(file.name));x.upload.onprogress=e=>{if(e.lengthComputable)p.value=e.loaded/e.total*100};x.onload=()=>{s.textContent=x.status===200?'Documento recibido. Ya puedes volver al ordenador.':'No se pudo enviar ('+x.status+').';b.disabled=x.status===200};x.onerror=()=>{s.textContent='Conexión interrumpida. Comprueba el Wi-Fi.';b.disabled=false};x.send(file)};</script></html>'''

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

class UploadSession:
    def __init__(self, host='0.0.0.0', extensions=('.pdf','.docx')):
        self.token=secrets.token_urlsafe(24); self.items=queue.Queue(maxsize=1); self.lock=threading.Lock(); self.accepted=False
        self.extensions=tuple(extensions); owner=self
        class Handler(BaseHTTPRequestHandler):
            def setup(self): super().setup(); self.connection.settimeout(30)
            def log_message(self,*args): pass
            def reply(self,code,body,kind='text/plain; charset=utf-8'):
                data=body.encode('utf-8'); self.send_response(code); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer'); self.end_headers(); self.wfile.write(data)
            def do_GET(self):
                if self.path!=f'/{owner.token}/': self.reply(404,'No disponible'); return
                page=PAGE.replace('accept=".pdf,.docx"','accept="'+html.escape(','.join(owner.extensions))+'"')
                self.reply(200,page,'text/html; charset=utf-8')
            def do_POST(self):
                if self.path!=f'/{owner.token}/upload': self.reply(404,'No disponible'); return
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
        self.server=ThreadingHTTPServer((host,0),Handler); self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.1},daemon=True); self.thread.start()
    def url(self,address): return f'http://{address}:{self.server.server_port}/{self.token}/'
    def close(self): self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=1)
