# BLOCK 06B — RC1 v0.6.17 (pendiente de validación)
FIX16 es el punto estable anterior. RC1 incorpora OCR de números y prefijo R como complemento del OMR, con verificación por secuencia y QR reutilizable. Queda mejorar OCR en reservas pequeñas, letras de opciones, formatos desconocidos y páginas parciales; preservar el lector estable. 06C Mis modelos / generador PDF, 06D modelos externos, 06E reconocimiento combinado siguen pendientes.

# Ágora — hoja de ruta acordada

Desarrollo incremental por bloques; mantener la última versión STABLE y no avanzar sin aprobación. Windows, Python/PySide6/SQLite, estética rosa pastel y blanco. Primera versión funcional del corrector: fin de BLOCK 06.

1. Interfaz, arquitectura, menú y configuración local. STABLE visual: FIX03, marca ÁGORA clásica y ocho botones 4×2.
2. Corrector manual (v0.2.0 RC1 y FIX01 validados por el usuario): número de preguntas y opciones configurables, reservas, anulaciones, blancos, puntuación configurable, plantillas guardadas y navegación rápida. No contar casillas fuera del examen como blancas.
Regla transversal de interfaz: la rueda nunca modifica desplegables cerrados ni valores numéricos; navegación directa por pasos con validación y recálculo de resultados. Guardar plantilla de respuestas = guardar solucionario y configuración, no respuestas personales; consulta de solo lectura.

3. Importador universal (RC1: PC/arrastre/QR de un PDF o DOCX; importación múltiple e imágenes pendientes): **toda** importación presente o futura ofrece ordenador (selección y arrastre) o móvil (QR, red local, selección múltiple, fotografías, progreso, sin nube). Seguridad: token temporal, límites de tamaño, validación de tipo, cerrar servidor al terminar.
4. Extracción de soluciones (RC1 integrado en el corrector manual; automático en BLOCK 06; OCR pendiente): importar obligatoriamente el solucionario PDF/Word (o reutilizar uno ya importado) en ambos correctores; nunca exigir transcribirlo. Leer texto digital, formatos compactos, columnas, documento independiente o soluciones al final del examen, numeración de reserva diferenciada y revisión editable de incidencias; OCR si necesario. Manual = introducir respuestas personales a mano; automático = importar también hoja de respuestas.
5. OMR: hoja real de 120 ordinarias + 9 reservas y A/B/C, alineación de perspectiva, marcas azules y rojas separadas, ignorar resaltado verde, advertir ambigüedades; prueba con foto original sin correcciones y con correcciones. No inferir automáticamente respuestas dudosas ni asumir que el rojo representa respuesta original.
6. Revisión visual editable de respuestas y corrección automática. Verificar contra datos manuales antes de aprobar.
7. Historial y exportación. Adelantado en BLOCK 03–04 FIX01: guardar progreso explícitamente, lista básica de simulacros en curso/finalizados, abrirlos y avisos de salida/reanudación. Pendiente organización avanzada, exportación y compatibilidad con el corrector automático cuando exista.
8. Estadísticas.
9. Biblioteca de PDF y Word, indexación de temas.
10. Extracción de enunciados, opciones y explicaciones existentes.
11. Vinculación con temario, referencias comprobables y explicación; no inventar fuentes. IA local/API a evaluar, no requerida para el corrector.
12. Banco de errores y repaso.
13. Planificación y repasos espaciados (propuesta futura).

Materiales de prueba externos: plantilla en blanco y corregida, S24 enunciados, respondido y soluciones, test de temas 56–59 y cuatro DOCX. No distribuirlos con el software. Antes de fijar penalización, confirmar fórmula exacta: no asumir que el ejemplo corregido establece una regla universal.

Norma visual: confirmaciones Sí/No en español; flechas y listas de controles acordes a la estética pastel, sin cambios mediante rueda.

FIX01 de BLOCK 03–04: importación en dos tarjetas con iconos y pantalla QR separada; cancelar centrado, URL oculta, IP solo para diagnóstico, límite 100 MiB por documento. Guardado explícito de simulacros independiente del borrador automático de recuperación; aviso al salir con cambios y al volver a entrar, no borrar intentos archivados al iniciar uno nuevo. Mantener estas reglas en módulos futuros.

FIX02 de BLOCK 03–04 (v0.4.2): quitar campos redundantes de configuración; detectar ordinarias y reservas desde solucionario, confirmar opciones únicamente durante importación (la mayor letra es un mínimo). Mis simulacros permite eliminar con confirmación irreversible, incluyendo borrador vinculado si existe, sin afectar a otros intentos ni plantillas. FIX01 validado por usuario; FIX02 COMPLETO validado por el usuario en Windows. BLOCK 03–04 STABLE para corrector manual.

BLOCK 05 RC1: lector experimental de plantilla 120+9 A/B/C, sugerencias azules, recortes y revisión, ajuste manual de esquinas, PDF 1–2 páginas o JPG/PNG desde PC o móvil. No integra puntuación ni guardado de lectura hasta BLOCK 06. Artefacto de GitHub nombrado por VERSION, BLOCK, BUILD_LABEL y número/intento de ejecución.

BLOCK 05 FIX01: actualizar empaquetador y prueba de arranque del EXE real obligatoria antes de publicar; no avanzar hasta validar en Windows.


BLOCK 06 RC1: integración del lector en el mismo asistente del manual; importador único para hojas, dos archivos/páginas PC o QR por lote, máximo 100 MiB; orden indiferente por geometría de la plantilla (no OCR de números arbitrarios). Ajuste de reservas por círculos, propuestas de azul/blanco, pendientes filtrables, confirmación conjunta y puntuación. Borradores independientes y modo en historial, migración SQLite 4. Recortes no persistidos; solo letras y datos del examen. Mantener BLOCK 05/06 en validación hasta pruebas en Windows, móvil y revisión de muestra real.


BLOCK 06 FIX01 (v0.6.1): usuario confirmó nota 5,89, 74/33 y resto de flujo RC1; pendiente perfeccionar recortes. Nueva alineación por círculos de ambas páginas y ajuste por fila. Interfaz compacta, carga automática de plantillas con protección ante sustitución y consulta/eliminación conservadas, modo visible junto al nombre en historial. Pendiente validar FIX01 antes de cerrar 05–06 STABLE.


BLOCK 06 FIX02 (v0.6.2): quitar plantilla sin borrar archivo guardado; resaltar números pendientes manuales; persistir imágenes de lectura, alineación y recortes en SQLite 5 junto con respuestas confirmadas; conservar originales visuales al reabrir, no PDF binario. Ajustar por cuatro centros de círculos específicos (zoom/deshacer/reiniciar/auto), mantener lectura anterior si falla. Las fotos de versiones previas no son recuperables automáticamente. Validar antes de STABLE.


BLOCK 06 FIX03 (v0.6.3): FIX02 validado por usuario (incluido ajuste de alineación). Inicio/menú lateral de los correctores siempre crea un examen nuevo; recuperar únicamente desde Mis simulacros. Aviso al salir con cambios: Guardar y salir, Salir sin guardar (descarta cambios no archivados), Cancelar. Consulta de plantilla no modifica nombre, configuración, respuestas o intento; selección con trabajo activo no carga automáticamente, Usar plantilla explícito. Mi temario > Mis plantillas conserva documentos de soluciones originales aceptados (PDF/DOCX, deduplicados) y plantillas reutilizables; vista PDF local y exportación de copia. SQLite esquema 6, migración conservadora. Los PDF antiguos no se pueden recuperar si no se archivaron. Mis temas se implementará en BLOCK 09. Estas reglas reemplazan las antiguas de recuperación automática al entrar. Pendiente validación Windows antes de STABLE.


BLOCK 06 FIX04 (v0.6.4): FIX03 validado. Biblioteca recíproca única; importación múltiple de solucionarios PC/QR, registro automático con nombre del archivo, guardado con nombre elegido y aviso de patrones exactos. Fichas con original y plantilla, orden alfabético/cronológico y metadatos, botones grandes Mis temas/Mis plantillas, eliminar textos redundantes. SQLite 7 conserva datos y fechas desconocidas sin inventarlas. Imágenes y PDF escaneados como solucionarios pendientes de OCR específico. Temarios BLOCK 09. Pendiente validación Windows.

BLOCK 06 FIX05 (v0.6.5): raíz Mi temario con dos pantallas independientes; importación de soluciones en correctores no registra plantillas hasta guardar explícitamente; importación biblioteca confirma lectura y solicita nombre, aviso de coincidencia previo. Eliminación explícita y transaccional de plantilla y simulacros vinculados tras aviso, sin inferir vínculos por coincidencias. SQLite 8 preserva datos antiguos y evita reutilizar IDs. Pendiente validación Windows. OMR y puntuación intactos.


BLOCK 06 FIX06 (v0.6.6): FIX05 validado para plantilla inicial. Se reabre validación de OMR por hojas de otros diseños y reservas ausentes. Configuración de ordinarias y reservas con contraste contra solucionario; reservas pendientes no bloquean si el usuario confirma, advertencia si se necesitan para anuladas. Detección de bloques cuadrados con confirmación de numeración, ajuste guiado para cuadrículas regulares diferentes, opciones impresas 2–5 frente a opciones válidas, varias páginas y reservas mixtas. Centrado de tarjetas de Mi temario. Sin OCR genérico automático de números ni guardado de modelos por ahora. SQLite 8 sin nueva migración. Pendiente pruebas de Windows y hojas adicionales antes de STABLE y BLOCK 07.


Norma de compilación desde FIX06: workflow_dispatch exclusivamente, sin push. Subir todos los archivos antes de ejecutar una sola compilación manual desde Actions (main). Retención de artefactos nuevos: 3 días; conservar EXE STABLE localmente. Mantener nomenclatura de versión, pruebas unitarias y prueba de arranque. No hay cambios de código de aplicación ni de esquema de datos por este ajuste de CI.

FIX07 (v0.6.7): componente común de tarjetas centradas para Inicio, Mi temario, importación; círculos con ajuste local independiente por columnas; círculos conocidos antes de cuadrados, respaldo anterior, diálogos adaptados a la altura de pantalla. Validación de FIX06 parcial; mantener 05–06 en revisión hasta probar hojas variadas en Windows. Compilación solo manual.

FIX08 (v0.6.8): nuevo ajuste de contornos circulares por fila/columna, validación del respaldo por columna y distinción frente a cuadrados; conservar lecturas guardadas hasta reimportar/reajustar expresamente. S24 pendiente de validar con foto original en Windows.

FIX09 (v0.6.9): restablecer numeración sin reimportar; conservar orientación de fotografía de cuadrados; recortes rectificados por fila y geometría archivada compatible con lecturas antiguas. Validación Windows pendiente. Mantener BLOCK 06 hasta confirmar.

FIX10 (v0.6.10): importar NumPy en choose_numbering; mantener las pruebas y el flujo de compilación manual. Pendiente de validación Windows.

FIX11 (v0.6.11): espacio de ajuste de alineación común, restauración automática desde imagen guardada, vista previa antes de aplicar y anulaciones por intento con reservas. Pendiente validar Windows antes de STABLE.


## BLOCK 06 — FIX12 — v0.6.12
- Ajuste común para círculos y cuadrados: elegir una columna detectada, señalar los cuatro centros de esa columna, previsualizar y aplicar. Las demás columnas se conservan. Redefinir bloques reconstruye una página si la detección inicial fue incorrecta. Restablecer automática usa la imagen guardada.
- Se rechazan encuadres desproporcionados y bloques que se solapan con otras preguntas.
- Una raya roja que atraviesa la fila deja la respuesta pendiente con «Posible anulada · tachadura roja · revisar». Una cruz roja aislada sigue siendo informativa. La anulación requiere confirmación del usuario; no se modifica el motor de notas.
- Las cuatro pruebas de regresión añadidas pasan localmente. La prueba gráfica común queda pendiente de GitHub.


# ÁGORA v0.6.13 — BLOCK 06 — FIX13

- Círculos, cuadrados y diseños regulares alternativos: una ruta automática común tanto al importar como al restablecer. Los cuadrados ya no abren el diálogo de numeración. Si no se reconoce la hoja con suficiente seguridad, se ofrece la misma ventana de ajuste (sin seleccionar previamente el tipo de plantilla), conservando la imagen mientras se ajusta.
- Numeración automática por orden de columnas en hojas regulares completas, usando la configuración del examen; se ignoran casillas físicas sobrantes al trasladar respuestas al examen. No se presupone numeración fiable de páginas parciales o arbitrarias: ajustar manualmente si no se puede identificar. El lector no incorpora aún OCR general de numeración impresa.
- Mejora de color: canal de contraste para contornos coloreados, eliminación de tinta impresa repetida de las máscaras de marcas y distinción de rayas rojas frente a fondos rosas o magenta. Detector geométrico adicional para cuadrículas regulares sin marco y con posiciones diferentes de la plantilla conocida. La imagen original se conserva; no se promete identificar tinta indistinguible de la impresión ni diseños arbitrarios.
- Botones de ajuste compactos, texto centrado; se conserva la vista previa y aplicación explícita. No cambia el motor de puntuación, las anulaciones, las reservas, la base de datos ni el QR. No modificar windows.yml; compilación manual.
- Pruebas locales: 27 pruebas OMR anteriores + 4 nuevas + 57 de otros módulos = 88 superadas por grupos. 27 pruebas GUI pendientes en Windows. Comprobaciones adicionales con los archivos de referencia externos: plantilla rosa en blanco (120 ordinarias, 9 reservas, sin falsas anulaciones), TEST 10 (103 propuestas, 8 blancos, 1 duda en 112 preguntas) y plantilla corregida original (106 propuestas, 1 duda en 107 preguntas). Las nuevas fotografías de color que fallaron en el ordenador del usuario no están adjuntas, por lo que no se han reproducido directamente. No se distribuye material privado.



## FIX14 (v0.6.14)
Detector complementario de filas repetidas, exclusión de cabeceras, muestreo de tinta y rayas azules/rojas, renombrado de plantillas y selector QR ampliado. Pendiente validación de usuario, OCR general de numeración y mayor variedad de diseños.

FIX15: refuerzo de numeración y eliminación del ajuste geométrico manual en interfaz. BLOCK 06B: OCR local, verificación real de números. BLOCK 06C: Mis modelos y PDF personalizable. BLOCK 06D/E: importar modelos en blanco y reconocer modelos propios/aprendidos. Pendientes, no implementados en FIX15.

### Siguiente tras validación de FIX16
BLOCK 06B: OCR local y numeración universal; BLOCK 06C: Mi temario / Mis modelos y generador PDF personalizable; BLOCK 06D: importar modelos externos en blanco por PC/QR y aprender geometría; BLOCK 06E: identificación automática de modelos propios y aprendidos. El lector universal sigue admitiendo modelos externos sin registro previo.
