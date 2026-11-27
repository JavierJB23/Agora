"""Route mobile batches to the current screen, never a different exam silently."""
import queue,secrets,math
from PySide6.QtCore import QObject,QTimer
from PySide6.QtWidgets import QApplication,QMessageBox
from .mobile_session import MobileSession

class MobileConnection(QObject):
    def __init__(self,window):
        super().__init__(window); self.window=window; self.session=None; self.dialog=None; self.route_key=None; self.route_token=None; self.busy=False; self.in_poll=False
        self.timer=QTimer(self); self.timer.setInterval(150); self.timer.timeout.connect(self.poll); self.timer.start()
    def invalidate(self,*_):
        self.route_key=None; self.route_token=None
        if self.session: self.session.set_route(None)
    def start(self,dialog):
        if self.session and self.session.remaining()<=0: self.close(expired=True)
        if not self.session: self.session=MobileSession()
        self.dialog=dialog; self.invalidate(); self.update_route(); return self.session
    def detach(self,dialog):
        if self.dialog is dialog: self.dialog=None; self.invalidate()
    def close(self,checked=False,expired=False):
        if self.session:
            self.session.retire("expired" if expired else "disconnected"); self.session=None
        self.invalidate(); self.window.mobile_status.hide(); self.window.mobile_stop.hide()
    def destination(self):
        w=self.window
        if self.busy or not w.isEnabled(): return None
        modal=QApplication.activeModalWidget()
        if self.dialog is not None and (modal is None or modal is self.dialog) and self.dialog.isVisible():
            d=self.dialog; return (('dialog',id(d)),self.screen_label(),tuple(d.extensions),d.max_files,d.receive_mobile)
        if modal is not None: return None
        current=w.stack.currentWidget()
        for mode in ('manual','automatic'):
            if current is w.pages.get(mode):
                p=getattr(w,mode)
                if p.stage==1: return ((mode,1,id(p.key),p.attempt_id),'Corrector '+('manual' if mode=='manual' else 'automático')+' · Soluciones · '+p.config.name,('.pdf','.docx'),1,p.receive_mobile_key)
                if p.stage==2 and mode=='automatic':
                    from .omr import EXTENSIONS
                    return ((mode,2,id(p.reader),p.attempt_id),'Corrector automático · Respuestas · '+p.config.name,EXTENSIONS,20,p.reader.import_items)
        if current is w.pages.get('library') and w.library_stack.currentIndex()==1 and w.library_tabs.currentIndex()==1:
            return (('library',1),'Mi temario · Mis plantillas',('.pdf','.docx'),20,w.receive_library_items)
        return None
    def screen_label(self):
        w=self.window
        for mode in ('manual','automatic'):
            if w.stack.currentWidget() is w.pages.get(mode):
                p=getattr(w,mode); return 'Corrector '+('manual' if mode=='manual' else 'automático')+' · '+('Soluciones' if p.stage==1 else 'Respuestas')+' · '+p.config.name
        if w.stack.currentWidget() is w.pages.get('library'): return 'Mi temario · Mis plantillas'
        return 'Importar documento'
    def update_route(self):
        if not self.session: return None
        d=self.destination(); key=d[0] if d else None
        if key!=self.route_key:
            self.route_key=key; self.route_token=secrets.token_urlsafe(18) if d else None
        self.session.set_route((self.route_token,d[1],d[2],d[3]) if d else None)
        return d
    def poll(self):
        if self.in_poll or not self.session: return
        self.in_poll=True
        try:
            left=math.ceil(self.session.remaining()); self.window.mobile_status.show(); self.window.mobile_stop.show(); self.window.mobile_status.setText(f'Móvil conectado · {left//60}:{left%60:02d}')
            if not left:
                d=self.dialog; self.close(expired=True)
                if d is not None: d.mobile_expired()
                return
            d=self.update_route()
            try: token,items=self.session.items.get_nowait()
            except queue.Empty: return
            if not d or token!=self.route_token:
                self.window.statusBar().showMessage('Envío descartado: cambió el destino. Vuelve a enviarlo desde la pantalla correcta.',10000); return
            self.busy=True; self.session.set_route(None)
            try: d[4](items)
            except Exception as e: QMessageBox.warning(self.window,'No se pudo importar',str(e))
            finally: self.busy=False; self.invalidate()
        finally: self.in_poll=False
