import unittest,tempfile
from dataclasses import replace
from agora.models import Model,ModelLibrary,PRESETS,layout,pdf_bytes,identifier
from pypdf import PdfReader
from io import BytesIO

class ModelTests(unittest.TestCase):
    def test_presets_and_page_count(self):
        for m in PRESETS:
            pdf=PdfReader(BytesIO(pdf_bytes(m))); pages=layout(m)
            self.assertEqual(len(pdf.pages),len(pages)); self.assertTrue(all('HOJA DE RESPUESTAS' in p.extract_text() for p in pdf.pages))
        pages=layout(PRESETS[0]); self.assertEqual(len(pages),2); self.assertEqual([len(b['rows']) for b in pages[0]['blocks']],[30]*4)
    def test_all_numbers_and_geometry(self):
        for m in (Model(),Model(questions=500,reserves=100,options=5,columns=4,size=8,margin=22,notes=True),Model(questions=80,reserves=10,options=4,shape='oval',orientation='landscape',separate=True,header=False,logo=False,notes=True)):
            actual=[]
            for p in layout(m):
                for b in p['blocks']:
                    for r in b['rows']:
                        actual.append(r['number']); self.assertEqual(len(r['centers']),m.options)
                        self.assertGreaterEqual(r['y']-p['cell']/2,p['bottom']); self.assertLess(r['y']+p['cell']/2,p['top'])
                        for cx in r['centers']: self.assertGreater(cx-p['cell']/2,b['x']); self.assertLess(cx+p['cell']/2,b['x']+b['width'])
            self.assertEqual(actual,[str(i) for i in range(1,m.questions+1)]+[f'R{i}' for i in range(1,m.reserves+1)])
            self.assertEqual(len(PdfReader(BytesIO(pdf_bytes(m))).pages),len(layout(m)))
    def test_model_library_roundtrip_and_rename(self):
        with tempfile.TemporaryDirectory() as d:
            lib=ModelLibrary(d); m=PRESETS[1]; a=lib.save(m); b=lib.save(PRESETS[2]); renamed=replace(m,name='Nuevo nombre'); lib.save(renamed,a)
            self.assertEqual(dict((i,m) for i,m,_ in ModelLibrary(d).entries())[a],renamed); self.assertEqual(identifier(renamed),identifier(m)); lib.delete(b); self.assertEqual(len(lib.entries()),1)
    def test_invalid(self):
        for args in ({'options':6},{'questions':0},{'color':'blue'},{'name':' '},{'size':10}):
            with self.assertRaises(ValueError): Model(**args)
    def test_render_pdf(self):
        import pypdfium2 as pdfium
        doc=pdfium.PdfDocument(pdf_bytes(PRESETS[0])); page=doc[0]; bitmap=page.render(scale=1)
        try: self.assertGreater(bitmap.width,500); self.assertGreater(bitmap.height,800)
        finally: bitmap.close(); page.close(); doc.close()
    def test_color_names_and_empty_observations(self):
        from agora.models import color_name
        self.assertEqual(color_name('#a55379'),'Rosa Ágora')
        self.assertEqual(color_name('#7034A5'),'Morado amatista')
        self.assertEqual(color_name('#F8F5EC'),'Blanco roto')
        self.assertNotIn('#',color_name('#123456'))
        # The inside of the notes rectangle is white: no diagonal or ruled lines.
        import pypdfium2 as pdfium
        from reportlab.lib.units import mm
        m=replace(PRESETS[0],notes=True); geometry=layout(m)[0]
        doc=pdfium.PdfDocument(pdf_bytes(m)); page=doc[0]; bitmap=page.render(scale=2)
        try:
            im=bitmap.to_pil().convert('RGB'); ma=geometry['margin']; h=geometry['height']; w=geometry['width']
            crop=im.crop((int((ma+mm)*2),int((h-ma-36*mm)*2),int((w-ma-mm)*2),int((h-ma-20*mm)*2)))
            self.assertEqual(crop.getextrema(),((255,255),(255,255),(255,255)))
        finally: bitmap.close(); page.close(); doc.close()
