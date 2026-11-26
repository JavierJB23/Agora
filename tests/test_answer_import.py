import unittest, zipfile
from io import BytesIO
from agora.answer_import import extract_key,parse_pages

class ImportTests(unittest.TestCase):
    def test_compact(self):
        self.assertEqual(parse_pages(['1A, 2A, 3C, 4B, 5B, 6C']).key,list('AACBBC'))
    def test_columns_with_reserves(self):
        p='''Respuestas correctas
1. A                       3. C                       5. B
2. B                       4. X                       6. A
                           7. C                    Preguntas de reserva:
                           8. B                       1. C
                                                      2. B'''
        k=parse_pages([p]); self.assertEqual(k.ordinary,tuple('ABCXBACB')); self.assertEqual(k.reserves,tuple('CB'))
    def test_questionnaire(self):
        k=parse_pages(['1. ¿Pregunta?\na) X\nb) Y','Respuestas correctas:\n1 B\n2 C']); self.assertEqual(k.key,['B','C'])
    def test_reserves(self):
        self.assertEqual(parse_pages(['1. A\n2. ANULADA\nPreguntas de reserva:\n1 C']).key,['A','X','C'])
        self.assertEqual(parse_pages(['1A 2B R1C R2A']).reserves,('C','A'))
        self.assertEqual(parse_pages(['1A 2B R-1C R-2A']).reserves,('C','A'))
    def test_missing_and_duplicate_and_prose(self):
        for p in ['1A 3C','1A 1B','1A 2Z','1. A es una respuesta','1A R2B','0A','1A 501B','1. ¿Cuál?','']:
            with self.subTest(p=p),self.assertRaises(ValueError): parse_pages([p])
    def test_docx(self):
        b=BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('word/document.xml','''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Respuestas correctas:</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc></w:tr><w:tr><w:tc><w:p><w:r><w:t>2 B</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>''')
        self.assertEqual(extract_key(b.getvalue(),'test.docx').key,['A','B'])
    def test_invalid_file(self):
        for n in ['image.png','test.doc','test.pdf','test.docx']:
            with self.subTest(n=n),self.assertRaises(Exception): extract_key(b'not a document',n)
