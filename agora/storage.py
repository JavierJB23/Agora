"""SQLite local; sin datos de estudio ficticios ni dependencia de la interfaz."""
from pathlib import Path
import os
import sqlite3
from contextlib import contextmanager

DEFAULTS = {'student_name': '', 'welcome_message': 'Aprende. Comprende. Avanza.'}
SCHEMA_VERSION = 1

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
