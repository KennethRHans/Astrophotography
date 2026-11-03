"""Stage an MSIX payload using either real Partner Center identity or explicit test mode."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app_version import VERSION

NS='http://schemas.microsoft.com/appx/manifest/foundation/windows10'
UAP='http://schemas.microsoft.com/appx/manifest/uap/windows10'
UAP10='http://schemas.microsoft.com/appx/manifest/uap/windows10/10'
RESCAP='http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities'
for prefix,uri in [('',NS),('uap',UAP),('uap10',UAP10),('rescap',RESCAP)]:ET.register_namespace(prefix,uri)
TEST_IDENTITY=dict(name='Astrivanta.EasyAstroStudio.Development',publisher='CN=Astrivanta MSIX Development',publisher_display_name='Astrivanta (development test)',display_name='Easy Astro Studio Test')


def validate_identity(identity,test=False):
    for key in ('name','publisher','publisher_display_name','display_name'):
        value=identity.get(key)
        if not isinstance(value,str) or not value.strip() or any(ord(ch)<32 for ch in value):raise ValueError(f'Provide the Partner Center {key} value.')
    if not re.fullmatch(r'[A-Za-z0-9.-]{3,50}',identity['name']):raise ValueError('Invalid MSIX package identity name.')
    if not identity['publisher'].startswith('CN='):raise ValueError('Publisher must match the Partner Center distinguished name (CN=...).')
    if not test and (identity['name']==TEST_IDENTITY['name'] or identity['publisher']==TEST_IDENTITY['publisher']):raise ValueError('Development identity cannot be used for a Store submission.')
    return dict(identity)


def manifest(identity,version=None):
    version=version or VERSION+'.0'
    parts=version.split('.')
    if len(parts)!=4 or not all(p.isdigit() and 0<=int(p)<=65535 for p in parts) or int(parts[0])==0 or int(parts[3])!=0:raise ValueError('Store version requires four numbers, a nonzero major version and final component 0.')
    node=lambda tag:'{'+NS+'}'+tag
    root=ET.Element(node('Package'),{'IgnorableNamespaces':'uap uap10 rescap'})
    ET.SubElement(root,node('Identity'),{'Name':identity['name'],'Publisher':identity['publisher'],'Version':version,'ProcessorArchitecture':'x64'})
    properties=ET.SubElement(root,node('Properties'))
    for tag,value in [('DisplayName',identity['display_name']),('PublisherDisplayName',identity['publisher_display_name']),('Description','Align and stack FITS exposures; adjust, crop and export astrophotography images.'),('Logo',r'Assets\StoreLogo.png')]:ET.SubElement(properties,node(tag)).text=value
    resources=ET.SubElement(root,node('Resources'));ET.SubElement(resources,node('Resource'),{'Language':'en-US'})
    dependencies=ET.SubElement(root,node('Dependencies'));ET.SubElement(dependencies,node('TargetDeviceFamily'),{'Name':'Windows.Desktop','MinVersion':'10.0.22000.0','MaxVersionTested':'10.0.26100.0'})
    applications=ET.SubElement(root,node('Applications'))
    application=ET.SubElement(applications,node('Application'),{'Id':'App','Executable':r'App\EasyAstroStudio.exe','{'+UAP10+'}RuntimeBehavior':'packagedClassicApp','{'+UAP10+'}TrustLevel':'mediumIL'})
    ET.SubElement(application,'{'+UAP+'}VisualElements',{'DisplayName':identity['display_name'],'Description':'Astrophotography FITS processing','Square150x150Logo':r'Assets\Logo150.png','Square44x44Logo':r'Assets\Logo44.png','BackgroundColor':'transparent'})
    capabilities=ET.SubElement(root,node('Capabilities'));ET.SubElement(capabilities,node('Capability'),{'Name':'internetClient'});ET.SubElement(capabilities,'{'+RESCAP+'}Capability',{'Name':'runFullTrust'})
    ET.indent(root)
    return ET.ElementTree(root)


def make_assets(source,destination):
    # Export the existing approved artwork to Windows-required resource sizes.
    from PySide6 import QtCore,QtGui
    image=QtGui.QImage(str(source))
    if image.isNull():raise ValueError('Cannot load the approved logo.')
    destination.mkdir(parents=True,exist_ok=True)
    for name,size in [('StoreLogo',50),('Logo44',44),('Logo150',150),('Logo44.targetsize-44_altform-unplated',44),('Logo44.targetsize-256_altform-unplated',256)]:
        canvas=QtGui.QImage(size,size,QtGui.QImage.Format_ARGB32);canvas.fill(QtCore.Qt.transparent)
        scaled=image.scaled(round(size*.84),round(size*.84),QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation)
        painter=QtGui.QPainter(canvas);painter.drawImage((size-scaled.width())//2,(size-scaled.height())//2,scaled);painter.end()
        if not canvas.save(str(destination/(name+'.png'))):raise OSError('Could not save Store assets.')


def collect_licenses(destination):
    destination.mkdir(parents=True,exist_ok=True)
    summary=[]
    for distribution in importlib.metadata.distributions():
        name=distribution.metadata.get('Name','unknown');safe=re.sub(r'[^A-Za-z0-9_.-]','_',name)
        copied=[]
        for member in distribution.files or []:
            text=str(member).replace('\\','/')
            if '.dist-info/' not in text:continue
            if '/licenses/' not in text and not re.match(r'^(LICENSE|COPYING|NOTICE)',Path(text).name,re.I):continue
            source=Path(distribution.locate_file(member))
            if not source.is_file():continue
            relative=text.split('.dist-info/',1)[1]
            target=destination/safe/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);copied.append(str(target.relative_to(destination)))
        summary.append(dict(name=name,version=distribution.version,license_files=copied))
    (destination/'inventory.json').write_text(json.dumps(sorted(summary,key=lambda r:r['name'].lower()),indent=2),encoding='utf-8')


def stage(payload,output,identity,test=False):
    identity=validate_identity(identity,test)
    payload=Path(payload);output=Path(output)
    if not (payload/'EasyAstroStudio.exe').is_file():raise ValueError('Build the Windows executable before packaging.')
    if output.exists() and any(output.iterdir()):raise ValueError('Staging output must be empty; refusing to overwrite existing files.')
    output.mkdir(parents=True,exist_ok=True)
    shutil.copytree(payload,output/'App')
    logo=Path(__file__).resolve().parents[1]/'assets'/'easy-astro-logo.png'
    make_assets(logo,output/'Assets')
    collect_licenses(output/'ThirdPartyNotices')
    manifest(identity).write(output/'AppxManifest.xml',encoding='utf-8',xml_declaration=True)
    info=dict(purpose='DEVELOPMENT TEST ONLY - NOT A STORE SUBMISSION' if test else 'Store submission candidate; certification pending',identity=identity,version=VERSION+'.0',architecture='x64',minimum_windows='Windows 11',signed=False)
    (output/'BuildInfo.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    return info


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--payload',required=True);parser.add_argument('--output',required=True)
    group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--identity');group.add_argument('--test-identity',action='store_true')
    args=parser.parse_args();identity=TEST_IDENTITY if args.test_identity else json.loads(Path(args.identity).read_text(encoding='utf-8-sig'))
    print(json.dumps(stage(args.payload,args.output,identity,args.test_identity),indent=2))
