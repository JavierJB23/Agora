# Ágora v0.6.20 — BLOCK 06C — FIX01

Base: 06C RC1 v0.6.19 validado por usuario. Pulido visual y eliminación selectiva de páginas. Se conservan el solucionario, las revisiones, imágenes y respuestas de las demás páginas. Si ordinarias y reservas comparten página, se elimina solo la categoría seleccionada y se conserva la foto para la restante. Si hay varias hojas de un tipo, se permite elegir una. Guardar progreso actualiza el simulacro. La sesión QR permanece abierta. Releer conserva el tipo de preguntas de la lectura seleccionada.
- Mis modelos: miniaturas del PDF real, cuadrícula de dos columnas y botones compactos. Consulta con campos de solo lectura sin flechas, casillas deshabilitadas y color con nombre descriptivo y muestra del RGB elegido.
- PDF: observaciones sin líneas interiores, símbolo vectorial del logotipo original sin fondo, en el color de impresión legible. Sin cambios de geometría de casillas ni identificador. Los colores muy claros conservan la protección de contraste del RC1.
- No se modifica el motor OMR/OCR, la puntuación, la sesión QR, ni el esquema de almacenamiento. Compilar manualmente con el windows.yml existente. Próximo 06D después de validar este FIX.

## Histórico (06C FIX01 prevalece)

# Ágora v0.6.19 — BLOCK 06C — RC1

Base: 06B FIX01 validado por el usuario. Copia estable: conservar ZIP v0.6.18 y copia de datos.
- Mi temario > Mis modelos, tercer botón y pantalla independiente. Cuatro diseños de serie, consultables, descargables y personalizables sin modificar originales.
- Generador A4 con vista previa del PDF real, paginación, 1–500 ordinarias, 0–100 reservas, 2–5 opciones (límites del corrector), hasta cuatro columnas, círculos/cuadrados/óvalos, orientación, color, márgenes, tamaño de casillas, título, cabecera, logo, notas y reservas separadas. Si no caben, reduce columnas/pagina; no encoge las casillas. Colores demasiado claros usan tinta oscura para conservar contraste. Guardado local independiente models.sqlite3; editar, renombrar, eliminar con aviso, exportar PDF e imprimir. Se incluyen marcas de alineación e identificador QR de diseño; su lectura específica está pendiente del 06E. El modelo generado no es un solucionario. Importar modelos en blanco desde PC/QR y aprender sus geometrías: 06D, no implementado aún. No se modifica OMR/OCR ni puntuación.
- QR móvil: reloj de 48 px, sin notas redundantes. Al desconectar o agotar tiempo, la web oculta todos los controles y muestra el motivo. El servidor conserva temporalmente únicamente el estado final (hasta el plazo original + 60 s), sin admitir envíos. Si se corta Wi-Fi no puede conocer el motivo hasta reconectar; muestra error de conexión. Se mantienen importación inmediata, enrutamiento y avisos de sustitución.
- Subir todos los archivos, incluyendo requirements.txt (añade ReportLab); mantener windows.yml del 06B RC1, ejecutar Run workflow manualmente. No instalar Python. Se añade comprobación de PDF generado al smoke test del EXE. No se incluyen documentos privados.

Validación local: 146 pruebas ejecutadas, 113 correctas y 33 gráficas omitidas por falta de PySide6; comprobación adicional de los tres estados de página móvil mediante JavaScript y decodificación del QR de las dos páginas del modelo clásico. Revisadas visualmente las dos páginas del clásico y el compacto. Pendientes Windows, impresión real y Safari.

## Histórico (06C RC1 prevalece)

# Ágora v0.6.18 — BLOCK 06B — FIX01

- Sesión móvil global: el QR dura 15 minutos desde su creación, sin reiniciarse con cada envío. La ventana del PC acepta la primera tanda automáticamente; la página del móvil sigue disponible y muestra el destino y la cuenta atrás. Conservar el navegador abierto, navegar a Soluciones (manual o automático), Respuestas del automático o Mis plantillas y enviar otra tanda sin escanear. El destino debe estar disponible y no ocupado; en Inicio y otros apartados se bloquea el envío. Los envíos que cambien de destino se rechazan, sin reasignación silenciosa. Límite de 20 archivos / 100 MiB por tanda (1 archivo para Soluciones). Desconectar móvil en el lateral o cerrar Ágora finaliza la sesión. Se mantiene la revisión de solucionarios y las confirmaciones de sustitución de respuestas solapadas; no se exige confirmación de sustitución para una hoja adicional sin solapamientos. Las duplicidades en biblioteca siguen su flujo normal.
- El resumen/tooltip del OCR se oculta, pero la comprobación de numeración, los avisos importantes y el lector OMR se conservan. No se modifican las fórmulas, la base de datos ni la configuración del compilador RC1.
- Pruebas de HTTP nuevas: sesiones, cambio de destino durante la transferencia, caducidad y formatos; pruebas gráficas añadidas para enrutamiento y cancelación de sustitución. Validación Windows/iPhone pendiente. No se incluyen documentos privados.
- Compilación manual: conservar el windows.yml del RC1.

## Histórico (06B FIX01 prevalece)

# Ágora v0.6.17 — BLOCK 06B — RC1

- OCR local de numeración impresa con Tesseract, añadido como comprobación del lector OMR estable (FIX16). Extrae el área a la izquierda de cada fila, elimina marcos y agrupa caracteres. Contrasta anclas fiables de cada columna; solo remapea con evidencia consistente y rechaza numeraciones duplicadas o secuencias contradictorias repetidas. Si no hay OCR fiable conserva la numeración geométrica, identificándola como tal. No cambia detección de marcas, anulaciones, puntuación o reservas. No es todavía un lector universal ni reconoce cualquier formato, y el OCR de letras de opciones queda pendiente.
- La tabla muestra en una línea el número de identificadores contrastados directamente y por secuencia; el número de pregunta tiene un tooltip con el tipo de verificación. El archivo óptico conserva la información y admite registros antiguos.
- QR reutilizable en todas las importaciones de selección múltiple (respuestas y biblioteca). Mantiene la ventana abierta, acumula tandas, muestra archivos nuevos y total, y permite Importar archivos (N) al terminar. Cierre con confirmación si hay archivos recibidos. Límite acumulado de 20 archivos / 100 MB en las pantallas actuales; el QR caduca tras 15 minutos sin nuevas tandas (5 min para importación individual). Un solucionario individual se sigue recibiendo como antes.
- El workflow Windows cambia: instalar Tesseract en el runner, empaquetarlo y verificar la ejecución real desde el EXE. Sustituir .github/workflows/windows.yml además de todos los archivos del ZIP; continúa siendo compilación manual exclusivamente. No se requiere Python ni Tesseract en el ordenador del usuario. La compilación Windows y el diálogo Qt se validan en GitHub; no se han ejecutado en el entorno Linux sin Qt.
- Próximos pasos: validación de 06B, OCR de opciones y ampliación de formatos; BLOCK 06C Mis modelos y generador PDF; 06D modelos externos en blanco; 06E reconocimiento de modelos. No se incluyen fotografías privadas.

Validación local: suite no gráfica de 102 pruebas, 101 correctas y una carrera en el cierre QR detectada; corregida y las 6 pruebas de transferencia superadas posteriormente. 8 pruebas de OCR (incluyendo una adicional posterior) correctas con Tesseract local. En la exploración del ZIP de 20 fotos, 17 hojas ordinarias y la hoja de reservas alcanzaron OCR; dos fueron rechazadas por el detector geométrico anterior con configuración de prueba 120+9. No se puede certificar la lectura de las 20 fotos en este entorno ni la exactitud de todas las respuestas. El lector previo validado por el usuario se mantiene sin cambios de geometría. La página de reservas tiene poca evidencia OCR y conserva el reconocimiento geométrico.

## Histórico (06B RC1 prevalece)

# Ágora v0.6.16 — BLOCK 06 — FIX16

- Conserva las páginas de reserva incluso cuando el solucionario tiene cero reservas; las casillas sin solución aparecen en Reservas / Todas las preguntas y no participan en la nota. Cuando sí existe clave de reserva, se conserva el comportamiento de puntuación anterior. Importación parcial advertida explícitamente; no se descartan otras páginas válidas sin ofrecer conservarlas.
- Barra rosa bajo la tabla durante la lectura de archivos procedentes del PC o QR; procesamiento óptico en un hilo, porcentaje aproximado por etapas y páginas, tiempo estimado tras observar avance. Transferencia móvil conserva su indicador de envío. No se altera el algoritmo óptico, salvo notificaciones de progreso.
- Prueba local: página de reservas del ZIP con 112 ordinarias y 0/9 reservas configuradas: R1–R9 y recuperación de los nueve recortes en ambos casos. Prueba sintética automática de reservas y 59 pruebas no gráficas de otros módulos superadas. Suite GUI y compilación Windows pendientes; no se incluyen fotografías privadas.
- Compilación manual: no cambiar windows.yml.

## Histórico (FIX16 prevalece)

# Ágora v0.6.15 — BLOCK 06 — FIX15

- Verificación de cabeceras y secuencias de filas; detección por columnas con alturas independientes y preferencia por la foto sin deformar.
- Ajuste manual retirado de la interfaz. Releer hoja conserva la previsualización automática y las revisiones manuales.
- OCR general pendiente (BLOCK 06B).
- Validación local: archivo 2023 del ZIP, recorte sin márgenes, reducción a 650 px de ancho y perspectiva simulada: 120 filas y las ocho posibles anuladas en todos los casos. El fichero exacto recibido desde el móvil no está disponible; verificarlo en Windows. TEST10: 120 filas físicas, 103 letras, 7 blancos y 2 dudas entre las 112 configuradas; no se certifica cada respuesta. Reservas: 9 filas.

# ÁGORA v0.6.14 — BLOCK 06 — FIX14

- Lector: nuevo detector complementario de cuatro columnas de círculos (30 filas por columna) basado en contornos, contraste y continuidad, sin posiciones absolutas de las casillas. Excluye cabeceras por contraste local, reconstruye filas tachadas y valida las cuatro secuencias. Conserva los detectores anteriores y el lector de cuadrados. La numeración general por OCR sigue pendiente.
- Marcas: muestreo central adaptado al tamaño, separación de tinta de impresión repetida, detección de trazos que cruzan espacios entre casillas y de rayas manuscritas que atraviesan el hueco anterior a las opciones. Las posibles anulaciones quedan pendientes, nunca se anulan automáticamente. El ajuste manual de tres opciones comparte el muestreo.
- Mis plantillas: Renombrar conserva ID, fecha, archivo original, patrón y vínculos a los simulacros; rechaza nombres vacíos o duplicados.
- QR: selector de archivos de ancho completo, igual relleno que Enviar; logo original, nombre seleccionado y selección múltiple conservada. Sin cambios de red, límites de carga o almacenamiento.
- Validación con 20 JPEG privados: 15 hojas ordinarias de círculos, cuatro de cuadrados y una de reservas. El detector ha recuperado las 120 filas físicas de las 19 hojas ordinarias y las 9 reservas de la última. En la hoja 2023: 107 letras propuestas, 2 blancos y 11 pendientes, incluidas las ocho rayas visibles (5, 6, 24, 38, 39, 100, 108, 109). No equivale a certificar todas las respuestas: faltan claves y comprobación manual individual. Se siguen observando dudas y algunos avisos adicionales; no se promete cualquier diseño o tinta indistinguible de la impresión.
- Pruebas nuevas: renombrado, selector móvil y hoja sintética coloreada con rayas. Pruebas de regresión locales por grupos; ejecución íntegra y GUI pendientes en GitHub/Windows. No se incluyen fotografías ni datos privados. No cambia el esquema de base de datos ni windows.yml; compilación manual.

## Histórico (FIX15 prevalece)

# ÁGORA v0.6.13 — BLOCK 06 — FIX13

- Círculos, cuadrados y diseños regulares alternativos: una ruta automática común tanto al importar como al restablecer. Los cuadrados ya no abren el diálogo de numeración. Si no se reconoce la hoja con suficiente seguridad, se ofrece la misma ventana de ajuste (sin seleccionar previamente el tipo de plantilla), conservando la imagen mientras se ajusta.
- Numeración automática por orden de columnas en hojas regulares completas, usando la configuración del examen; se ignoran casillas físicas sobrantes al trasladar respuestas al examen. No se presupone numeración fiable de páginas parciales o arbitrarias: ajustar manualmente si no se puede identificar. El lector no incorpora aún OCR general de numeración impresa.
- Mejora de color: canal de contraste para contornos coloreados, eliminación de tinta impresa repetida de las máscaras de marcas y distinción de rayas rojas frente a fondos rosas o magenta. Detector geométrico adicional para cuadrículas regulares sin marco y con posiciones diferentes de la plantilla conocida. La imagen original se conserva; no se promete identificar tinta indistinguible de la impresión ni diseños arbitrarios.
- Botones de ajuste compactos, texto centrado; se conserva la vista previa y aplicación explícita. No cambia el motor de puntuación, las anulaciones, las reservas, la base de datos ni el QR. No modificar windows.yml; compilación manual.
- Pruebas locales: 27 pruebas OMR anteriores + 4 nuevas + 57 de otros módulos = 88 superadas por grupos. 27 pruebas GUI pendientes en Windows. Comprobaciones adicionales con los archivos de referencia externos: plantilla rosa en blanco (120 ordinarias, 9 reservas, sin falsas anulaciones), TEST 10 (103 propuestas, 8 blancos, 1 duda en 112 preguntas) y plantilla corregida original (106 propuestas, 1 duda en 107 preguntas). Las nuevas fotografías de color que fallaron en el ordenador del usuario no están adjuntas, por lo que no se han reproducido directamente. No se distribuye material privado.

## Histórico (FIX13 prevalece)

# ÁGORA v0.6.11 — BLOCK 06 — FIX11

- Ajustar alineación abre una vista previa común para círculos y cuadrados desde la fotografía conservada. Restablecer automática ejecuta los detectores originales (en cuadrados se confirma la numeración). Ajuste por bloques y, en la plantilla conocida, por referencias. En el ajuste por bloques se puede volver a la lectura automática sin reimportar. Los cambios se previsualizan con las casillas verdes antes de aplicar; cancelar conserva la lectura anterior. Las anuladas y las respuestas que difieren de la propuesta previa se preservan al reajustar sus mismas preguntas.
- Anulada disponible en Respuestas de ambos correctores (X por teclado en manual). Se registra en el intento, no en el solucionario compartido. Las anulaciones de la clave y las del intento se combinan sin duplicarse; se usan tantas reservas válidas como anuladas ordinarias, por orden. Las reservas anuladas no sustituyen a nadie. Si faltan reservas necesarias, se avisa antes de contarlas como blancas; si no se necesitan, no afectan a la nota.
- Recortes de ajuste manual por bloques: geometría individual de fila, con previsualización horizontal. No cambia el algoritmo automático de círculos ni cuadrados, ni la clasificación de marcas.
- Compatible con la base de datos actual. La selección Anulada se guarda como X en las respuestas del intento; no se modifican simulacros anteriores al abrirlos. No requiere actualizar windows.yml. Compilación manual en Actions.
- Pruebas: 79 pruebas no gráficas superadas en la suite previa al ajuste final de recortes; dos pruebas específicas de recortes guiados superadas después (una de ellas nueva). 25 pruebas GUI pendientes en Windows (PySide6 no disponible aquí), incluido el nuevo flujo de alineación y guardado de anulaciones.

# ÁGORA v0.6.10 — BLOCK 06 — FIX10

- Corrige la importación de NumPy (`np`) en el diálogo de numeración introducido en FIX09. No cambia la lectura, el QR ni el almacenamiento. Se conserva la prueba gráfica de restablecimiento. Compilación manual: no modificar windows.yml.

# ÁGORA v0.6.9 — BLOCK 06 — FIX09

- Numeración de hojas: botón Restablecer para recuperar los números iniciales propuestos sin volver a importar por QR/PC. Si se cancela el ajuste por bloques o se introduce numeración inválida, se vuelve al diálogo de numeración con la imagen conservada.
- Casillas cuadradas: se conserva la orientación y proporción de la foto en la previsualización. Se intenta leer sin transformar la hoja globalmente; si la lectura previa rectificada resulta necesaria o ambas propuestas no coinciden, se conserva la ruta de lectura del FIX08 y se proyectan sus posiciones sobre la foto sin deformar. Cada fila tiene cuatro vértices propios para dibujar la superposición y enderezar el recorte, sin arrastrar las filas vecinas. La corrección de círculos no cambia.
- Las coordenadas de fila se guardan en los metadatos de lectura junto a la imagen. Se leen también los archivos guardados sin esta geometría; para actualizar recortes de un simulacro antiguo, reimportar la hoja y guardar. No cambia el esquema SQLite ni el flujo QR.
- Prueba con fotografía de referencia TEST 10: 103 letras, ocho blancos y una duda (92), en 112 preguntas. No certifica exactitud letra a letra ni nota. 75 pruebas no gráficas superadas por grupos, 23 GUI pendientes (sin PySide6 en este entorno). No se incluyen fotografías privadas. Compilación manual: mantener windows.yml, pulsar Run workflow.

## Histórico (FIX09 prevalece)

# ÁGORA v0.6.8 — BLOCK 06 — FIX08

- Círculos A–C: nueva detección de contornos impresos en cada columna, ajustando los extremos, las 30 filas, la curvatura y los centros individuales. Comprueba la forma circular frente a la cuadrada y la evidencia por columna; si necesita recurrir a los detectores anteriores, verifica y refina todas las columnas antes de aceptar sus centros. No acepta directamente una cuadrícula global descentrada.
- No se modifica el lector de cuadrados, reservas, puntuación, QR, biblioteca, estética ni almacenamiento. Las imágenes y lecturas guardadas no se recalculan automáticamente: reimportar la hoja o usar Ajustar alineación > Alineación automática, confirmar y guardar. Se mantienen los tamaños de diálogos del FIX07.
- Validación con la foto de S24 visible en las capturas del usuario, incluida una reconstrucción de la captura alineada (eliminando la superposición verde en la medida posible). No disponemos del fichero original de esta hoja; la comprobación es geométrica, no certifica sus respuestas ni nota. No se incluye material privado en el paquete.
- Compilación manual: no cambiar windows.yml; subir archivos y pulsar Run workflow. Pendiente validación del EXE en Windows.

## Histórico (FIX08 prevalece)

# ÁGORA v0.6.7 — BLOCK 06 — FIX07

- Todos los botones grandes (Inicio, Mi temario e importación PC/móvil) comparten un componente con icono y texto centrados como conjunto. No se cambian los iconos laterales de navegación ni el logotipo.
- Círculos A–C conocidos: ajuste independiente por columnas y refinamiento local de cada fila. Se comprueba la cobertura de las 30 filas, los extremos, separación de casillas y coherencia entre columnas; se conserva el algoritmo anterior como respaldo. Se prueba primero la geometría conocida y después la de cuadrados. Se mantiene la numeración confirmada de los bloques de cuadrados y la lectura de reservas.
- Diálogos de alineación y numeración limitados a la altura de pantalla; no modifica corrección, almacenamiento, configuración ni transferencia. No requiere modificar windows.yml: conserva el disparo manual y la prueba del EXE. FIX07 pendiente de validación Windows.
- Validación adicional con la imagen de la captura de S24 (no con la foto original de máxima resolución): alineación de 120 filas automática y por cuatro referencias. No valida la nota de S24 ni garantiza todas las lecturas; usar la revisión de pendientes. Se conservan las pruebas de los documentos anteriores. Ningún documento privado incluido.

## Histórico (FIX07 prevalece)

# ÁGORA v0.6.6 — BLOCK 06 — FIX06

- Dos campos seguros en Configuración: preguntas ordinarias y reservas. Se conservan las cantidades previstas separadas de las detectadas por el solucionario. Si difieren, se avisa al importar y antes de corregir; tras aceptar la corrección se usan las cantidades del solucionario. Si no se acepta, vuelve a Configuración o carga el solucionario correcto. No se inventan claves ni se eliminan preguntas silenciosamente.
- Reservas pendientes: si todas las ordinarias están registradas, se permite corregir tras aviso explícito. El aviso distingue reservas no utilizadas y las necesarias para sustituir anuladas. Las pendientes se convierten en blancas solo al aceptar; las preguntas ordinarias sin resolver siguen pendientes. Se admiten prefijos R-1 en solucionarios y numeración por bloques.
- Lector flexible: conserva el OMR original de círculos A–C y añade detección geométrica de bloques de casillas cuadradas conectadas, con confirmación del número inicial de cada bloque. Distingue opciones impresas y válidas, y marca para revisión las opciones inválidas. Ajuste guiado por cuatro centros para otras cuadrículas regulares de 2–5 opciones y 2–120 filas por bloque. Indicar R1, R4… cuando sean reservas en la misma página o en otra. No es OCR universal de numeración; requiere confirmar la estructura de nuevos diseños. Tinta azul; rojo informativo. Las hojas atípicas todavía pueden requerir corrector manual. No se incluye aún el guardado de modelos de hoja.
- Importación única de respuestas PC/QR: hasta 20 archivos/páginas por sesión, 100 MiB total, con páginas de ordinarias, reservas o mixtas, numeradas por bloque. Conserva imágenes y recortes de cada página en el mismo esquema SQLite 8; no modifica datos existentes. Se rechazan numeraciones duplicadas y sustituciones parciales de páginas para evitar mezclas. No abrir lecturas nuevas multipágina con EXE anteriores.
- Mi temario: icono y nombre centrados verticalmente, separación reducida.
- Compilación manual: actualizar una sola vez `.github/workflows/windows.yml` con el archivo incluido en este ZIP (si la carpeta oculta no se sube desde la web, editar el archivo existente y pegar su contenido completo). Subir el resto del paquete a GitHub si aún no está actualizado. En Actions > Compilar Agora Windows > Run workflow, elegir main y pulsar Run workflow. No hay compilaciones automáticas por push. Los artefactos nuevos caducan tras 3 días; conservar localmente los EXE. No instalar Python. Se conservan las pruebas y la prueba de arranque del EXE. FIX06 pendiente de validación Windows. No publicar documentos privados ni bases de datos.

## Registro histórico (prevalecen las reglas de FIX06)

# ÁGORA v0.6.5 — BLOCK 06 — FIX05

- Mi temario es una raíz con dos tarjetas cuadradas. Cada tarjeta abre su propia pantalla, con botón de vuelta a Mi temario. Nuevo icono de libros. Mis temas continúa pendiente del BLOCK 09.
- Importar soluciones en un corrector solo carga el solucionario del examen. Los bytes originales se conservan localmente para consultar y guardar el examen; no crean una entrada en la biblioteca ni cuentan como coincidencia. Guardar plantilla es una acción explícita. Desde Mis plantillas, Confirmar la lectura lleva al aviso de coincidencias (si procede), seguido del diálogo de nombre con el nombre del archivo sugerido. Desde los correctores Guardar plantilla sigue el mismo proceso. Cancelar no registra una plantilla. Biblioteca única para ambos correctores.
- Eliminar plantilla desde biblioteca o correctores: confirmación con cantidad y nombres de los simulacros asociados; si se acepta, elimina en una transacción la plantilla y los intentos asociados, así como sus borradores. Los intentos sin vínculo explícito no se eliminan por tener el mismo patrón. Los originales pueden conservarse internamente para intentos independientes. Identificadores de plantilla no reutilizables. Migración conserva las plantillas existentes, incluidas las que versiones anteriores registraron automáticamente; no registra nuevos documentos huérfanos y desvincula referencias antiguas inexistentes o claramente incompatibles en lugar de borrar intentos.
- Si se guarda una plantilla durante un examen, guardar progreso conserva su vínculo. Los intentos guardados antes de crear la plantilla que no se vuelvan a guardar permanecen independientes. No cambia OMR ni puntuación. SQLite esquema 8: hacer copia de datos con Ágora cerrado antes de actualizar; no abrir BD migrada con EXE anterior.
- Subir paquete completo a GitHub, conservar windows.yml. No instalar Python. Pruebas locales y pendientes en TESTS.txt.

## Registro histórico (las reglas anteriores quedan sustituidas por FIX05)

# ÁGORA v0.6.4 — BLOCK 06 — FIX04

- Biblioteca compartida entre correctores y Mi temario > Mis plantillas. Importación confirmada registra automáticamente una plantilla con el nombre de archivo; Guardar plantilla permite nombrarla o guardar otra copia. Coincidencia de patrón exacto (ordinarias, reservas y letras, incluidas anuladas) avisa y permite sustituir o guardar otro nombre. No altera intentos archivados.
- Una ficha por plantilla con original y clave interpretada; orden A–Z, Z–A, reciente, antigua; tamaño y fecha/hora local. Las fechas antiguas no registradas se muestran como desconocidas. Originales huérfanos previos se recuperan cuando el lector puede extraer sus soluciones, o quedan consultables para registrar más tarde. Eliminar una plantilla oculta su ficha, conserva originales necesarios para consultas de intentos.
- Importación de hasta 20 solucionarios PDF/DOCX por sesión (100 MiB total), PC y QR, revisión individual. Lector de respuestas mantiene su límite de dos hojas. PDF se visualiza dentro de Ágora; DOCX vista de texto y exportación del original. Imágenes/escaneos sin texto no admitidos como solucionarios.
- Botones de Mi temario con iconos, acciones compactas y textos redundantes retirados. Mis temas se mantiene para BLOCK 09. SQLite esquema 7; hacer copia de datos antes de actualizar y no abrir con EXE anterior. No cambia motor de corrección ni OMR. FIX03 validado por usuario. FIX04 pendiente Windows.
- Subir paquete completo, conservar windows.yml actual. No instalar Python. Pruebas locales en TESTS.txt; interfaz pendiente porque PySide6 no está disponible aquí.

---

# ÁGORA v0.6.3 — BLOCK 06 — FIX03

## FIX03 — biblioteca y nuevo ciclo del simulacro
- Al entrar desde Inicio o el menú lateral en cualquiera de los correctores se inicia un simulacro nuevo. Solo Mis simulacros abre intentos archivados. Al salir, guardar y salir archiva; salir sin guardar descarta el borrador y conserva la última versión archivada; cancelar mantiene la pantalla. Se mantiene el guardado temporal interno durante el trabajo, pero no se ofrece recuperación automática al entrar. Los antiguos borradores sin archivar no reaparecerán.
- Si el examen está vacío, la plantilla elegida se carga automáticamente. Si ya existe trabajo, seleccionar una plantilla no lo cambia; Usar plantilla permite sustituirla explícitamente previa confirmación. Consultar es siempre de solo lectura.
- Mi temario > Mis plantillas muestra los documentos originales (PDF/DOCX) aceptados en ambos correctores y las plantillas reutilizables. El PDF se consulta dentro de Ágora y puede guardarse una copia; Word conserva sus bytes y permite exportar copia. Los originales se archivan automáticamente y se deduplican por contenido y extensión. No se pueden recuperar los archivos originales de importaciones anteriores: se conservan las letras y plantillas antiguas; reimportar para archivar el archivo. Eliminar una plantilla o intento no borra los originales. Mis temas sigue pendiente de BLOCK 09.
- SQLite esquema 6 conserva los datos anteriores. Realizar copia antes de actualizar. No usar una base migrada con EXE anteriores. No se modifica OMR ni puntuación.
- Las notas históricas de versiones anteriores se incluyen a continuación; las reglas de FIX03 prevalecen.

Actualización acumulativa. Subir agora, assets, tests, scripts y archivos de raíz a GitHub. Mantener windows.yml del BLOCK 05 FIX01. No instalar Python. Guardar una copia de la carpeta de datos con Ágora cerrado antes de actualizar: se migra de SQLite 4 a 5; no abrir esa BD con un EXE anterior.

- Quitar plantilla: deselecciona el solucionario cargado y, previa confirmación, limpia las respuestas asociadas del borrador sin eliminar plantillas ni simulacros archivados. Conserva los datos de configuración visibles. Si solo se había seleccionado una plantilla y se rechazó su carga, se puede deseleccionar sin modificar el solucionario importado independiente.
- Números pendientes en el corrector manual: rosa más intenso; el guion registrado como blanco no cuenta como pendiente. El cursor conserva su borde resaltado.
- Persistencia óptica: guarda las imágenes de página a la resolución de lectura (no el PDF/fichero original), imágenes alineadas y coordenadas de recorte, junto con las respuestas revisadas. SQLite guarda snapshots PNG sin pérdida, compartidos entre borrador e historial y eliminados al quedar sin referencias. Recuperar sin nueva importación, consultar en Respuestas > Ver hoja y casillas (Hoja original / Casillas leídas). Los simulacros de versiones anteriores no guardaban imágenes: no pueden recuperarse retroactivamente; reimportar si se necesita y guardar de nuevo. El tamaño de la BD aumenta con las fotos.
- Ajustar alineación sustituye el ajuste de esquinas del papel: señalar los centros en orden 1A, 91C, 120C, 30A (ordinarias) o R1A, R7C, R9C, R3A (reservas). Zoom ×2/×3, deshacer y reiniciar puntos; alternativa Alineación automática. Si la nueva lectura falla se conserva la anterior. Si la detección inicial falla se ofrece indicar tipo de hoja y ajustar manualmente. El ajuste que sí se acepta vuelve a interpretar la página (con confirmación si ya estaba cargada); revisar cambios antes de corregir. Sigue siendo específico de la plantilla 120+9 A/B/C.
- 54 pruebas no gráficas superadas y 15 GUI pendientes (PySide6 no disponible). Hoja real: tanto alineación automática como manual por círculos reproducen 106 propuestas y la 33 pendiente; al elegir B, 74 aciertos, 33 errores, 5,89. Reservas reales sin marcas: nueve blancos con ambos métodos. La prueba del EXE comprueba también recuperación de imágenes. Pendiente probar diálogos, zoom, reapertura visual y EXE en Windows. No se incluyen documentos privados.

---

# ÁGORA v0.6.1 — BLOCK 06 — FIX01

Actualización acumulativa sobre v0.6.0 validada por el usuario (nota 5,89; 74 aciertos, 33 errores). Sin cambios en SQLite, dependencias ni windows.yml. Subir agora, assets, tests, scripts y archivos de raíz. No instalar Python en Windows. Nombre de artefacto dinámico.

- Alineación del lector: ajuste proyectivo de la cuadrícula ordinaria y afín de reservas mediante detección de círculos; ajuste local por fila. Si la geometría no es fiable se rechaza. Continúa especializado en la plantilla A/B/C 120+9. Revisión de recortes y confirmación de lectura antes de corregir.
- Pantalla de respuestas compacta: elimina texto redundante, contador breve, acciones de reinicio y corrección en una sola fila. Se conservan avisos de error, dudas y confirmaciones.
- Al elegir una plantilla se carga automáticamente sin abandonar configuración. Si hay un intento activo se pide confirmación; No permite consultar o eliminar la plantilla seleccionada sin sustituir el intento. Volver a elegirla permite cargarla. Se elimina el botón Cargar plantilla. Consultar y Eliminar permanecen.
- Historial: etiqueta Corrección manual/automática en cursiva rosa al lado del nombre.
- Las fotos no se persisten; igual que en v0.6.0. Las soluciones y respuestas sí.

Pruebas: 49 no gráficas superadas, 13 GUI pendientes (PySide6 no disponible localmente). Con documentos reales, 120 recortes ordinarios y 9 de reserva inspeccionados visualmente; 106 propuestas de 107, pregunta 33 débil (B), 74/33 y 5,89 tras confirmar B. Plantilla vacía 120+9 blancos. No garantiza precisión con otras fotos. Pendiente comprobar visualmente EXE y flujo de plantillas en Windows.

## Historial

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


## BLOCK 06 — FIX12 — v0.6.12
- Ajuste común para círculos y cuadrados: elegir una columna detectada, señalar los cuatro centros de esa columna, previsualizar y aplicar. Las demás columnas se conservan. Redefinir bloques reconstruye una página si la detección inicial fue incorrecta. Restablecer automática usa la imagen guardada.
- Se rechazan encuadres desproporcionados y bloques que se solapan con otras preguntas.
- Una raya roja que atraviesa la fila deja la respuesta pendiente con «Posible anulada · tachadura roja · revisar». Una cruz roja aislada sigue siendo informativa. La anulación requiere confirmación del usuario; no se modifica el motor de notas.
- Las cuatro pruebas de regresión añadidas pasan localmente. La prueba gráfica común queda pendiente de GitHub.
