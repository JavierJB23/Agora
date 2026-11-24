# Ágora — hoja de ruta acordada

Desarrollo incremental por bloques; mantener la última versión STABLE y no avanzar sin aprobación. Windows, Python/PySide6/SQLite, estética rosa pastel y blanco. Primera versión funcional del corrector: fin de BLOCK 06.

1. Interfaz, arquitectura, menú y configuración local. STABLE visual: FIX03, marca ÁGORA clásica y ocho botones 4×2.
2. Corrector manual (v0.2.0 RC1 y FIX01 validados por el usuario): número de preguntas y opciones configurables, reservas, anulaciones, blancos, puntuación configurable, plantillas guardadas y navegación rápida. No contar casillas fuera del examen como blancas.
Regla transversal de interfaz: la rueda nunca modifica desplegables cerrados ni valores numéricos; navegación directa por pasos con validación y recálculo de resultados. Guardar plantilla de respuestas = guardar solucionario y configuración, no respuestas personales; consulta de solo lectura.

3. Importador universal (RC1: PC/arrastre/QR de un PDF o DOCX; importación múltiple e imágenes pendientes): **toda** importación presente o futura ofrece ordenador (selección y arrastre) o móvil (QR, red local, selección múltiple, fotografías, progreso, sin nube). Seguridad: token temporal, límites de tamaño, validación de tipo, cerrar servidor al terminar.
4. Extracción de soluciones (RC1 integrado en el corrector manual; automático en BLOCK 06; OCR pendiente): importar obligatoriamente el solucionario PDF/Word (o reutilizar uno ya importado) en ambos correctores; nunca exigir transcribirlo. Leer texto digital, formatos compactos, columnas, documento independiente o soluciones al final del examen, numeración de reserva diferenciada y revisión editable de incidencias; OCR si necesario. Manual = introducir respuestas personales a mano; automático = importar también hoja de respuestas.
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

Norma visual: confirmaciones Sí/No en español; flechas y listas de controles acordes a la estética pastel, sin cambios mediante rueda.
