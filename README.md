# ÁGORA v0.4.0 — BLOCK 03–04 — RC1

Corrector manual: se importa el solucionario PDF digital o Word .docx y se introducen a mano las respuestas personales. Conserva motor, identidad y datos locales del BLOCK 02 FIX01. La importación PC/QR es un módulo reutilizable, actualmente recibe un documento por sesión. No incluye OCR, OMR, Word .doc antiguo, imágenes, ni importación múltiple todavía. Los solucionarios deben contener números y letras explícitos; la numeración automática de Word y diseños no reconocidos pueden requerir guardar en PDF o adaptar el archivo.

## Actualizar
Descomprime el ZIP. Desde la raíz de Agora (main), Add file > Upload files, arrastra las carpetas agora, assets, tests y los cuatro archivos README.md, ROADMAP.md, TESTS.txt, requirements.txt. Commit changes. No toques windows.yml ni requirements-build.txt: el flujo existente instala requirements.txt y recoge assets. En Actions descarga el artefacto del nuevo commit (aunque conserva el nombre BLOCK01). Debe abrir v0.4.0 · Block 03–04. No necesitas instalar nada en Windows.

## Flujo
1. Configuración: nombre, penalización y nota máxima; las cantidades se ajustan tras leer el solucionario. Número de opciones revisable (una letra máxima no demuestra cuántas opciones tenía el examen).
2. Soluciones: importar documento > Desde ordenador (o arrastre) / Desde móvil · QR. En móvil: cámara, misma red privada, seleccionar PDF o DOCX y enviar. Si Windows pregunta, autorizar redes privadas, no públicas. El QR es temporal (5 minutos), con token aleatorio y sin nube. HTTP local sin cifrado; usar solo una red de confianza. Límite 25 MB, una transferencia por sesión. Se cierra al aceptar/cancelar/caducar. Los originales no se guardan automáticamente. Se guarda el solucionario estructurado y su nombre.
3. Revisar todas las soluciones y número de ordinarias/reservas. Los huecos internos y duplicados bloquean la importación. No se puede detectar un final truncado si no hay un recuento de referencia; verificar total. Confirmar e importar. Corregir incidencias puntuales si es necesario. Guardar plantilla de respuestas opcional. Las plantillas/borradores completos anteriores se conservan como excepción de compatibilidad. Un nuevo examen exige importación o plantilla guardada.
4. Respuestas personales: teclado/ratón; A–E, guion para blanco, retroceso para pendiente, flechas arriba/abajo. Navegación superior directa. Corregir para ver nota y detalle; el motor no cambia. Historial aún pendiente.

Regla de reservas y puntuación: reemplazo por orden ascendente; sin reservas válidas suficientes, se reduce denominador. Penalización de 1/3 provisional y configurable. Mantiene esquema SQLite 2. No se incluyen documentos privados.

## Pruebas
31 pruebas no gráficas superadas, 6 gráficas pendientes por falta de PySide6 en este entorno. Se comprobó extracción de los dos PDF reales aportados: 120+9 y 107+0. QR probado por HTTP loopback, no con móvil físico ni Windows. Ver TESTS.txt. El estilo de controles y el EXE están pendientes de validación en Windows. No declarar STABLE aún.
