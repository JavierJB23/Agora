import sqlite3
from contextlib import closing
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
            with closing(sqlite3.connect(s.path)) as db:
                with db:
                    db.execute('PRAGMA user_version=99')
            with self.assertRaises(RuntimeError): Storage(d)
            with closing(sqlite3.connect(s.path)) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 99)
    def test_module_registry(self):
        self.assertEqual(len(MODULES),8)
        self.assertEqual(len({m.key for m in MODULES}),8)
        for m in MODULES: self.assertTrue((Path(__file__).resolve().parents[1]/'assets'/f'{m.icon}.svg').exists())

class ManualStorageTests(unittest.TestCase):
    def test_upgrade_from_block01(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'agora.sqlite3'
            with closing(sqlite3.connect(path)) as db:
                with db:
                    db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
                    db.execute('INSERT INTO settings VALUES (?,?)',('student_name','Perfil anterior'))
                    db.execute('PRAGMA user_version=1')
            s=Storage(d); self.assertEqual(s.get('student_name'),'Perfil anterior')
            with s.connection() as db: self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],3)
    def test_draft_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); self.assertIsNone(s.load_draft()); s.save_draft({'key':['A','X'],'answers':['','-']}); self.assertEqual(Storage(d).load_draft()['key'],['A','X']); s.clear_draft(); self.assertIsNone(s.load_draft())
    def test_templates_independent(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); s.save_template('Tema 1',{'key':['A']}); s.save_template('Tema 2',{'key':['B']}); s.save_draft({'key':['C']}); s.clear_draft()
            t=Storage(d).templates(); self.assertEqual([x[1] for x in t],['Tema 2','Tema 1']); s.delete_template(t[0][0]); self.assertEqual(len(s.templates()),1)

    def test_saved_attempts_are_independent_of_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); a=s.save_attempt({'answers':['A']}); s.save_draft({'answers':['B'],'attempt_id':a}); s.clear_draft()
            self.assertEqual(s.load_attempt(a)['answers'],['A']); self.assertIsNone(s.load_draft())
            s.save_attempt({'answers':['C']},a); self.assertEqual(s.load_attempt(a)['answers'],['C']); self.assertEqual(len(s.attempts()),1)
            b=s.save_attempt({'answers':['D']}); self.assertNotEqual(a,b); self.assertEqual(len(s.attempts()),2)
    def test_upgrade_from_schema2_preserves_data(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); s.save_template('Anterior',{'key':['A']}); s.save_draft({'key':['B']})
            with s.connection() as db:
                db.execute('DROP TABLE saved_attempts'); db.execute('PRAGMA user_version=2')
            s=Storage(d); self.assertEqual(s.load_draft()['key'],['B']); self.assertEqual(s.templates()[0][1],'Anterior'); self.assertEqual(s.attempts(),[])
