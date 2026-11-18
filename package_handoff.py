"""Assemble an immutable source handoff, never build or alter the Apple app."""
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

PIN='af4e91d5387cd02419d828dd70044ce3cb7fcebc'
MODULE_SHA='bed9c8ef1d1e83501b1cb782366092c72c5ecd1c88f16fef3166188ae8062066'
source,docs,destination=map(lambda value:Path(value).resolve(),sys.argv[1:])
actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
if actual!=PIN:raise ValueError('Unexpected Windows source revision: '+actual)
destination.mkdir(parents=True,exist_ok=True)
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=source).decode().split('\0')
for name in filter(None,tracked):
    path=source/name
    if path.suffix.lower() in {'.fit','.fits','.astro','.pfx','.p12','.cer','.msix','.exe'}:
        continue
    if not path.is_file() or path.is_symlink():raise ValueError('Unexpected source entry '+name)
    target=destination/'windows-source'/name;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,target)
reference=source/'assets/reference'
module=(reference/'vendor/aladin-lite/dist/aladin.js').read_bytes()
if hashlib.sha256(module).hexdigest()!=MODULE_SHA:raise ValueError('Unexpected renderer module')
html=(reference/'reference.html').read_text(encoding='utf-8')
match=re.search(r'<script id="aladinModule" type="application/octet-stream">(.*?)</script>',html,re.S)
if not match or base64.b64decode(match[1])!=module:raise ValueError('Prepared renderer mismatch')
for name in ['LICENSE','COPYING','COPYING.LESSER','SOURCE.txt','corresponding-source.zip']:
    if not (reference/'vendor/aladin-lite'/name).is_file():raise ValueError('Missing upstream notice/source '+name)
shutil.copytree(reference,destination/'windows-source/assets/reference',dirs_exist_ok=True)
if (source/'PRIVACY.md').read_bytes()!=(source/'assets/privacy_policy.md').read_bytes():raise ValueError('Privacy policy mismatch')
for name in ['START_HERE.md','APPLE_COMBINED_HANDOFF.md','APPLE_HANDOFF_1_7.md','APPLE_HANDOFF_1_7_1.md','package_handoff.py']:
    shutil.copyfile(docs/name,destination/name)
metadata=dict(product='Easy Astro Studio',handoff='Combined Apple Object Reference and adaptive FITS opening',windows_version='1.7.1 portable test (Object Reference from 1.7.0)',
    source_commit=PIN,source_branch='preview/adaptive-fits-opening-1-7-1',
    repository='https://github.com/KennethRHans/Astrophotography',
    verified_build='https://github.com/KennethRHans/Astrophotography/actions/runs/44333483520',
    windows_tests=dict(passed=128,skipped=14),mac_validation='Not performed; handoff only',
    authorization='Prepare handoff only. Wait for Ken before implementing or releasing the Apple upgrade.',
    renderer=dict(version='3.8.2',module_sha256=MODULE_SHA,source_commit='3476c535e682336d1bde3dac98cf7db54fcc749f'),
    features=['Object Reference (Windows 1.7.0)','Adaptive linked-RGB opening (Windows 1.7.1 test)'],
    previous_reference_source='14258de020e5cbfbdd862d7af10804f42af78a98',
    windows_status='Both user-tested; adaptive change is a portable test, not yet a Store release.',
    excluded='Private captures, projects, API keys, browser profiles, certificates, Windows installers and Mac builds')
(destination/'SOURCE.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
checksums={path.relative_to(destination).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted(destination.rglob('*')) if path.is_file() and path.name!='SHA256SUMS.json'}
(destination/'SHA256SUMS.json').write_text(json.dumps(checksums,indent=2)+'\n',encoding='utf-8')
for name,digest in checksums.items():
    if hashlib.sha256((destination/name).read_bytes()).hexdigest()!=digest:raise ValueError('Checksum mismatch '+name)
print('Validated handoff:',len(checksums),'files;',sum(p.stat().st_size for p in destination.rglob('*') if p.is_file()),'bytes')
