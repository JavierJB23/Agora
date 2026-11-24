import sqlite3
import tempfile
import unittest
from pathlib import Path
from agora.storage import Storage, DEFAULTS
from agora.modules import MODULES

class StorageTests(unittest.TestCase):
    def test_initialization(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d)
            self.assertTrue(s.path.exists())
            for k,v in DEFAULTS.items(): self.assertEqual(s.get(k),v)
    def test_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            Storage(d).save({'student_name':'Lucía','welcome_message':'¡Ánimo!'})
            s=Storage(d); self.assertEqual(s.get('student_name'),'Lucía'); self.assertEqual(s.get('welcome_message'),'¡Ánimo!')
    def test_reject_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d)
            with self.assertRaises(ValueError): s.save({'student_name':'x','invalid':'x'})
            self.assertEqual(s.get('student_name'),'')
    def test_future_db_not_downgraded(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d)
            with sqlite3.connect(s.path) as db: db.execute('PRAGMA user_version=2')
            with self.assertRaises(RuntimeError): Storage(d)
    def test_module_registry(self):
        self.assertEqual(len(MODULES),8)
        self.assertEqual(len({m.key for m in MODULES}),8)
        for m in MODULES: self.assertTrue((Path(__file__).resolve().parents[1]/'assets'/f'{m.icon}.svg').exists())
