"""SQLite local; sin datos de estudio ficticios ni dependencia de la interfaz."""
from pathlib import Path
import os
import sqlite3
import json
from contextlib import contextmanager

DEFAULTS = {'student_name': '', 'welcome_message': 'Aprende. Comprende. Avanza.'}
SCHEMA_VERSION = 8

def default_data_dir():
    override = os.environ.get('AGORA_DATA_DIR')
    if override:
        return Path(override).expanduser()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'Agora'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'Agora'

class Storage:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else default_data_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'agora.sqlite3'
        with self.connection() as db:
            v = db.execute('PRAGMA user_version').fetchone()[0]
            if v > SCHEMA_VERSION:
                raise RuntimeError('La base de datos pertenece a una versión más reciente de Ágora.')
            db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.executemany('INSERT OR IGNORE INTO settings VALUES (?, ?)', DEFAULTS.items())
            db.execute('CREATE TABLE IF NOT EXISTS manual_draft (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS automatic_draft (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS manual_templates (id INTEGER PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS saved_attempts (id INTEGER PRIMARY KEY, updated TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS optical_pages (id TEXT PRIMARY KEY, original BLOB NOT NULL, aligned BLOB NOT NULL, marks TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS solution_documents (id TEXT PRIMARY KEY, name TEXT NOT NULL, data BLOB NOT NULL)')
            for table in ('manual_templates','solution_documents'):
                if 'created' not in {r[1] for r in db.execute(f'PRAGMA table_info({table})')}:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN created TEXT')
            if 'listed' not in {r[1] for r in db.execute('PRAGMA table_info(solution_documents)')}:
                db.execute('ALTER TABLE solution_documents ADD COLUMN listed INTEGER NOT NULL DEFAULT 1')
            if v==6: self._migrate_library(db)
            # Never recycle template IDs: old snapshots may still reference a deleted ID.
            db.execute('CREATE TABLE IF NOT EXISTS template_sequence (id INTEGER PRIMARY KEY CHECK(id=1), last_id INTEGER NOT NULL)')
            high=db.execute('SELECT COALESCE(MAX(id),0) FROM manual_templates').fetchone()[0]
            for table in ('saved_attempts','manual_draft','automatic_draft'):
                for (raw,) in db.execute(f'SELECT payload FROM {table}'):
                    tid=json.loads(raw).get('template_id')
                    if isinstance(tid,int): high=max(high,tid)
            db.execute('INSERT INTO template_sequence VALUES (1,?) ON CONFLICT(id) DO UPDATE SET last_id=MAX(last_id,excluded.last_id)',(high,))
            if v<8: self._detach_stale_template_links(db)
            db.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
    @staticmethod
    def _detach_stale_template_links(db):
        # Older schemas recycled IDs. Preserve attempts, but detach missing or clearly
        # incompatible links rather than risk deleting unrelated historical records.
        templates={i:json.loads(raw) for i,raw in db.execute('SELECT id,payload FROM manual_templates')}
        for table in ('saved_attempts','manual_draft','automatic_draft'):
            for i,raw in db.execute(f'SELECT id,payload FROM {table}').fetchall():
                d=json.loads(raw); tid=d.get('template_id')
                if tid is None: continue
                p=templates.get(tid)
                a=Storage.template_pattern(d); b=Storage.template_pattern(p) if p is not None else None
                same_doc=bool(p and d.get('document_ref') and d['document_ref']==p.get('document_ref'))
                if p is None or (a is not None and b is not None and a!=b and not same_doc):
                    d.pop('template_id',None)
                    db.execute(f'UPDATE {table} SET payload=? WHERE id=?',(json.dumps(d,ensure_ascii=False),i))
    @staticmethod
    def _migrate_library(db):
        # v6 stored originals separately. Only reconnect explicitly named templates.
        from dataclasses import asdict
        from .answer_import import extract_key
        from .grading import ExamConfig
        rows=[(tid,name,json.loads(p)) for tid,name,p in db.execute('SELECT id,name,payload FROM manual_templates')]
        linked={p.get('document_ref') for _,_,p in rows}
        for ref,name,data in db.execute('SELECT id,name,data FROM solution_documents').fetchall():
            if ref in linked: continue
            try:
                k=extract_key(data,name)
                c=ExamConfig(name=Path(name).stem[:120] or 'Plantilla',questions=len(k.ordinary),reserves=len(k.reserves),options=max(3,k.options))
                p={'config':asdict(c),'key':k.key,'key_source':name,'document_ref':ref}
            except Exception:
                continue  # keep the original available for consultation / later registration
            matching=[(tid,d) for tid,_,d in rows if not d.get('document_ref') and d.get('key_source')==name and Storage.template_pattern(d)==Storage.template_pattern(p)]
            if len(matching)==1:
                tid,d=matching[0]; d['document_ref']=ref
                db.execute('UPDATE manual_templates SET payload=? WHERE id=?',(json.dumps(d,ensure_ascii=False),tid)); continue

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            db.execute('PRAGMA foreign_keys = ON')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    def get(self, key):
        with self.connection() as db:
            row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else DEFAULTS.get(key, '')
    def save(self, values):
        if not set(values) <= DEFAULTS.keys():
            raise ValueError('Ajuste desconocido')
        with self.connection() as db:
            db.executemany('INSERT INTO settings VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', values.items())

    def load_draft(self, mode="manual"):
        table = self.draft_table(mode)
        with self.connection() as db:
            row=db.execute(f'SELECT payload FROM {table} WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None

    def save_draft(self, payload, mode="manual", pages=()):
        table = self.draft_table(mode)
        with self.connection() as db:
            old=db.execute(f'SELECT payload FROM {table} WHERE id=1').fetchone()
            self._store_pages(db,pages,payload)
            db.execute(f'INSERT INTO {table} VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (json.dumps(payload,ensure_ascii=False),))
            if old and json.loads(old[0]).get('optical_pages',{})!=payload.get('optical_pages',{}): self._prune_pages(db)

    def clear_draft(self, mode="manual"):
        table=self.draft_table(mode)
        with self.connection() as db:
            db.execute(f'DELETE FROM {table} WHERE id=1')
            self._prune_pages(db)

    @staticmethod
    def draft_table(mode):
        if mode not in ('manual','automatic'): raise ValueError('Modo no válido')
        return mode+'_draft'


    def archive_solution_document(self, name, data):
        """Keep original bytes for an attempt; never register a library template."""
        from hashlib import sha256
        suffix=Path(name).suffix.lower()
        if suffix not in ('.pdf','.docx') or not data or len(data)>100*1024*1024:
            raise ValueError('Documento de soluciones no válido.')
        ref=sha256(suffix.encode()+b'\0'+data).hexdigest()
        with self.connection() as db:
            db.execute('INSERT OR IGNORE INTO solution_documents(id,name,data,created) VALUES (?,?,?,?)',(ref,Path(name).name,data,self.timestamp()))
        return ref

    def solution_documents(self):
        with self.connection() as db:
            return db.execute('SELECT id,name,length(data) FROM solution_documents ORDER BY rowid DESC').fetchall()

    def load_solution_document(self, ref):
        with self.connection() as db:
            row=db.execute('SELECT name,data FROM solution_documents WHERE id=?',(ref,)).fetchone()
        if row is None: raise ValueError('No se conserva el documento original de esta plantilla.')
        return row

    @staticmethod
    def timestamp():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec='microseconds')

    def save_template(self, name, payload, replace_id=None):
        name=name.strip()
        if not name or len(name)>120: raise ValueError('Introduce un nombre de hasta 120 caracteres.')
        with self.connection() as db:
            if replace_id is None:
                db.execute('UPDATE template_sequence SET last_id=last_id+1 WHERE id=1')
                tid=db.execute('SELECT last_id FROM template_sequence WHERE id=1').fetchone()[0]
                db.execute('INSERT INTO manual_templates(id,name,payload,created) VALUES (?,?,?,?)',(tid,name,json.dumps(payload,ensure_ascii=False),self.timestamp()))
                return tid
            previous=db.execute('SELECT payload FROM manual_templates WHERE id=?',(replace_id,)).fetchone()
            cur=db.execute('UPDATE manual_templates SET name=?,payload=? WHERE id=?',(name,json.dumps(payload,ensure_ascii=False),replace_id))
            if cur.rowcount!=1: raise ValueError('Plantilla no encontrada.')
            oldref=json.loads(previous[0]).get('document_ref') if previous else None
            if oldref and oldref!=payload.get('document_ref'): db.execute('UPDATE solution_documents SET listed=0 WHERE id=?',(oldref,))
            return replace_id

    @staticmethod
    def template_pattern(payload):
        c=payload.get('config',{}); k=tuple(payload.get('key',()))
        if not k or not all(k) or c.get('questions',0)+c.get('reserves',0)!=len(k): return None
        return (c['questions'],c.get('reserves',0),k)

    def matching_templates(self,payload):
        signature=self.template_pattern(payload)
        return [r for r in self.templates() if signature is not None and self.template_pattern(r[2])==signature]

    def library_entries(self,order='new'):
        with self.connection() as db:
            docs={r[0]:r[1:] for r in db.execute('SELECT id,name,length(data),created,listed FROM solution_documents')}
            templates=db.execute('SELECT id,name,payload,created FROM manual_templates').fetchall()
        entries=[]; linked=set()
        for tid,name,raw,stamp in templates:
            payload=json.loads(raw); ref=payload.get('document_ref'); doc=docs.get(ref)
            if doc: linked.add(ref)
            entries.append(dict(id=tid,name=name,payload=payload,ref=ref if doc else None,filename=doc[0] if doc else None,size=doc[1] if doc else None,created=stamp or (doc[2] if doc else None)))
        if order in ('az','za'):
            entries.sort(key=lambda x:x['name'].casefold(),reverse=order=='za')
        else:
            # Unknown legacy dates remain last for either chronology.
            known=[x for x in entries if x['created']]; unknown=[x for x in entries if not x['created']]
            known.sort(key=lambda x:x['created'],reverse=order!='old'); entries=known+unknown
        return entries

    def templates(self):
        with self.connection() as db:
            rows=db.execute('SELECT id,name,payload FROM manual_templates ORDER BY id DESC').fetchall()
        return [(i,n,json.loads(p)) for i,n,p in rows]

    @staticmethod
    def _template_attempts(db, template_id):
        return [(i, (d.get('form') or {}).get('name') or (d.get('config') or {}).get('name') or 'Simulacro sin nombre')
                for i,raw in db.execute('SELECT id,payload FROM saved_attempts')
                if (d:=json.loads(raw)).get('template_id')==template_id]

    def template_attempts(self, template_id):
        with self.connection() as db: return self._template_attempts(db,template_id)

    def delete_template(self, template_id, confirmed_attempts=()):
        """Atomically remove named template and explicitly confirmed dependent attempts."""
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM manual_templates WHERE id=?',(template_id,)).fetchone()
            if row is None: return False
            affected={i for i,_ in self._template_attempts(db,template_id)}
            if affected!=set(confirmed_attempts):
                raise ValueError('Los simulacros vinculados han cambiado. Vuelve a confirmar la eliminación.')
            db.executemany('DELETE FROM saved_attempts WHERE id=?',[(i,) for i in affected])
            for table in ('manual_draft','automatic_draft'):
                r=db.execute(f'SELECT payload FROM {table} WHERE id=1').fetchone()
                if r:
                    d=json.loads(r[0])
                    if d.get('template_id')==template_id or d.get('attempt_id') in affected:
                        db.execute(f'DELETE FROM {table} WHERE id=1')
            db.execute('DELETE FROM manual_templates WHERE id=?',(template_id,))
            self._prune_pages(db)
            return True

    def save_attempt(self, payload, attempt_id=None, pages=()):
        from datetime import datetime, timezone
        stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
        with self.connection() as db:
            if attempt_id is None:
                attempt_id=db.execute('INSERT INTO saved_attempts(updated,payload) VALUES (?,?)',(stamp,'{}')).lastrowid
            record=dict(payload, attempt_id=attempt_id)
            table=self.draft_table(record.get("mode","manual"))
            self._store_pages(db,pages,record)
            encoded=json.dumps(record,ensure_ascii=False)
            cur=db.execute('UPDATE saved_attempts SET updated=?,payload=? WHERE id=?',(stamp,encoded,attempt_id))
            if cur.rowcount!=1: raise ValueError('El simulacro guardado ya no existe.')
            db.execute(f'INSERT INTO {table} VALUES (1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(encoded,))
            self._prune_pages(db)
        return attempt_id

    def attempts(self):
        with self.connection() as db:
            rows=db.execute('SELECT id,updated,payload FROM saved_attempts ORDER BY updated DESC,id DESC').fetchall()
        return [(i,t,json.loads(p)) for i,t,p in rows]

    def load_attempt(self, attempt_id):
        with self.connection() as db:
            row=db.execute('SELECT payload FROM saved_attempts WHERE id=?',(attempt_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def delete_attempt(self, attempt_id):
        """Delete one archived attempt and its linked recovery draft, never other records."""
        with self.connection() as db:
            cur=db.execute('DELETE FROM saved_attempts WHERE id=?',(attempt_id,))
            if cur.rowcount!=1: return False
            for table in ('manual_draft','automatic_draft'):
                row=db.execute(f'SELECT payload FROM {table} WHERE id=1').fetchone()
                if row and json.loads(row[0]).get('attempt_id')==attempt_id:
                    db.execute(f'DELETE FROM {table} WHERE id=1')
            self._prune_pages(db)
            return True

    @staticmethod
    def _store_pages(db,pages,payload):
        # Immutable snapshots; the draft and archived attempt can share an image.
        for record in pages:
            if not db.execute('SELECT 1 FROM optical_pages WHERE id=?',(record[0],)).fetchone():
                db.execute('INSERT INTO optical_pages VALUES (?,?,?,?)',record)
        for ref in payload.get('optical_pages',{}).values():
            if not db.execute('SELECT 1 FROM optical_pages WHERE id=?',(ref,)).fetchone():
                raise ValueError('No se encuentra una imagen del simulacro.')

    def load_optical_page(self,ref):
        with self.connection() as db:
            row=db.execute('SELECT id,original,aligned,marks FROM optical_pages WHERE id=?',(ref,)).fetchone()
        if row is None: raise ValueError('No se encuentra la imagen guardada.')
        return row

    @staticmethod
    def _prune_pages(db):
        # Only delete images no longer referenced by ANY saved attempt or draft.
        refs=set()
        for table in ('manual_draft','automatic_draft','saved_attempts'):
            for (p,) in db.execute(f'SELECT payload FROM {table}'):
                refs.update(json.loads(p).get('optical_pages',{}).values())
        for (ref,) in db.execute('SELECT id FROM optical_pages').fetchall():
            if ref not in refs: db.execute('DELETE FROM optical_pages WHERE id=?',(ref,))
