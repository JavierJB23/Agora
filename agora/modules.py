from dataclasses import dataclass

@dataclass(frozen=True)
class Module:
    key: str
    name: str
    icon: str
    description: str
    block: str
    features: tuple[str, ...]

MODULES = (
    Module('automatic','Corrector automático','scan','Importa tu hoja y compara las respuestas.','05–06',('PDF e imágenes desde ordenador o móvil mediante QR.','Lectura de marcas azules, revisión de resultados dudosos y gestión de reservas.','Corrección con una plantilla de soluciones verificada.')),
    Module('manual','Corrector manual','clipboard','Introduce respuestas y calcula tu nota.','02',('Cuestionario configurable y navegación por teclado.','Soluciones importadas desde PC o móvil mediante QR.','Aciertos, errores, blancos, anuladas y penalizaciones.')),
    Module('history','Mis simulacros','history','Consulta y organiza tus exámenes.','03–04 / 07',('Historial local de correcciones.','Consulta y exportación de resultados.')),
    Module('progress','Mi progreso','chart','Conoce tu evolución y tus puntos fuertes.','08',('Gráficas de notas y precisión.','Comparación entre simulacros.')),
    Module('library','Mi temario','book','Tu biblioteca personal de estudio.','09',('Importación de PDF y Word desde PC o móvil.','Organización por temas y apartados.')),
    Module('errors','Repasar errores','checkbook','Comprende y aprende de tus fallos.','10–12',('Vinculación con los enunciados y el temario.','Explicaciones con referencias comprobables.')),
    Module('training','Entrenamiento','brain','Practica con preguntas por temas.','12',('Banco de preguntas y repaso de errores.','Sesiones de práctica personalizadas.')),
    Module('plan','Plan de estudio','calendar','Organiza tus objetivos y repasos.','13',('Planificación personal.','Repasos espaciados.')),
)
