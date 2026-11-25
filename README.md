# ÁGORA v0.6.0 — BLOCK 06 — RC1 (integra ajustes del BLOCK 05)

Actualizar con el paquete completo: subir agora, tests, assets, scripts y archivos raíz. Mantener el windows.yml del BLOCK05 FIX01 (ya incluye prueba del ejecutable real y nombre dinámico). Sin instalar Python en Windows.

Ambos correctores comparten el asistente de configuración, solucionario, respuestas y resultado. En automático, las respuestas se importan por un único botón PC/QR, hasta dos archivos y dos páginas en total, 100 MiB agregados por carga. Puede cargar primero reservas o principal, o añadir la otra página después. Reconoce la distribución de casillas de la plantilla conocida (no OCR general de la numeración), y recentra las reservas por detección de círculos. Solo compatible con el modelo de referencia A/B/C de 120 preguntas ordinarias y 9 reservas como máximo. Fotos completas, verticales, PDF/JPG/JPEG/PNG; HEIC, otras tintas y modelos no soportados. Si el modelo no coincide, rechazar la lectura. Se ignoran las casillas sobrantes según solucionario. Azul claro y ausencia de azul se proponen automáticamente (la ausencia se interpreta como blanco bajo la hipótesis de uso exclusivo de azul); rojo informativo, débiles/dobles y rojo sin azul pendientes. El filtro permite revisar solo pendientes o todas; confirmar el conjunto antes de calificar. No certifica precisión universal. La selección puede modificarse; el motor no cambia.

SQLite migra de esquema 3 a 4, conserva datos y plantillas, añade borrador automático independiente, historial con modo y reapertura correcta. Guarda respuestas, soluciones y configuración; las fotos y recortes no se guardan en la BD, solo se conservan en memoria mientras se trabaja en el intento. Al recuperar después de cerrar, se conservan letras, pero no recortes; reimportar para comprobar visualmente. Hacer copia de la carpeta de datos antes de actualizar; no abrir BD migrada con versiones anteriores.

48 pruebas no gráficas superadas, 12 GUI pendientes por no disponer de PySide6. Probados los dos documentos reales: clasificación y recorte de reservas centrado; en las 107 preguntas del examen, 105 propuestas (72 iguales al solucionario y 33 distintas), 2 pendientes (33 y 60). Plantilla rosa vacía: 120+9 propuestas de blanco. No prueba exactitud letra por letra. QR probado por HTTP local, no en iPhone físico. Windows y EXE pendientes. No distribuir documentos privados.

## Registro de versiones anteriores

# ÁGORA v0.5.1 — BLOCK 05 — FIX01

Actualiza PyInstaller a 6.22.3, añade la dependencia interna de NumPy 2.3 y comprueba el EXE real (arranque Qt, ventana, lectura OMR PNG y PDF) antes de publicar el artefacto. No modifica el esquema de datos ni el lector. Actualizar también windows.yml. Prueba del EXE en Windows pendiente de GitHub Actions.

# ÁGORA v0.5.0 — BLOCK 05 — RC1

Actualizar desde el paquete completo: subir agora, assets, tests, scripts y los archivos raíz. Editar `.github/workflows/windows.yml` en GitHub y sustituir su contenido por el incluido en el ZIP (la carpeta oculta puede omitirse en la subida web). El nombre se obtiene automáticamente del código. Mantener el EXE anterior STABLE. No modifica el esquema SQLite.

Corrector automático: espacio de prueba del lector óptico, no corrige ni archiva todavía. Importar hoja principal PDF de 1–2 páginas o foto JPG/PNG desde PC o QR. Página de reservas por separado si se usa una segunda foto. Seleccionar página, comprobar alineación, ajustar cuatro esquinas si es necesario, revisar recortes y confirmar respuestas. Los resultados de la lectura permanecen en memoria mientras el programa está abierto. No se consideran válidas las sugerencias sin revisión; tinta negra y ausencia de azul requieren comprobación. Solo compatible con la plantilla de referencia de 120+9 A/B/C, orientada verticalmente y con papel completo. No incluye soporte HEIC ni otros diseños. Para fotografiar: luz uniforme, sin reflejos, papel plano, azul para original, rojo para correcciones. No se incluyen documentos privados.

Pruebas: 44 no gráficas superadas, 11 GUI omitidas por falta de PySide6. La muestra real produjo 106 sugerencias en 107 preguntas (73 coincidentes con el solucionario, 33 no coincidentes, pregunta 60 dudosa); pregunta 33 azul débil. No equivale a exactitud verificada letra a letra. Hoja en blanco y página de reservas de la muestra sin sugerencias azules. Pendiente ejecución Windows y prueba móvil con foto.

---

# Historial de la versión anterior (v0.4.2)

Corrector manual: se importa el solucionario PDF digital o Word .docx y se introducen a mano las respuestas personales. Conserva motor, identidad y datos locales del BLOCK 02 FIX01. La importación PC/QR es un módulo reutilizable, actualmente recibe un documento por sesión. En esa versión no se incluía OMR ni imágenes. Los solucionarios deben contener números y letras explícitos; la numeración automática de Word y diseños no reconocidos pueden requerir guardar en PDF o adaptar el archivo.

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
