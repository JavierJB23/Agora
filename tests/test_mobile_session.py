import json,time,unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import quote
from agora.mobile_session import MobileSession

class MobileSessionTests(unittest.TestCase):
    def setUp(self):
        self.s=MobileSession('127.0.0.1'); self.addCleanup(self.s.close); self.url=self.s.url('127.0.0.1')
    def status(self):
        with urlopen(self.url+'status',timeout=3) as r: return json.load(r)
    def send(self,token,files):
        req=Request(self.url+'batch',data=b''.join(data for _,data in files),headers={'X-Destination':token,'X-Files':quote(json.dumps([[n,len(d)] for n,d in files]))})
        with urlopen(req,timeout=3) as r: return r.status
    def test_reuse_across_destinations_and_countdown(self):
        deadline=self.s.deadline
        self.s.set_route(('one','Respuestas',('.jpg',),20))
        self.assertEqual(self.status()['token'],'one')
        self.assertEqual(self.send('one',[('a.jpg',b'abc'),('b.jpg',b'def')]),200)
        self.assertEqual(self.s.items.get(timeout=1),('one',[('a.jpg',b'abc'),('b.jpg',b'def')]))
        self.s.set_route(('two','Mis plantillas',('.pdf','.docx'),20))
        self.assertEqual(self.status()['label'],'Mis plantillas')
        self.assertEqual(self.send('two',[('plantilla.pdf',b'pdf')]),200)
        self.assertEqual(self.s.items.get(timeout=1),('two',[('plantilla.pdf',b'pdf')]))
        self.assertEqual(self.s.deadline,deadline); self.assertGreater(self.status()['remaining'],0)
        with urlopen(self.url,timeout=3) as r:
            page=r.read().decode(); self.assertIn('Tiempo agotado',page); self.assertNotIn('Puedes enviar más',page); self.assertIn('X-Destination',page)
    def test_wrong_screen_and_wrong_format(self):
        self.assertIsNone(self.status()['token'])
        with self.assertRaises(HTTPError) as e: self.send('old',[('a.pdf',b'a')])
        self.assertEqual(e.exception.code,409)
        self.s.set_route(('new','Soluciones',('.pdf',),1))
        for token,files,code in [('old',[('a.pdf',b'a')],409),('new',[('a.jpg',b'a')],400),('new',[('a.pdf',b'a'),('b.pdf',b'b')],400)]:
            with self.assertRaises(HTTPError) as e: self.send(token,files)
            self.assertEqual(e.exception.code,code)
        self.assertTrue(self.s.items.empty())
        self.assertEqual(self.send('new',[('a.pdf',b'a')]),200)
        with self.assertRaises(HTTPError) as e: self.send('new',[('b.pdf',b'b')])
        self.assertEqual(e.exception.code,409)
    def test_expiry(self):
        self.s.set_route(('one','Respuestas',('.jpg',),20)); self.s.deadline=time.monotonic()-1
        self.assertIsNone(self.status()['token']); self.assertEqual(self.status()['state'],'expired')
        with self.assertRaises(HTTPError) as e: self.send('one',[('a.jpg',b'a')])
        self.assertEqual(e.exception.code,410)
    def test_changed_destination_while_uploading(self):
        import http.client, threading
        self.s.set_route(('one','Respuestas',('.jpg',),20))
        c=http.client.HTTPConnection('127.0.0.1',self.s.server.server_port,timeout=4)
        try:
            c.putrequest('POST','/'+self.s.token+'/batch'); c.putheader('Content-Length','4'); c.putheader('X-Destination','one'); c.putheader('X-Files',quote(json.dumps([['a.jpg',4]]))); c.endheaders(); c.send(b'a')
            until=time.monotonic()+2
            while not self.s.receiving and time.monotonic()<until: time.sleep(.01)
            self.assertTrue(self.s.receiving)
            self.s.set_route(('two','Mis plantillas',('.pdf',),20)); c.send(b'bcd')
            r=c.getresponse(); self.assertEqual(r.status,409); r.read(); self.assertTrue(self.s.items.empty())
        finally: c.close()

    def test_disconnect_reports_terminal_state_and_blocks_upload(self):
        self.s.set_route(('one','Respuestas',('.jpg',),20)); self.s.retire()
        v=self.status(); self.assertEqual(v['state'],'disconnected'); self.assertEqual(v['remaining'],0); self.assertIsNone(v['token'])
        with self.assertRaises(HTTPError) as e: self.send('one',[('a.jpg',b'a')])
        self.assertEqual(e.exception.code,410); self.assertTrue(self.s.items.empty())
