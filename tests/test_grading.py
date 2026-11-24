import unittest
from fractions import Fraction
from agora.grading import ExamConfig,evaluate,format_number

class GradingTests(unittest.TestCase):
    def config(self,n=4,r=0,**kw): return ExamConfig(questions=n,reserves=r,**kw)
    def test_all_correct(self):
        r=evaluate(self.config(),list('ABCA'),list('ABCA'))
        self.assertEqual((r.correct,r.wrong,r.blank,r.grade),(4,0,0,10))
    def test_mixed(self):
        r=evaluate(self.config(),list('ABCA'),list('AC-A'))
        self.assertEqual((r.correct,r.wrong,r.blank,r.net,r.grade),(2,1,1,Fraction(5,3),Fraction(25,6)))
        self.assertEqual(format_number(r.grade),'4,17')
    def test_real_size_example(self):
        r=evaluate(self.config(107),['A']*107,['A']*74+['B']*33)
        self.assertEqual((r.correct,r.wrong,r.net),(74,33,63)); self.assertEqual(format_number(r.grade),'5,89')
    def test_blank(self): self.assertEqual(evaluate(self.config(),list('ABCA'),list('----')).grade,0)
    def test_negative_and_floor(self):
        self.assertEqual(evaluate(self.config(2),['A']*2,['B']*2).grade,Fraction(-10,3))
        r=evaluate(self.config(2,floor_zero=True),['A']*2,['B']*2)
        self.assertEqual(r.grade,0); self.assertEqual(r.raw_grade,Fraction(-10,3))
    def test_unused_reserves(self):
        r=evaluate(self.config(2,2),list('ABCA'),list('ABBB'))
        self.assertEqual((r.grade,r.reserve_used,r.effective),(10,0,2)); self.assertEqual(r.rows[2].status,'Reserva no utilizada')
    def test_replacement_order(self):
        r=evaluate(self.config(4,3),list('XBXAXBC'),list('ABAAABC'))
        self.assertEqual((r.annulled,r.reserve_used,r.effective,r.correct),(2,2,4,4))
        self.assertEqual((r.rows[5].replaces,r.rows[6].replaces),('1','3'))
        self.assertEqual(r.rows[4].status,'Reserva anulada')
    def test_insufficient_reserves(self):
        r=evaluate(self.config(3,1),list('XXAB'),list('AAAB'))
        self.assertEqual((r.annulled,r.reserve_used,r.effective,r.grade),(2,1,2,10))
    def test_no_evaluable(self): self.assertIsNone(evaluate(self.config(2),['X','X'],['-','-']).grade)
    def test_five_options_custom_scoring(self):
        r=evaluate(self.config(2,options=5,penalty='0.25',maximum='50'),list('ED'),list('EC'))
        self.assertEqual(r.grade,Fraction(75,4))
    def test_zero_penalty(self): self.assertEqual(evaluate(self.config(2,penalty='0'),list('AB'),list('AC')).grade,5)
    def test_invalid_config(self):
        for kw in ({'questions':0},{'options':6},{'reserves':-1},{'penalty':'1/0'},{'penalty':'-1'},{'maximum':'0'},{'name':' '},{'penalty':'1e999999999'}):
            with self.subTest(kw=kw),self.assertRaises(ValueError): ExamConfig(**kw)
    def test_invalid_entries(self):
        for k,a in [('A','A'),('ABCA','ABCCX'),('ABCA','ABCX'),('ABCA','ABC'),('ABC','ABCA'),('ABCD','ABCA'),('ABCA',['A','B','C','']),(['A','B','C',''],'ABCA')]:
            with self.subTest(k=k,a=a),self.assertRaises(ValueError): evaluate(self.config(),k,a)
    def test_precision_and_rounding(self):
        self.assertEqual(format_number(Fraction(1,200)),'0,01'); self.assertEqual(format_number(Fraction(-1,200)),'-0,01'); self.assertEqual(format_number(Fraction(-1,1000)),'0,00')
    def test_large_exam(self):
        c=self.config(500,100,options=5); r=evaluate(c,['A']*600,['A']*600)
        self.assertEqual((r.correct,r.grade,len(r.rows)),(500,10,600))
