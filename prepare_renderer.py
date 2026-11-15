"""Fetch the pinned public library and matching source, verify, then embed it."""
import base64,hashlib,io,tarfile,urllib.request
from pathlib import Path
import subprocess,sys,json
VERSION='3.8.2'
INTEGRITY='sha512-/VGtxSWZ4StdKgwjmzqNkUY/3iTaBZJ5F6bN+nAfcK1NEATcAb2CYJX4U8FElpwYMgKrypYQV5KniRzhVbH+nA=='
COMMIT='3476c535e682336d1bde3dac98cf7db54fcc749f'
URL='https://registry.npmjs.org/aladin-lite/-/aladin-lite-3.8.2.tgz'
SOURCE='https://codeload.github.com/cds-astro/aladin-lite/zip/'+COMMIT
root=Path('vendor/aladin-lite');root.mkdir(parents=True,exist_ok=True)
with urllib.request.urlopen(URL,timeout=30) as r:data=r.read(8*1024*1024)
assert 'sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode()==INTEGRITY,'Library integrity mismatch'
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
 for path in ['dist/aladin.js','LICENSE','COPYING','COPYING.LESSER','README.md','package.json']:
  member=tar.extractfile('package/'+path)
  if member is None:raise ValueError('Missing upstream file '+path)
  output=root/path;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(member.read())
with urllib.request.urlopen(SOURCE,timeout=45) as r:source=r.read(64*1024*1024)
if not source.startswith(b'PK'):raise ValueError('Invalid upstream source archive')
(root/'corresponding-source.zip').write_bytes(source)
(root/'SOURCE.txt').write_text('Aladin Lite '+VERSION+'\nExact source commit: '+COMMIT+'\n'+SOURCE+'\n'+INTEGRITY+'\nThe library module is unmodified. See licenses and corresponding-source.zip.\n')
subprocess.run([sys.executable,'pack_renderer.py','Reference-View-Test.html',str(root/'dist/aladin.js')],check=True)
print('Renderer source/license bundle prepared:',len(source),'source bytes')
