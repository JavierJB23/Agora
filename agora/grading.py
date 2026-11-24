"""Deterministic exam scoring, independent of Qt and storage."""
from dataclasses import dataclass
import re
from fractions import Fraction
from decimal import Decimal, ROUND_HALF_UP, localcontext

PENALTIES = ('0', '1/4', '1/3', '1/2', '1')

@dataclass(frozen=True)
class ExamConfig:
    name: str = 'Nuevo simulacro'
    questions: int = 120
    reserves: int = 9
    options: int = 3
    penalty: str = '1/3'
    maximum: str = '10'
    floor_zero: bool = False

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name)>120:
            raise ValueError('Introduce un nombre de hasta 120 caracteres.')
        for value, low, high in ((self.questions,1,500),(self.reserves,0,100),(self.options,2,5)):
            if type(value) is not int or not low <= value <= high:
                raise ValueError('Número de preguntas, reservas u opciones no válido.')
        try:
            if any(not isinstance(x,str) or not re.fullmatch(r'[0-9]{1,10}(?:[./][0-9]{1,10})?',x) for x in (self.penalty,self.maximum)): raise ValueError()
            if not 0 <= Fraction(self.penalty) <= 100 or not 0 < Fraction(self.maximum) <= 10000:
                raise ValueError()
        except (ValueError, ZeroDivisionError, TypeError, OverflowError):
            raise ValueError('Penalización entre 0 y 100 y nota máxima entre 0 y 10000 (excluido 0).') from None
        if type(self.floor_zero) is not bool: raise ValueError('Configuración no válida.')

    @property
    def size(self): return self.questions+self.reserves
    @property
    def letters(self): return 'ABCDE'[:self.options]
    def number(self,i): return str(i+1) if i<self.questions else f'R{i-self.questions+1}'

@dataclass(frozen=True)
class Row:
    number: str
    solution: str
    answer: str
    status: str
    replaces: str = ''

@dataclass(frozen=True)
class Result:
    rows: tuple[Row,...]
    correct: int
    wrong: int
    blank: int
    annulled: int
    reserve_used: int
    effective: int
    net: Fraction
    grade: Fraction | None
    raw_grade: Fraction | None


def format_number(value):
    if value is None: return '—'
    value=Fraction(value)
    with localcontext() as ctx:
        ctx.prec=50
        rounded=(Decimal(value.numerator)/Decimal(value.denominator)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    if not rounded: rounded=abs(rounded)
    return f'{rounded:.2f}'.replace('.',',')


def evaluate(config, key, answers):
    if len(key)!=config.size or len(answers)!=config.size:
        raise ValueError('La longitud de la plantilla y las respuestas debe coincidir con el examen.')
    if any(x not in (*config.letters,'X') for x in key):
        raise ValueError('Completa todas las soluciones o márcalas como anuladas.')
    if any(x not in (*config.letters,'-') for x in answers):
        raise ValueError('Hay respuestas pendientes o no válidas.')
    annulled=[i for i in range(config.questions) if key[i]=='X']
    reserves=[i for i in range(config.questions,config.size) if key[i]!='X']
    replacements=dict(zip(reserves,annulled))
    rows=[]; counts={'Acierto':0,'Error':0,'En blanco':0}
    for i,(solution,answer) in enumerate(zip(key,answers)):
        if solution=='X': status='Anulada' if i<config.questions else 'Reserva anulada'
        elif i>=config.questions and i not in replacements: status='Reserva no utilizada'
        else:
            status='En blanco' if answer=='-' else 'Acierto' if answer==solution else 'Error'
            counts[status]+=1
        rows.append(Row(config.number(i),solution,answer,status,config.number(replacements[i]) if i in replacements else ''))
    a,e,b=(counts[s] for s in ('Acierto','Error','En blanco'))
    effective=a+e+b
    net=Fraction(a)-Fraction(config.penalty)*e
    raw=net*Fraction(config.maximum)/effective if effective else None
    grade=max(Fraction(0),raw) if raw is not None and config.floor_zero else raw
    return Result(tuple(rows),a,e,b,len(annulled),len(replacements),effective,net,grade,raw)
