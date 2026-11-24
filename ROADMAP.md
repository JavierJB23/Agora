# Ágora — hoja de ruta acordada

Desarrollo incremental por bloques; mantener la última versión STABLE y no avanzar sin aprobación. Windows, Python/PySide6/SQLite, estética rosa pastel y blanco. Primera versión funcional del corrector: fin de BLOCK 06.

1. Interfaz, arquitectura, menú y configuración local. STABLE visual: FIX03, marca ÁGORA clásica y ocho botones 4×2.
2. Corrector manual (v0.2.0 RC1, pendiente de Windows): número de preguntas y opciones configurables, reservas, anulaciones, blancos, puntuación configurable, plantilla manual y navegación rápida. No contar casillas fuera del examen como blancas.
3. Importador universal: **toda** importación presente o futura ofrece ordenador (selección y arrastre) o móvil (QR, red local, selección múltiple, fotografías, progreso, sin nube). Seguridad: token temporal, límites de tamaño, validación de tipo, cerrar servidor al terminar.
4. Extracción de soluciones: texto de PDF, documento independiente o soluciones al final del examen, numeración de reserva diferenciada y revisión editable; OCR para imágenes cuando necesario.
5. OMR: hoja real de 120 ordinarias + 9 reservas y A/B/C, alineación de perspectiva, marcas azules y rojas separadas, ignorar resaltado verde, advertir ambigüedades; prueba con foto original sin correcciones y con correcciones. No inferir automáticamente respuestas dudosas ni asumir que el rojo representa respuesta original.
6. Revisión visual editable de respuestas y corrección automática. Verificar contra datos manuales antes de aprobar.
7. Historial y exportación.
8. Estadísticas.
9. Biblioteca de PDF y Word, indexación de temas.
10. Extracción de enunciados, opciones y explicaciones existentes.
11. Vinculación con temario, referencias comprobables y explicación; no inventar fuentes. IA local/API a evaluar, no requerida para el corrector.
12. Banco de errores y repaso.
13. Planificación y repasos espaciados (propuesta futura).

Materiales de prueba externos: plantilla en blanco y corregida, S24 enunciados, respondido y soluciones, test de temas 56–59 y cuatro DOCX. No distribuirlos con el software. Antes de fijar penalización, confirmar fórmula exacta: no asumir que el ejemplo corregido establece una regla universal.
