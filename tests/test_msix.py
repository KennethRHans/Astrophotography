import sys
from pathlib import Path
import importlib.util
import xml.etree.ElementTree as ET
import pytest

spec=importlib.util.spec_from_file_location('prepare_msix',Path(__file__).resolve().parents[1]/'scripts'/'prepare_msix.py')
msix=importlib.util.module_from_spec(spec);spec.loader.exec_module(msix)


def test_manifest_requires_real_identity_for_store_and_escapes_values():
    with pytest.raises(ValueError):msix.validate_identity(msix.TEST_IDENTITY)
    with pytest.raises(ValueError):msix.validate_identity(dict(name='',publisher='',publisher_display_name='',display_name='Easy Astro Studio'))
    identity=dict(name='12345.AstrivantaEasyAstroStudio',publisher='CN=12345678-1234-1234-1234-123456789012',publisher_display_name='A & B',display_name='Easy Astro Studio')
    root=msix.manifest(msix.validate_identity(identity)).getroot()
    data=ET.tostring(root);parsed=ET.fromstring(data)
    assert parsed.find('{'+msix.NS+'}Properties/{'+msix.NS+'}PublisherDisplayName').text=='A & B'
    assert parsed.find('{'+msix.NS+'}Identity').attrib['Version']=='1.5.0.0'
    app=parsed.find('{'+msix.NS+'}Applications/{'+msix.NS+'}Application')
    assert app.attrib['{'+msix.UAP10+'}TrustLevel']=='mediumIL'
    assert app.attrib['Executable']=='App\\EasyAstroStudio.exe'
    for version in ['0.17.0.0','1.0.0.1','1.0.0','1.0.99999.0']:
        with pytest.raises(ValueError):msix.manifest(identity,version)


def test_store_icons_and_stage_preserve_payload(tmp_path,monkeypatch):
    from PySide6.QtGui import QImage
    payload=tmp_path/'payload';payload.mkdir();(payload/'EasyAstroStudio.exe').write_bytes(b'test executable')
    (payload/'original.txt').write_text('preserve original')
    monkeypatch.setattr(msix,'collect_licenses',lambda path:path.mkdir())
    output=tmp_path/'staged'
    info=msix.stage(payload,output,msix.TEST_IDENTITY,test=True)
    assert info['purpose'].startswith('DEVELOPMENT TEST ONLY') and not info['signed']
    assert (output/'App'/'original.txt').read_text()=='preserve original'
    for name,size in [('StoreLogo',50),('Logo44',44),('Logo150',150)]:
        image=QImage(str(output/'Assets'/(name+'.png')));assert image.width()==size and image.height()==size
    with pytest.raises(ValueError):msix.stage(payload,output,msix.TEST_IDENTITY,test=True)


def test_upload_archive_matches_astrivanta_identity_and_rejects_mismatch(tmp_path,monkeypatch):
    import json,zipfile
    scripts=Path(__file__).resolve().parents[1]/'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    import verify_msix
    identity=json.loads((scripts.parent/'store'/'identity.json').read_text())
    assert identity['name']=='Astrivanta.EasyAstroStudio'
    assert identity['publisher']=='CN=D1BC40AB-66EF-44E8-9901-3DF6CBECAF25'
    assert identity['publisher_display_name']=='Astrivanta'
    path=tmp_path/'store.msix'
    def package(publisher=None):
        data=dict(identity)
        if publisher:data['publisher']=publisher
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('AppxManifest.xml',ET.tostring(msix.manifest(data).getroot()))
            archive.writestr('App/EasyAstroStudio.exe',b'test executable')
            archive.writestr('BuildInfo.json',json.dumps(dict(identity=identity,purpose='Store submission candidate; certification pending')))
    package();report=verify_msix.verify(path,identity)
    assert report['status']=='passed' and len(report['sha256'])==64 and not report['signed']
    package('CN=WrongPublisher')
    with pytest.raises(ValueError,match='Publisher'):verify_msix.verify(path,identity)
