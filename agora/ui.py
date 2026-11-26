from pathlib import Path
from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QIcon, QDesktopServices, QFont
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QToolButton, QFrame, QStackedWidget, QScrollArea, QLineEdit, QMessageBox, QSizePolicy, QTabWidget)
from . import VERSION, BLOCK
from .modules import MODULES
from .storage import Storage
from .manual import ManualPage, confirm
from .controls import SafeComboBox, CenteredTile
from .grading import ExamConfig, evaluate, format_number

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
STYLE = '''
QWidget {font-family: "Segoe UI", sans-serif; font-size: 14px; color: #563D49;}
QMainWindow, QWidget#root, QWidget#canvas {background: #FFF7FA;}
QFrame#sidebar {background: #FFFFFF; border-right: 1px solid #EFDFE7;}
QFrame#hero {background: #F4D6E3; border: 1px solid #EFCBDD; border-radius: 20px;}
QFrame#tile, QFrame#panel {background: white; border: 1px solid #EEDDE5; border-radius: 16px;}
QLabel#brand {font-family: "Palatino Linotype", "Georgia", serif; font-size: 30px; font-weight: 700; color: #8C4667;}
QLabel#headline {font-size: 30px; font-weight: 650; color: #75405B;}
QLabel#heading {font-size: 25px; font-weight: 650; color: #75405B;}
QLabel#tileTitle {font-size: 17px; font-weight: 600; color: #73425A;}
QLabel#historyMode {font-size: 14px; font-style: italic; font-weight: 600; color: #A55379;}
QTabWidget#libraryTabs::pane {border: none; background: transparent;}
QTabBar::tab {background: #FFFFFF; border: 1px solid #EEDDE5; padding: 10px 22px; border-top-left-radius: 8px; border-top-right-radius: 8px;}
QTabBar::tab:selected {background: #F4D6E3; color: #75405B; font-weight: 600;}
QLabel#muted {color: #795C6B; font-size: 13px;}
QLabel#tag {background: #FAEDF3; color: #8D5070; border-radius: 8px; padding: 5px 9px; font-size: 12px;}
QPushButton {border: 1px solid #EBD5E0; border-radius: 9px; padding: 9px 13px; background: #FFFFFF; font-weight: 500; text-align: left;}
QPushButton:hover {background: #FAEAF1; border-color: #DDAEC4;}
QPushButton:focus, QLineEdit:focus {border: 2px solid #B45F86;}
QPushButton#nav {border: 1px solid transparent; padding: 10px 12px; background: transparent;}
QPushButton#nav:checked {background: #F6DCE8; color: #803D5E; border: 1px solid #EBC5D8; font-weight: 600;}
QPushButton#nav:hover {background: #FBEDF3;}
QPushButton#primary {background: #A55379; color: white; border: 1px solid #A55379; text-align:center;}
QPushButton#primary:hover {background: #904268;}
QPushButton#softAction {background:#F4D6E3; color:#75405B; border:1px solid #E8CEDB; text-align:center;}
QPushButton#softAction:hover {background:#EBC1D4;}
QPushButton#libraryTile {background:white; border:1px solid #EEDDE5; border-radius:16px;}
QPushButton#libraryTile:hover {background:#FAEAF1; border-color:#DDAEC4;}
QPushButton#libraryTile:pressed {background:#F1D0DF;}
QToolButton#homeTile:checked {background:#F4D6E3; border:1px solid #C987A6;}
QToolButton#homeTile {background: #FFFFFF; border: 1px solid #EEDDE5; border-radius: 16px; padding: 10px 8px; color: #73425A; font-size: 17px; font-weight: 600;}
QToolButton#homeTile:hover {background: #FAEAF1; border-color: #DDAEC4;}
QToolButton#homeTile:pressed {background: #F1D0DF; border-color: #C987A6;}
QToolButton#homeTile:focus {border: 2px solid #B45F86;}
QLineEdit {background: #FFF9FB; border: 1px solid #E8CEDB; border-radius: 9px; padding: 10px; selection-background-color: #A55379;}
QScrollArea {border: none; background: transparent;}
QScrollBar:vertical {background: #F9ECF2; width: 9px; border-radius: 4px; margin: 2px;}
QScrollBar::handle:vertical {background: #D8A9BF; border-radius: 4px; min-height: 28px;}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {height: 0;}
QPushButton#manualStep {background: #FFFFFF; border: 1px solid #EEDDE5; border-radius: 9px; padding: 9px; color:#795C6B; font-size:13px;}
QPushButton#manualStep[active="true"] {background:#F4D6E3; color:#75405B; font-weight:700;}
QPushButton#manualStep:hover {background:#FAEAF1; border-color:#DDAEC4;}
QSpinBox, QComboBox {background:#FFF9FB; border:1px solid #E8CEDB; border-radius:8px; padding:8px; min-height:20px;}
QComboBox {padding-right:34px; combobox-popup:0;}
QComboBox::drop-down {subcontrol-origin:padding; subcontrol-position:top right; width:30px; border:0; border-left:1px solid #EEDDE5; border-top-right-radius:8px; border-bottom-right-radius:8px; background:#FAEDF3;}
QComboBox::drop-down:hover {background:#F4D6E3;}
QComboBox::down-arrow {image:url("@ASSETS@/chevron-down.svg"); width:14px; height:14px;}
QComboBox QAbstractItemView {background:white; border:1px solid #E8CEDB; border-radius:8px; padding:5px; outline:0; selection-background-color:#F4D6E3; selection-color:#563D49;}
QComboBox QAbstractItemView::item {min-height:30px; padding:4px 8px;}
QComboBox QLineEdit {border:0; padding:0; background:transparent;}
QSpinBox {padding-right:32px;}
QSpinBox::up-button, QSpinBox::down-button {subcontrol-origin:padding; width:27px; border:0; border-left:1px solid #EEDDE5; background:#FAEDF3;}
QSpinBox::up-button {subcontrol-position:top right; border-top-right-radius:8px;}
QSpinBox::down-button {subcontrol-position:bottom right; border-bottom-right-radius:8px;}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {background:#F4D6E3;}
QSpinBox::up-arrow {image:url("@ASSETS@/chevron-up.svg"); width:13px; height:13px;}
QSpinBox::down-arrow {image:url("@ASSETS@/chevron-down.svg"); width:13px; height:13px;}
QSpinBox:focus, QComboBox:focus {border:1px solid #B45F86;}
QDialog, QMessageBox {background:#FFF7FA;}
QMessageBox QPushButton {min-width:65px; text-align:center;}
QCheckBox {spacing:8px;}
QPushButton#manualNumber {text-align:center; padding:5px; background:#FAEDF3; border:1px solid #EEDDE5;}
QPushButton#manualNumber[pending="true"] {background:#E6AFC9; color:#75405B; font-weight:700; border:1px solid #C27A9E;}
QPushButton#manualNumber[selected="true"] {border:2px solid #A55379; background:#A55379; color:white; font-weight:700;}
QPushButton#manualNumber[pending="true"][selected="true"] {background:#E6AFC9; color:#75405B; border:2px solid #A55379; font-weight:700;}
QPushButton#manualChoice, QPushButton#manualClear {text-align:center; padding:5px 2px; border-radius:7px;}
QPushButton#manualChoice:checked {background:#A55379; color:white; border-color:#904268; font-weight:700;}
QPushButton:disabled {color:#BBA9B2; background:#F8F5F7;}
QFrame#manualMetric {background:#FFF7FA; border:1px solid #EEDDE5; border-radius:10px;}
QLabel#correct, QLabel#wrong, QLabel#neutral {font-size:25px; font-weight:650; color:#75405B;}
QLabel#correct {color:#30764D;} QLabel#wrong {color:#A13952;}
QTableWidget {background:white; alternate-background-color:#FFF7FA; border:1px solid #EEDDE5; gridline-color:#F2E3EB; selection-background-color:#F4D6E3; selection-color:#563D49;}
QHeaderView::section {background:#F4D6E3; border:0; padding:7px; color:#75405B; font-weight:600;}

'''

def icon(name):
    return QIcon(str(ASSETS / (name + '.svg')))

def label(text, role='', wrap=False):
    w = QLabel(text)
    w.setTextFormat(Qt.TextFormat.PlainText)
    if role: w.setObjectName(role)
    w.setWordWrap(wrap)
    return w

def button(text, symbol=None, role=''):
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if role: b.setObjectName(role)
    if symbol:
        b.setIcon(icon(symbol)); b.setIconSize(QSize(20,20))
    return b

def frame(role='panel'):
    w = QFrame(); w.setObjectName(role); return w

def vertical(parent, margins=(0,0,0,0), spacing=12):
    l=QVBoxLayout(parent); l.setContentsMargins(*margins); l.setSpacing(spacing); return l

class CurrentPageStack(QStackedWidget):
    # The library landing page must not inherit the height of a long hidden list.
    def sizeHint(self):
        w=self.currentWidget(); return w.sizeHint() if w is not None else super().sizeHint()
    def minimumSizeHint(self):
        w=self.currentWidget(); return w.minimumSizeHint() if w is not None else super().minimumSizeHint()

class HomeTile(CenteredTile):
    """Whole tile is a keyboard-accessible button with an icon above its name."""
    def __init__(self, module):
        super().__init__(module.name,icon(module.icon))
        self.full_name=module.name
        self.setObjectName('homeTile')
        self.setText(self.full_name)
        self.setAccessibleName(self.full_name)
        self.setIcon(icon(module.icon))
        self.setIconSize(QSize(64,64))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setFixedHeight(170)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        name=self.full_name
        # Keep one line on normal windows; split long names on small windows.
        if self.fontMetrics().horizontalAdvance(name)>self.width()-24 and ' ' in name:
            words=name.split()
            cut=min(range(1,len(words)),key=lambda i:abs(len(' '.join(words[:i]))-len(' '.join(words[i:]))))
            name=' '.join(words[:cut])+'\n'+' '.join(words[cut:])
        if self.text()!=name: self.setText(name)

class MainWindow(QMainWindow):
    def __init__(self, storage: Storage):
        super().__init__(); self.storage=storage
        self.setWindowTitle(f'Ágora · v{VERSION} · Block {BLOCK}')
        self.setWindowIcon(icon('logo')); self.resize(1200, 830); self.setMinimumSize(850, 620)
        root=QWidget(); root.setObjectName('root'); self.setCentralWidget(root); self.setStyleSheet(STYLE.replace('@ASSETS@', ASSETS.as_posix()))
        layout=QHBoxLayout(root); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        side=frame('sidebar'); side.setFixedWidth(235); layout.addWidget(side)
        sl=vertical(side,(16,22,16,16),7)
        brand=QHBoxLayout(); brand.setSpacing(10)
        mark=QLabel(); mark.setPixmap(icon('logo').pixmap(47,47)); brand.addWidget(mark)
        brand.addWidget(label('ÁGORA','brand')); brand.addStretch(); sl.addLayout(brand)
        sl.addWidget(label('Tu espacio de aprendizaje','muted')); sl.addSpacing(18)
        self.nav={}; self.pages={}; self.stack=QStackedWidget(); layout.addWidget(self.stack,1)
        self.add_nav(sl,'home','Inicio','home')
        for m in MODULES: self.add_nav(sl,m.key,m.name,m.icon)
        sl.addStretch(); self.add_nav(sl,'settings','Configuración','settings')
        sl.addWidget(label(f'v{VERSION}  ·  BLOCK {BLOCK}','muted')); sl.addWidget(label('Datos locales · Sin cuenta','muted'))
        self.make_home()
        for m in MODULES:
            if m.key=='manual':
                l=self.page('manual'); self.manual=ManualPage(self.storage,lambda:self.go('home')); l.addWidget(self.manual)
            elif m.key=='history': self.make_history()
            elif m.key=='library': self.make_library()
            elif m.key=='automatic':
                l=self.page('automatic'); self.automatic=ManualPage(self.storage,lambda:self.go('home'),mode='automatic'); l.addWidget(self.automatic)
            else: self.make_module(m)
        self.make_settings(); self.go('home')
    def add_nav(self, layout, key, name, symbol):
        b=button(name,symbol,'nav'); b.setCheckable(True); b.clicked.connect(lambda checked=False,k=key:self.go(k)); layout.addWidget(b); self.nav[key]=b
    def page(self,key):
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        canvas=QWidget(); canvas.setObjectName('canvas'); scroll.setWidget(canvas)
        self.pages[key]=scroll; self.stack.addWidget(scroll)
        return vertical(canvas,(30,25,30,25),16)
    def go(self,key,skip_entry=False):
        current=self.stack.currentWidget()
        for mode in ('manual','automatic'):
            if current is self.pages.get(mode) and key!=mode and not getattr(self,mode).allow_leave():
                self.sync_nav(mode); return
        if key in ('manual','automatic') and current is not self.pages.get(key) and not skip_entry and not getattr(self,key).allow_enter():
            self.sync_nav(next(k for k,p in self.pages.items() if p is current)); return
        if key=='home': self.refresh_home()
        if key=='settings': self.load_settings()
        if key=='history': self.refresh_history()
        if key=='library': self.library_stack.setCurrentIndex(0)
        self.sync_nav(key); self.stack.setCurrentWidget(self.pages[key])
        if key in ('manual','automatic'): getattr(self,key).focus_entry()
    def sync_nav(self,key):
        for k,b in self.nav.items(): b.setChecked(k==key)
    def closeEvent(self,event):
        for mode in ('manual','automatic'):
            if self.stack.currentWidget() is self.pages.get(mode) and not getattr(self,mode).allow_leave(): event.ignore(); return
        super().closeEvent(event)
    def make_library(self):
        l=self.page('library'); self.library_stack=CurrentPageStack(); self.library_stack.currentChanged.connect(lambda *_:self.library_stack.updateGeometry()); l.addWidget(self.library_stack); l.addStretch()
        root=QWidget(); rl=vertical(root,spacing=16); self.library_stack.addWidget(root)
        back=button('Volver al inicio','home'); back.clicked.connect(lambda:self.go('home')); rl.addWidget(back,0,Qt.AlignmentFlag.AlignLeft)
        rl.addWidget(label('Mi temario','heading')); tiles=QHBoxLayout(); self.library_buttons=[]
        for i,(name,symbol) in enumerate((('Mis temas','books'),('Mis plantillas','template'))):
            b=CenteredTile(name,icon(symbol)); b.setFixedSize(220,220); b.clicked.connect(lambda checked=False,j=i:self.select_library_tab(j)); tiles.addWidget(b); self.library_buttons.append(b)
        tiles.addStretch(); rl.addLayout(tiles); rl.addStretch()
        tabs=QTabWidget(); tabs.setObjectName('libraryTabs'); tabs.tabBar().hide(); self.library_tabs=tabs; self.library_stack.addWidget(tabs)
        themes=QWidget(); tl=vertical(themes,spacing=16); back=button('Volver a Mi temario','book'); back.clicked.connect(lambda:self.library_stack.setCurrentIndex(0)); tl.addWidget(back,0,Qt.AlignmentFlag.AlignLeft); tl.addWidget(label('Mis temas','heading')); tl.addWidget(label('Temario de estudio','tileTitle')); tl.addStretch(); tabs.addTab(themes,'Mis temas')
        archive=QWidget(); al=vertical(archive,spacing=16); tabs.addTab(archive,'Mis plantillas')
        back=button('Volver a Mi temario','book'); back.clicked.connect(lambda:self.library_stack.setCurrentIndex(0)); al.addWidget(back,0,Qt.AlignmentFlag.AlignLeft); al.addWidget(label('Mis plantillas','heading'))
        pane=frame(); pl=vertical(pane,(18,18,18,18),12); al.addWidget(pane)
        toolbar=QHBoxLayout(); imp=button('Importar plantillas','template','primary'); imp.clicked.connect(self.import_library); toolbar.addWidget(imp); toolbar.addStretch(); toolbar.addWidget(label('Ordenar por')); self.library_sort=SafeComboBox()
        for title,value in [('Más recientes','new'),('Más antiguas','old'),('Nombre A–Z','az'),('Nombre Z–A','za')]: self.library_sort.addItem(title,value)
        toolbar.addWidget(self.library_sort); pl.addLayout(toolbar)
        items=QWidget(); self.library_layout=vertical(items,spacing=10); pl.addWidget(items); al.addStretch()
        self.library_sort.currentIndexChanged.connect(lambda *_:self.refresh_library())

    def select_library_tab(self,index):
        self.library_tabs.setCurrentIndex(index); self.library_stack.setCurrentIndex(1)
        if index==1: self.refresh_library()

    def import_library(self):
        from .import_ui import ImportDialog
        from PySide6.QtWidgets import QDialog
        dialog=ImportDialog(self,multiple=True,max_files=20)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        for name,data in dialog.items:
            self.register_library_document(name,data)
        self.refresh_library()

    def register_library_document(self,name,data,ref=None):
        from dataclasses import asdict
        from .answer_import import extract_key
        from .template_ui import review_key,named_save
        try:
            imported=extract_key(data,name); options=review_key(self,imported,name)
            if options is None: return
            c=ExamConfig(name=Path(name).stem[:120] or 'Plantilla',questions=len(imported.ordinary),reserves=len(imported.reserves),options=options)
            payload={'config':asdict(c),'key':imported.key,'key_source':name,'document_ref':ref}
            return named_save(self,self.storage,payload,c.name,document=None if ref else (name,data))
        except Exception as e: QMessageBox.warning(self,'No se pudo importar '+name,str(e))

    def register_existing_document(self,ref):
        try: name,data=self.storage.load_solution_document(ref); self.register_library_document(name,data,ref)
        except Exception as e: QMessageBox.warning(self,'No se pudo abrir',str(e))
        self.refresh_library()

    def refresh_library(self):
        from datetime import datetime
        from .library_ui import consult_document,consult_template
        l=self.library_layout
        while l.count():
            it=l.takeAt(0); w=it.widget()
            if w: w.hide(); w.deleteLater()
        try: entries=self.storage.library_entries(self.library_sort.currentData() or 'new')
        except Exception as e: l.addWidget(label('No se pudo consultar la biblioteca: '+str(e),wrap=True)); return
        if not entries: l.addWidget(label('Todavía no hay plantillas.','muted'))
        for e in entries:
            item=frame('tile'); h=QHBoxLayout(item); h.setContentsMargins(12,12,12,12); info=QVBoxLayout(); info.addWidget(label(e['name'],'tileTitle',True))
            size=f"{e['size']/1024/1024:.2f} MB" if e['size'] is not None else 'Sin archivo original'
            stamp=datetime.fromisoformat(e['created']).astimezone().strftime('%d/%m/%Y · %H:%M') if e['created'] else 'Fecha no disponible'
            info.addWidget(label(size+' · '+stamp,'muted',True)); h.addLayout(info,1)
            if e['ref']:
                b=button('Consultar PDF' if e['filename'].lower().endswith('.pdf') else 'Consultar Word',role='softAction'); b.clicked.connect(lambda checked=False,r=e['ref']:consult_document(self,self.storage,r)); h.addWidget(b)
            if e['payload']:
                b=button('Consultar plantilla',role='softAction'); b.clicked.connect(lambda checked=False,n=e['name'],p=e['payload']:consult_template(self,self.storage,n,p)); h.addWidget(b)
            b=button('Eliminar plantilla',role='softAction'); b.clicked.connect(lambda checked=False,t=e['id']:self.delete_library_template(t)); h.addWidget(b)
            l.addWidget(item)
        l.addStretch(); self.library_stack.updateGeometry()

    def delete_library_template(self,tid):
        from .template_ui import delete_named_template
        try:
            affected={i for i,_ in self.storage.template_attempts(tid)}
            pages=[getattr(self,mode) for mode in ('manual','automatic')]
            active=[p for p in pages if p.template_id==tid or p.attempt_id in affected]
            if delete_named_template(self,self.storage,tid,bool(active)):
                for p in active: p.reset_state()
                self.refresh_library()
        except Exception as e: QMessageBox.warning(self,'No se pudo eliminar',str(e))

    def make_history(self):
        l=self.page('history'); back=button('Volver al inicio','home'); back.clicked.connect(lambda:self.go('home')); l.addWidget(back,0,Qt.AlignmentFlag.AlignLeft)
        l.addWidget(label('Mis simulacros','heading')); l.addWidget(label('Simulacros manuales y automáticos, tanto en curso como finalizados.','muted',True))
        self.history_panel=frame(); self.history_layout=vertical(self.history_panel,(20,20,20,20),12); l.addWidget(self.history_panel); l.addStretch()
    def refresh_history(self):
        from datetime import datetime
        l=self.history_layout
        while l.count():
            item=l.takeAt(0); w=item.widget()
            if w: w.hide(); w.deleteLater()
        try: rows=self.storage.attempts()
        except Exception as e: l.addWidget(label('No se pudieron leer los simulacros: '+str(e),wrap=True)); return
        if not rows: l.addWidget(label('Todavía no hay simulacros guardados. Pulsa Guardar progreso en cualquiera de los correctores.','muted',True)); return
        for i,stamp,d in rows:
            c=ExamConfig(**d['config']); answers=d['answers']; key=d['key']; count=sum(bool(v) for v in answers); complete=bool(d.get('key_source')) and all(key) and all(answers) and not d.get('form') and d.get('corrected',d.get('stage')==3)
            name=d.get('form',{}).get('name',c.name) or c.name
            summary=f'En curso · {count}/{c.size} respuestas registradas'
            if complete:
                r=evaluate(c,key,answers); summary='Finalizado · Nota '+format_number(r.grade)+' / '+format_number(c.maximum)
            mode='Corrección automática' if d.get('mode')=='automatic' else 'Corrección manual'
            item=frame('tile'); h=QHBoxLayout(item); h.setContentsMargins(12,12,12,12); info=QVBoxLayout(); heading=QHBoxLayout(); heading.setSpacing(8); heading.addWidget(label(name,'tileTitle',True)); heading.addWidget(label('· '+mode,'historyMode')); heading.addStretch(); info.addLayout(heading); info.addWidget(label(summary,'muted',True)); info.addWidget(label(datetime.fromisoformat(stamp).astimezone().strftime('%d/%m/%Y · %H:%M'),'muted')); h.addLayout(info,1)
            op=button('Abrir'); op.clicked.connect(lambda checked=False,aid=i:self.open_history(aid)); h.addWidget(op); delete=button('Eliminar'); delete.clicked.connect(lambda checked=False,aid=i,n=name:self.delete_history(aid,n)); h.addWidget(delete); l.addWidget(item)
    def open_history(self,aid):
        d=self.storage.load_attempt(aid)
        if not d: return
        mode=d.get('mode','manual')
        if getattr(self,mode).open_saved(aid): self.go(mode,skip_entry=True)
    def delete_history(self,aid,name):
        text=f'Se va a borrar el simulacro «{name}». Esta operación no se puede deshacer. ¿Seguro que quieres continuar?'
        if any(getattr(self,m).attempt_id==aid for m in ('manual','automatic')):
            text+='\n\nTambién se eliminará su borrador activo, incluidos los cambios no guardados.'
        if not confirm(self,'Eliminar simulacro',text): return
        try:
            if not self.storage.delete_attempt(aid):
                QMessageBox.information(self,'Eliminar simulacro','El simulacro ya no existe.'); self.refresh_history(); return
        except Exception as e:
            QMessageBox.warning(self,'No se pudo eliminar',str(e)); return
        for mode in ('manual','automatic'):
            if getattr(self,mode).attempt_id==aid: getattr(self,mode).reset_state()
        self.refresh_history()
    def make_home(self):
        l=self.page('home'); top=QHBoxLayout(); top.addWidget(label('Inicio','heading')); top.addStretch(); top.addWidget(label(f'Versión v{VERSION} · BLOCK {BLOCK}','tag')); l.addLayout(top)
        hero=frame('hero'); hl=QHBoxLayout(hero); hl.setContentsMargins(25,22,25,22)
        words=QVBoxLayout(); self.greeting=label('Tu plaza, un paso más cerca.','headline',True); words.addWidget(self.greeting)
        self.motto=label('', 'muted',True); words.addWidget(self.motto); hl.addLayout(words,1)
        art=QLabel(); art.setPixmap(icon('hero').pixmap(142,104)); hl.addWidget(art,0,Qt.AlignmentFlag.AlignVCenter); l.addWidget(hero)
        l.addWidget(label('Tus herramientas','tileTitle'))
        grid=QGridLayout(); grid.setSpacing(14)
        self.home_tiles={}
        for i,m in enumerate(MODULES):
            tile=HomeTile(m); tile.clicked.connect(lambda checked=False,k=m.key:self.go(k))
            self.home_tiles[m.key]=tile
            grid.addWidget(tile,i//4,i%4)
        for col in range(4): grid.setColumnStretch(col,1)
        l.addLayout(grid); l.addStretch()
    def refresh_home(self):
        name=self.storage.get('student_name').strip()
        self.greeting.setText(f'¡Hola, {name}!' if name else 'Tu plaza, un paso más cerca.')
        self.motto.setText(self.storage.get('welcome_message') or 'Aprende. Comprende. Avanza.')
    def make_module(self,m):
        l=self.page(m.key); back=button('Volver al inicio','home'); back.clicked.connect(lambda:self.go('home')); l.addWidget(back,0,Qt.AlignmentFlag.AlignLeft)
        l.addWidget(label(m.name,'heading',True)); l.addWidget(label(m.description,'muted',True))
        panel=frame(); p=vertical(panel,(24,24,24,24),15)
        logo=QLabel(); logo.setPixmap(icon(m.icon).pixmap(54,54)); p.addWidget(logo)
        p.addWidget(label('Disponible en un próximo bloque','tileTitle')); p.addWidget(label('Desarrollo previsto: BLOCK '+m.block,'tag'),0,Qt.AlignmentFlag.AlignLeft)
        p.addWidget(label('Qué podrás hacer aquí','tileTitle'))
        for f in m.features: p.addWidget(label('•  '+f,wrap=True))
        p.addWidget(label('Este módulo todavía no está disponible.','muted',True)); l.addWidget(panel); l.addStretch()
    def make_settings(self):
        l=self.page('settings'); l.addWidget(label('Configuración','heading')); l.addWidget(label('Personaliza tu espacio. Los cambios se guardan en este equipo.','muted',True))
        panel=frame(); p=vertical(panel,(22,22,22,22),10)
        p.addWidget(label('Perfil','tileTitle')); p.addWidget(label('Nombre (opcional)'))
        self.name=QLineEdit(); self.name.setPlaceholderText('Tu nombre'); self.name.setMaxLength(50); p.addWidget(self.name)
        p.addWidget(label('Frase de bienvenida')); self.message=QLineEdit(); self.message.setMaxLength(120); p.addWidget(self.message)
        save=button('Guardar cambios','check','primary'); save.clicked.connect(self.save_settings); p.addWidget(save,0,Qt.AlignmentFlag.AlignLeft)
        self.status=label('','muted',True); p.addWidget(self.status); l.addWidget(panel)
        panel2=frame(); p2=vertical(panel2,(22,22,22,22),10); p2.addWidget(label('Almacenamiento local','tileTitle'))
        p2.addWidget(label(str(self.storage.directory),'muted',True)); op=button('Abrir carpeta de datos','folder'); op.clicked.connect(self.open_data); p2.addWidget(op,0,Qt.AlignmentFlag.AlignLeft); l.addWidget(panel2)
        panel3=frame(); p3=vertical(panel3,(22,22,22,22),10); p3.addWidget(label('Acerca de Ágora','tileTitle')); p3.addWidget(label(f'Versión {VERSION} · BLOCK {BLOCK}\nCorrector manual y automático con importación PDF/Word, QR y lector óptico de plantilla A/B/C.',wrap=True)); l.addWidget(panel3); l.addStretch()
    def load_settings(self):
        self.name.setText(self.storage.get('student_name')); self.message.setText(self.storage.get('welcome_message')); self.status.setText('')
    def save_settings(self):
        try:
            self.storage.save({'student_name':self.name.text().strip(),'welcome_message':self.message.text().strip()}); self.status.setText('Cambios guardados correctamente.'); self.refresh_home()
        except Exception as e: QMessageBox.warning(self,'No se pudo guardar',str(e))
    def open_data(self):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.storage.directory.resolve()))): QMessageBox.warning(self,'Ágora','No se pudo abrir la carpeta de datos.')
