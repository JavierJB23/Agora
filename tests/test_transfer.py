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
