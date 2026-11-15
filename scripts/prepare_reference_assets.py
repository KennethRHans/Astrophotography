"""Bundle the pinned unmodified Aladin renderer, licenses and matching source.

An alternate unmodified module may be substituted before rebuilding the HTML;
redistributors must preserve its licenses and corresponding-source obligations.
"""
import base64
import hashlib
import io
from pathlib import Path
import re
import tarfile
import urllib.request

VERSION='3.8.2'
INTEGRITY='sha512-/VGtxSWZ4StdKgwjmzqNkUY/3iTaBZJ5F6bN+nAfcK1NEATcAb2CYJX4U8FElpwYMgKrypYQV5KniRzhVbH+nA=='
COMMIT='3476c535e682336d1bde3dac98cf7db54fcc749f'
ROOT=Path(__file__).resolve().parents[1]/'assets/reference'
SOURCE='https://codeload.github.com/cds-astro/aladin-lite/zip/'+COMMIT

def prepare(package_data=None,source_data=None):
    vendor=ROOT/'vendor/aladin-lite';vendor.mkdir(parents=True,exist_ok=True)
    if package_data is None:
        with urllib.request.urlopen('https://registry.npmjs.org/aladin-lite/-/aladin-lite-3.8.2.tgz',timeout=45) as response:package_data=response.read(8*1024*1024)
    if 'sha512-'+base64.b64encode(hashlib.sha512(package_data).digest()).decode()!=INTEGRITY:raise ValueError('Library integrity mismatch')
    with tarfile.open(fileobj=io.BytesIO(package_data),mode='r:gz') as archive:
        for name in ['dist/aladin.js','LICENSE','COPYING','COPYING.LESSER','README.md','package.json']:
            stream=archive.extractfile('package/'+name)
            if stream is None:raise ValueError('Missing upstream file '+name)
            output=vendor/name;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(stream.read())
    if source_data is None:
        with urllib.request.urlopen(SOURCE,timeout=60) as response:source_data=response.read(64*1024*1024)
    if not source_data.startswith(b'PK'):raise ValueError('Invalid corresponding source archive')
    (vendor/'corresponding-source.zip').write_bytes(source_data)
    (vendor/'SOURCE.txt').write_text('Aladin Lite '+VERSION+'\nExact source commit: '+COMMIT+'\n'+SOURCE+'\n'+INTEGRITY+'\nLibrary module is unmodified. See licenses and corresponding-source.zip.\n',encoding='utf-8')
    module=base64.b64encode((vendor/'dist/aladin.js').read_bytes()).decode()
    template=(ROOT/'reference.template.html').read_text(encoding='utf-8')
    html,count=re.subn(r'(<script id="aladinModule" type="application/octet-stream">).*?(</script>)',lambda match:match[1]+module+match[2],template,flags=re.S)
    if count!=1:raise ValueError('Expected one renderer placeholder')
    (ROOT/'reference.html').write_text(html,encoding='utf-8')
    print('Reference renderer prepared, including matching source and license notices.')

if __name__=='__main__':prepare()
