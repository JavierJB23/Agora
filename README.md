# Ágora v0.1.0 — BLOCK 01 — RC1

**Estado: candidato a validación, no STABLE.**

Primer bloque del asistente personal de oposiciones para Windows. Python 3.12, PySide6, SQLite. Interfaz rosa pastel y blanca, logo provisional de inspiración griega, menú lateral, ocho módulos con pantallas informativas y configuración persistente. Los módulos futuros están identificados como no disponibles; no hay notas, historiales o correcciones simuladas.

## Compilar en GitHub (sin instalar Python)
1. Descomprime el ZIP completo.
2. Crea un repositorio privado llamado Agora en GitHub, con README inicial.
3. En Code > Add file > Upload files, arrastra todos los archivos y carpetas del ZIP descomprimido, incluida `.github`, a la raíz del repositorio. Confirma Commit changes.
4. En Actions, selecciona Compilar Agora Windows. El push a main o master inicia la compilación automáticamente; también se puede iniciar mediante Run workflow.
5. Cuando el proceso finalice en verde, abre esa ejecución y descarga el artefacto Agora-v0.1-BLOCK01-Windows.
6. Descomprime el artefacto y ejecuta Agora.exe. No necesitas Python ni dependencias en tu ordenador. Windows puede mostrar un aviso de firma digital porque el EXE no está firmado.

Si la carpeta `.github` no aparece en GitHub, verifica que se haya subido `.github/workflows/windows.yml`. No subas documentos personales ni los ejemplos de estudio. El pipeline aún no se ha ejecutado en Windows en este entorno.

## Validación manual antes de STABLE
- Inicio: logo, textos en castellano, rosa pastel y blanco, sin solapamientos a 100% y 125% de escala.
- Abrir los ocho módulos desde el menú y desde sus tarjetas; regresar a Inicio.
- Configuración: guardar nombre y frase, cerrar y abrir, verificar persistencia. Probar nombre vacío.
- Abrir carpeta de datos; confirmar SQLite en `%LOCALAPPDATA%\Agora`.
- Reducir ventana y comprobar desplazamiento vertical.
- Probar el EXE en Windows y reportar errores o capturas de interfaz. No avanzar al bloque 02 hasta confirmar STABLE.

## Estado y límites
- BLOCK 01: navegación, diseño, identidad provisional, ajustes locales. No importa documentos, no realiza correcciones, no usa Internet.
- Pruebas de almacenamiento y registro de módulos ejecutables sin Qt. Prueba de interfaz disponible y se ejecutará cuando PySide6 esté instalado. En el entorno de entrega no se dispone de PySide6 ni de compilador Windows; la UI y el EXE aún no se han validado allí.
- No incluir archivos de estudio en el repositorio. El almacenamiento se separa del directorio del programa.
