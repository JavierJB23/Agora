"""SQLite local; sin datos de estudio ficticios ni dependencia de la interfaz."""
from pathlib import Path
import os
import sqlite3
import json
from contextlib import contextmanager

DEFAULTS = {'student_name': '', 'welcome_message': 'Aprende. Comprende. Avanza.'}
SCHEMA_VERSION = 5

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
            db.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
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


    def save_template(self, name, payload):
        with self.connection() as db:
            db.execute('INSERT INTO manual_templates(name,payload) VALUES (?,?)',(name,json.dumps(payload,ensure_ascii=False)))

    def templates(self):
        with self.connection() as db:
            rows=db.execute('SELECT id,name,payload FROM manual_templates ORDER BY id DESC').fetchall()
        return [(i,n,json.loads(p)) for i,n,p in rows]

    def delete_template(self, template_id):
        with self.connection() as db: db.execute('DELETE FROM manual_templates WHERE id=?',(template_id,))

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
