# ÁGORA v0.2.0 — BLOCK 02 — FIX01

Corrector manual local. Conserva el diseño de BLOCK 01 FIX03 (validado visualmente en Windows). Sin Python, instalación de fuentes ni dependencias para el usuario del EXE.

## Actualizar el repositorio existente
Descomprime Agora_BLOCK02_RC1.zip. Desde la raíz del repositorio Agora (rama main), usa Add file > Upload files y arrastra el contenido descomprimido: carpetas agora y tests, y README.md, ROADMAP.md, TESTS.txt. Confirma con Commit changes. No borres los archivos anteriores ni modifiques .github/workflows/windows.yml. El flujo existente compila la versión nueva, aunque el nombre del artefacto conserva BLOCK01. Descarga el artefacto de la ejecución del nuevo commit, no de un commit anterior. El EXE debe indicar v0.2.0 · Block 02.

## Corrector manual
1. Configura nombre, 1–500 preguntas ordinarias, 0–100 reservas, 2–5 opciones, penalización y nota máxima. La penalización inicial 1/3 es provisional, no un criterio oficial verificado. También puede limitarse la nota a cero.
2. Introduce todas las soluciones; X = anulada (también en reservas). Guarda una plantilla si quieres reutilizarla.
3. Introduce las respuestas originales. A–E según configuración; guion = blanco; Retroceso = borrar a pendiente; flechas arriba/abajo = selección. La selección avanza automáticamente. Clic en el número para cambiar la pregunta activa. Las páginas muestran hasta 16 preguntas. Las pendientes solo pasan a blanco con confirmación.
4. Corrige y consulta la nota, contadores y detalle filtrable. Puedes editar soluciones o respuestas y volver a calcular.

Regla de reservas: sustituir las anuladas ordinarias en orden ascendente por reservas válidas en orden ascendente. Las reservas anuladas no se usan. Las reservas sobrantes no cuentan; si faltan reservas válidas, se reduce el denominador por cada anulada no sustituida. Si no hay preguntas evaluables, no se calcula nota. Nota = (aciertos − penalización × errores) × nota máxima / preguntas evaluables; cálculo exacto y redondeo de visualización a dos decimales, mitad alejándose de cero. No aplica baremos oficiales especiales ni notas de corte.

Se guarda un solo borrador local automáticamente tras confirmar configuración y registrar respuestas, además de las plantillas de soluciones que se guarden expresamente. Editar campos de configuración sin pulsar Continuar no guarda dichos cambios. Iniciar otro examen sustituye el borrador tras confirmación. No existe aún historial de exámenes ni exportación. La base de datos pasa de esquema 1 a 2 conservando el perfil. La versión antigua no puede abrir una base actualizada; no borres datos para volver atrás. No se incluyen documentos privados.

## Validación
23 pruebas sin interfaz superadas localmente. 3 pruebas gráficas añadidas o conservadas, pendientes de GitHub Actions (PySide6 no disponible en el entorno de entrega). El EXE y su aspecto en Windows están pendientes de validación. No declarar STABLE hasta aprobarlos.

Bloques 03+: importación universal PC/móvil QR, lectura de PDF, OMR y corrección automática; bloque 07: historial y exportación. Ver ROADMAP.md.

## FIX01
Subir desde la raíz las carpetas agora y tests y los archivos README.md, ROADMAP.md, TESTS.txt incluidos en el parche. No tocar el workflow ni borrar archivos. Mantiene esquema SQLite 2 y los datos existentes. Los pasos superiores son botones; los saltos aplican la configuración y validan las soluciones/respuestas, y el resultado se recalcula. Desplegables cerrados y campos numéricos ignoran la rueda. Consultar plantilla es de solo lectura; Guardar plantilla de respuestas conserva el solucionario y configuración. El flujo definitivo importará soluciones en ambos modos en BLOCK 04; la entrada provisional del BLOCK 02 se conserva mientras tanto.
