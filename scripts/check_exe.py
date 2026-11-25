"""Run the actual frozen program from an isolated working directory in CI."""
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

exe = Path(sys.argv[1]).resolve(strict=True)
with TemporaryDirectory() as folder:
    report = Path(folder) / 'smoke.txt'
    env = dict(os.environ)
    for key in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(key, None)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    result = subprocess.run([str(exe), '--smoke-test', str(report)], cwd=folder, env=env, timeout=120)
    message = report.read_text(encoding='utf-8') if report.exists() else 'No se generó informe de arranque.'
    print(message)
    if result.returncode != 0 or not message.startswith('OK\n'):
        raise SystemExit('El EXE no ha superado la prueba de arranque. No se publicará.')
