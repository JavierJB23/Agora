# ÁGORA v0.4.2 — BLOCK 03–04 — FIX02

Corrector manual: se importa el solucionario PDF digital o Word .docx y se introducen a mano las respuestas personales. Conserva motor, identidad y datos locales del BLOCK 02 FIX01. La importación PC/QR es un módulo reutilizable, actualmente recibe un documento por sesión. No incluye OCR, OMR, Word .doc antiguo, imágenes, ni importación múltiple todavía. Los solucionarios deben contener números y letras explícitos; la numeración automática de Word y diseños no reconocidos pueden requerir guardar en PDF o adaptar el archivo.

## Actualizar
Descomprime el ZIP. Desde la raíz de Agora (main), Add file > Upload files, arrastra las carpetas agora, tests y los tres archivos README.md, ROADMAP.md, TESTS.txt. Commit changes. No toques windows.yml ni requirements-build.txt: el flujo existente instala requirements.txt y recoge assets. En Actions descarga el artefacto del nuevo commit (aunque conserva el nombre BLOCK01). Debe abrir v0.4.2 · Block 03–04. No necesitas instalar nada en Windows.

## Flujo
1. Configuración: nombre, penalización, nota máxima y suelo opcional de cero. Las preguntas y reservas se detectan al importar; no se editan en configuración. El número de opciones se confirma exclusivamente en la revisión de importación (una letra máxima no demuestra cuántas opciones tenía el examen). Si existe solucionario, la configuración muestra un resumen de solo lectura.
2. Soluciones: importar documento > Desde PC (o arrastre) / Desde móvil. En móvil: cámara, misma red privada, seleccionar PDF o DOCX y enviar. Si Windows pregunta, autorizar redes privadas, no públicas. El QR es temporal (5 minutos), con token aleatorio y sin nube. HTTP local sin cifrado; usar solo una red de confianza. Límite 100 MB, una transferencia por sesión. Se cierra al aceptar/cancelar/caducar. Los originales no se guardan automáticamente. Se guarda el solucionario estructurado y su nombre.
3. Revisar todas las soluciones y número de ordinarias/reservas. Los huecos internos y duplicados bloquean la importación. No se puede detectar un final truncado si no hay un recuento de referencia; verificar total. Confirmar e importar. Corregir incidencias puntuales si es necesario. Guardar plantilla de respuestas opcional. Las plantillas/borradores completos anteriores se conservan como excepción de compatibilidad. Un nuevo examen exige importación o plantilla guardada.
4. Respuestas personales: teclado/ratón; A–E, guion para blanco, retroceso para pendiente, flechas arriba/abajo. Navegación superior directa. Corregir para ver nota y detalle; el motor no cambia. Guardar progreso archiva el intento en Mis simulacros. El historial básico permite abrir intentos en curso y corregidos; exportación, organización avanzada y estadísticas siguen pendientes.

Regla de reservas y puntuación: reemplazo por orden ascendente; sin reservas válidas suficientes, se reduce denominador. Penalización de 1/3 provisional y configurable. Migra SQLite de esquema 2 a 3, conservando el borrador, las plantillas y los ajustes. No usar un EXE antiguo con la base de datos ya migrada. No se incluyen documentos privados.

## Guardado y recuperación
- Guardar plantilla de respuestas conserva exclusivamente el solucionario y la configuración reutilizable.
- Guardar progreso archiva el intento actual, sus respuestas, la configuración, el punto del asistente y su estado de corrección. Guardar de nuevo actualiza el mismo intento; iniciar uno nuevo crea otro registro cuando se guarda.
- Si sales con cambios sin archivar, puedes guardar y salir, salir sin guardar en el historial (conservando el borrador de recuperación), o cancelar. Al volver a entrar, continuar, iniciar uno nuevo (descarta solo el borrador) o cancelar. Los intentos archivados se mantienen en SQLite y se pueden abrir desde Mis simulacros.
- Se conserva un único borrador de recuperación activo. Los cambios de configuración aún no aplicados se conservan al salir normalmente o guardar progreso; no se garantiza su recuperación si se interrumpe el proceso abruptamente.
- El QR tiene una pantalla separada; la dirección HTTP queda oculta y el selector de IP se muestra al pulsar «¿Problemas de conexión?». No se ha cambiado el protocolo local. Límite de 100 MiB por archivo, no ilimitado; los PDF de soluciones mantienen el límite de 300 páginas.

## Pruebas
37 pruebas no gráficas superadas, 11 gráficas pendientes por falta de PySide6 en este entorno. Incluye migración de esquema 2, independencia de borrador y simulacros archivados, actualización de un intento y transferencia HTTP loopback de 26 MiB. No se ha comprobado visualmente esta revisión en Windows. No se ha probado una carga completa de 100 MiB. Ver TESTS.txt. No declarar STABLE hasta validar.

## FIX02
- Mis simulacros: Eliminar con confirmación explícita Sí/No (No por defecto). Si coincide con el intento activo, se elimina también su borrador, avisando antes; otros intentos y plantillas no se tocan. Se mantiene el esquema 3.
- Configuración simplificada: sin campos manuales redundantes de preguntas, reservas y opciones. Se conservan los datos importados al cambiar el baremo.
