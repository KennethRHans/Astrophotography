"""Verify the actual upload archive against the supplied Partner Center identity."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_version import VERSION
from prepare_msix import validate_identity,NS


def verify(path,identity):
    identity=validate_identity(identity)
    with zipfile.ZipFile(path) as archive:
        root=ET.fromstring(archive.read('AppxManifest.xml'))
        package=root.find('{'+NS+'}Identity');properties=root.find('{'+NS+'}Properties')
        expected={'Name':identity['name'],'Publisher':identity['publisher'],'Version':VERSION+'.0','ProcessorArchitecture':'x64'}
        for key,value in expected.items():
            if package.get(key)!=value:raise ValueError(f'Manifest {key} does not match expected Store value.')
        for key,value in [('PublisherDisplayName',identity['publisher_display_name']),('DisplayName',identity['display_name'])]:
            if properties.find('{'+NS+'}'+key).text!=value:raise ValueError(f'Manifest {key} does not match expected Store value.')
        if 'AppxSignature.p7x' in archive.namelist():raise ValueError('The Store upload must remain the original unsigned candidate, not the CI test-signed copy.')
        if 'App/EasyAstroStudio.exe' not in archive.namelist():raise ValueError('Application executable missing from package.')
        info=json.loads(archive.read('BuildInfo.json'))
        if info['identity']!=identity or info['purpose'].startswith('DEVELOPMENT'):raise ValueError('BuildInfo does not identify this as the intended Store candidate.')
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return dict(status='passed',file=Path(path).name,sha256=digest.hexdigest(),identity=identity,version=VERSION+'.0',architecture='x64',signed=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('package');parser.add_argument('--identity',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
    result=verify(args.package,json.loads(Path(args.identity).read_text(encoding='utf-8-sig')))
    Path(args.report).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
