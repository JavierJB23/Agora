import unittest,tempfile,json
from dataclasses import asdict
from agora.storage import Storage
from agora.grading import ExamConfig
from agora.transfer import UploadSession
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from urllib.parse import quote

class LibraryTests(unittest.TestCase):
    def payload(self,key=('A','B','X'),questions=2,reserves=1,ref=None):
        return {'config':asdict(ExamConfig(questions=questions,reserves=reserves)),'key':list(key),'document_ref':ref}
    def test_linked_and_legacy_entries(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); ref=s.archive_solution_document('A.pdf',b'original'); tid=s.save_template('Zeta',self.payload(ref=ref)); s.save_template('Alfa',self.payload(('C','B','X')))
            self.assertEqual(len(s.library_entries()),2); self.assertEqual([x['name'] for x in s.library_entries('az')],['Alfa','Zeta']); self.assertEqual([x['name'] for x in s.library_entries('za')],['Zeta','Alfa']); self.assertEqual([x['name'] for x in s.library_entries('old')],['Zeta','Alfa']); self.assertEqual([x['name'] for x in s.library_entries('new')],['Alfa','Zeta'])
            e=next(x for x in s.library_entries() if x['id']==tid); self.assertEqual(e['size'],8); self.assertTrue(e['created']); self.assertEqual(s.load_solution_document(e['ref']),('A.pdf',b'original'))
    def test_duplicate_pattern_and_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); p=self.payload(); tid=s.save_template('Primera',p); s.save_template('Otra distribución',self.payload(questions=3,reserves=0)); aid=s.save_attempt(dict(p,answers=['A','B','-']))
            q=dict(p,config=dict(p['config'],penalty='0',options=4)); self.assertEqual([r[0] for r in s.matching_templates(q)],[tid]); self.assertEqual(s.save_template('Renombrada',q,replace_id=tid),tid); self.assertEqual(s.load_attempt(aid)['key'],p['key']); self.assertEqual(len(s.templates()),2)
    def test_migration_keeps_unknown_dates(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); s.save_template('Anterior',self.payload()); ref=s.archive_solution_document('old.pdf',b'old')
            with s.connection() as db:
                db.execute('UPDATE manual_templates SET created=NULL'); db.execute('UPDATE solution_documents SET created=NULL'); db.execute('PRAGMA user_version=6')
            s=Storage(d); self.assertEqual(len(s.library_entries()),2); self.assertTrue(all(x['created'] is None for x in s.library_entries())); self.assertEqual(s.load_solution_document(ref),('old.pdf',b'old'))
    def test_deleted_template_original_preserved_not_relisted(self):
        with tempfile.TemporaryDirectory() as d:
            s=Storage(d); ref=s.archive_solution_document('A.pdf',b'original'); tid=s.save_template('A',self.payload(ref=ref)); s.delete_template(tid)
            self.assertEqual(s.library_entries(),[]); self.assertEqual(s.load_solution_document(ref),('A.pdf',b'original'))
            s.archive_solution_document('A.pdf',b'original'); self.assertEqual(len(s.library_entries()),1)
    def test_batch_library_limit(self):
        s=UploadSession(host='127.0.0.1',multiple=True,max_files=20); url=s.url('127.0.0.1')
        try:
            with urlopen(url,timeout=3) as r: self.assertIn('files.length>20',r.read().decode())
            files=[[f'{i}.pdf',1] for i in range(21)]
            def req(f): return Request(url+'batch',data=b'x'*len(f),headers={'X-Files':quote(json.dumps(f))})
            with self.assertRaises(HTTPError): urlopen(req(files),timeout=3)
            self.assertTrue(s.items.empty())
            with urlopen(req(files[:4]),timeout=3) as r: self.assertEqual(r.status,200)
            self.assertEqual(len(s.items.get(timeout=1)),4)
        finally: s.close()
