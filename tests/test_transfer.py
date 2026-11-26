import unittest
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from agora.transfer import UploadSession

class TransferTests(unittest.TestCase):
    def test_upload_once_and_token(self):
        s=UploadSession(host='127.0.0.1'); url=s.url('127.0.0.1')
        try:
            with urlopen(url,timeout=3) as r: self.assertIn('Enviar documento',r.read().decode())
            with self.assertRaises(HTTPError) as e: urlopen(url.replace(s.token,'wrong'),timeout=3)
            self.assertEqual(e.exception.code,404)
            with self.assertRaises(HTTPError) as e: urlopen(Request(url+'upload',data=b'abc',headers={'X-File-Name':'test.exe'}),timeout=3)
            self.assertEqual(e.exception.code,415)
            req=Request(url+'upload',data=b'example',headers={'X-File-Name':'soluciones.pdf'})
            with urlopen(req,timeout=3) as r: self.assertEqual(r.status,200)
            self.assertEqual(s.items.get(timeout=1),('soluciones.pdf',b'example'))
            with self.assertRaises(HTTPError) as e: urlopen(req,timeout=3)
            self.assertEqual(e.exception.code,409)
        finally: s.close()

    def test_limit_and_browser_agree(self):
        from agora.answer_import import MAX_BYTES
        self.assertEqual(MAX_BYTES,100*1024*1024)
        s=UploadSession(host='127.0.0.1'); url=s.url('127.0.0.1')
        try:
            with urlopen(url,timeout=3) as r: self.assertIn(str(MAX_BYTES),r.read().decode())
            req=Request(url+'upload',data=b'x',headers={'X-File-Name':'test.pdf','Content-Length':str(MAX_BYTES+1)})
            with self.assertRaises(HTTPError) as e: urlopen(req,timeout=3)
            self.assertEqual(e.exception.code,413)
        finally: s.close()

    def test_transfer_above_previous_limit(self):
        s=UploadSession(host='127.0.0.1'); url=s.url('127.0.0.1'); data=b'x'*(26*1024*1024)
        try:
            req=Request(url+'upload',data=data,headers={'X-File-Name':'grande.pdf'})
            with urlopen(req,timeout=10) as r: self.assertEqual(r.status,200)
            name,received=s.items.get(timeout=1); self.assertEqual(name,'grande.pdf'); self.assertEqual(received,data)
        finally: s.close()

    def test_batch_two_images_atomic(self):
        import json
        from urllib.parse import quote
        s=UploadSession(host='127.0.0.1',extensions=('.png','.pdf'),multiple=True); url=s.url('127.0.0.1')
        try:
            with urlopen(url,timeout=3) as r: self.assertIn('multiple',r.read().decode())
            def req(files,data): return Request(url+'batch',data=data,headers={'X-Files':quote(json.dumps(files))})
            with self.assertRaises(HTTPError): urlopen(req([['a.png',3],['b.pdf',4]],b'ab'),timeout=3)
            self.assertTrue(s.items.empty())
            with urlopen(req([['reserva.png',3],['principal.pdf',4]],b'abcdefg'),timeout=3) as r: self.assertEqual(r.status,200)
            self.assertEqual(s.items.get(timeout=1),[('reserva.png',b'abc'),('principal.pdf',b'defg')])
            with self.assertRaises(HTTPError) as e: urlopen(req([['a.png',1]],b'x'),timeout=3)
            self.assertEqual(e.exception.code,409)
        finally: s.close()

    def test_mobile_large_file_selector_and_brand(self):
        for multi in (False,True):
            s=UploadSession(host='127.0.0.1',multiple=multi); url=s.url('127.0.0.1')
            try:
                with urlopen(url,timeout=3) as r: page=r.read().decode()
                self.assertIn('class="pick"',page); self.assertIn('Seleccionar archivos',page); self.assertIn('<svg ',page); self.assertIn('padding:14px;width:100%;font:inherit',page); self.assertIn('id="file"',page)
                self.assertEqual('type="file" multiple' in page,multi)
            finally: s.close()
