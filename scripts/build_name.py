"""Emit traceable GitHub Actions artifact name from the app's version."""
import os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agora
block=re.sub(r'[^0-9A-Za-z]+','-',agora.BLOCK).strip('-')
label=getattr(agora,'BUILD_LABEL','BUILD')
name=f'Agora-v{agora.VERSION}-BLOCK{block}-{label}-Windows-r{os.environ["GITHUB_RUN_NUMBER"]}-a{os.environ["GITHUB_RUN_ATTEMPT"]}'
with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:
    out.write('artifact='+name+'\n')
print(name)
