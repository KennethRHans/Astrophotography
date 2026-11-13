"""Sign a tested sandbox app and create a Mac App Store upload PKG on the owner's Mac.

Never uploads. Certificates/private keys stay in the local Keychain.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

TEAM = 'XHRHMQ4A9G'
BUNDLE = 'com.astrivanta.easyastrostudio'
MACHO = {bytes.fromhex(s) for s in ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe', 'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}


def run(*args):
    return subprocess.run([str(a) for a in args], check=True, capture_output=True).stdout


def validate_profile(profile, version, build, now=None):
    """Fail closed on a development, expired, wrong-team or wrong-app profile."""
    if 'OSX' not in profile.get('Platform', []):
        raise ValueError('Provisioning profile must be for macOS')
    ent = profile.get('Entitlements', {})
    expected = TEAM + '.' + BUNDLE
    if profile.get('TeamIdentifier') != [TEAM]:
        raise ValueError('Provisioning profile belongs to a different Apple team')
    if ent.get('com.apple.application-identifier') != expected:
        raise ValueError('Provisioning profile must match ' + expected)
    if ent.get('com.apple.developer.team-identifier') != TEAM:
        raise ValueError('Provisioning profile team entitlement does not match')
    if (profile.get('ProvisionedDevices') or profile.get('ProvisionsAllDevices')
            or ent.get('get-task-allow') or ent.get('com.apple.security.get-task-allow')):
        raise ValueError('Use a Mac App Store distribution profile, not development/Developer ID')
    expiry = profile.get('ExpirationDate')
    if not isinstance(expiry, dt.datetime):
        raise ValueError('Provisioning profile has no expiration date')
    if expiry.replace(tzinfo=dt.timezone.utc) <= (now or dt.datetime.now(dt.timezone.utc)):
        raise ValueError('Provisioning profile has expired')
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?', version):
        raise ValueError('Invalid app version')
    if not re.fullmatch(r'[1-9]\d{0,3}(?:\.\d{1,2}){0,2}', build):
        raise ValueError('Use an Apple-compatible numeric build number, e.g. 1')
    return dict(ent, **{
        'com.apple.security.app-sandbox': True,
        'com.apple.security.files.user-selected.read-write': True,
        'com.apple.security.network.client': True,
    })


def macho_paths(app):
    found=[]
    for path in app.rglob('*'):
        if path.is_symlink() or not path.is_file():continue
        with path.open('rb') as stream:
            if stream.read(4) in MACHO:found.append(path)
    return sorted(found, key=lambda p:len(p.parts), reverse=True)


def resolve_app_identity(requested, profile, listing):
    """Choose a valid application identity actually authorized by this profile."""
    allowed={hashlib.sha1(cert).hexdigest().upper() for cert in profile.get('DeveloperCertificates', [])}
    candidates=set()
    for digest,name in re.findall(r'([0-9A-Fa-f]{40}) "([^"\n]+)"',listing):
        digest=digest.upper()
        if digest not in allowed:continue
        if f'({TEAM})' not in name or not name.startswith(('3rd Party Mac Developer Application:', 'Apple Distribution:')):continue
        if requested==name or requested.upper()==digest:candidates.add(digest)
    if len(candidates)!=1:
        raise ValueError('Need exactly one valid application identity authorized by the provisioning profile. '
                         'Select its SHA-1 fingerprint with --app-identity, or regenerate the profile for the installed certificate.')
    return candidates.pop()


def package(args):
    if sys.platform != 'darwin':
        raise ValueError('Distribution signing requires macOS and local Apple certificates')
    app=args.app.resolve(); output=args.output.resolve()
    if not app.is_dir() or app.suffix != '.app':raise ValueError('Select the tested EasyAstroStudio.app')
    if output.exists() or output.with_suffix('.json').exists():raise ValueError('Output already exists; choose a new package path')
    app_hash=bool(re.fullmatch(r'[0-9A-Fa-f]{40}',args.app_identity))
    if (not app_hash and f'({TEAM})' not in args.app_identity) or f'({TEAM})' not in args.installer_identity:
        raise ValueError('Both certificate identity names must end with the correct Team ID')
    if not app_hash and not args.app_identity.startswith(('3rd Party Mac Developer Application:', 'Apple Distribution:')):
        raise ValueError('Select a Mac App Distribution application certificate')
    if not args.installer_identity.startswith('3rd Party Mac Developer Installer:'):
        raise ValueError('Select a Mac Installer Distribution certificate')
    profile=plistlib.loads(run('security','cms','-D','-i',args.profile.resolve()))
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    from app_version import APPLE_VERSION
    entitlements=validate_profile(profile, APPLE_VERSION, args.build_number)
    keychain=['--keychain',str(args.keychain.expanduser().resolve())] if args.keychain else []
    listing=run('security','find-identity','-v','-p','codesigning',*([keychain[1]] if keychain else [])).decode()
    app_identity=resolve_app_identity(args.app_identity,profile,listing)
    source_info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    if source_info.get('CFBundleIdentifier') != BUNDLE or source_info.get('CFBundleShortVersionString') != APPLE_VERSION:
        raise ValueError('App bundle identifier/version does not match this release kit')
    # Verify the tested download before changing anything. Work on a copy only.
    run('codesign','--verify','--deep','--strict',app)
    source_ent=plistlib.loads(run('codesign','-d','--entitlements',':-',app))
    if source_ent.get('com.apple.security.app-sandbox') is not True:
        raise ValueError('Use the tested sandbox app, not the unsandboxed preview')
    if not (app/'Contents/Resources/ThirdPartyNotices/inventory.json').is_file():
        raise ValueError('App is missing bundled dependency notices; use the latest preparation build')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='eas-app-store-') as folder:
        temp=Path(folder); staged=temp/app.name
        run('ditto',app,staged)
        shutil.copy2(args.profile,staged/'Contents/embedded.provisionprofile')
        info=dict(source_info,CFBundleVersion=args.build_number,LSApplicationCategoryType='public.app-category.photography',
                  CFBundleDisplayName='Easy Astro Studio',EASMacAppStoreBuild=True)
        (staged/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        entpath=temp/'distribution.entitlements';entpath.write_bytes(plistlib.dumps(entitlements))
        # Sign from the inside out; do not use codesign --deep to sign.
        for path in macho_paths(staged):
            run('codesign','--force','--sign',app_identity,*keychain,'--timestamp=none',path)
        containers=[p for p in staged.rglob('*') if p.is_dir() and not p.is_symlink() and p.suffix in ('.framework','.bundle','.app','.xpc')]
        for path in sorted(containers,key=lambda p:len(p.parts),reverse=True):
            run('codesign','--force','--sign',app_identity,*keychain,'--timestamp=none',path)
        run('codesign','--force','--sign',app_identity,*keychain,'--timestamp=none','--entitlements',entpath,staged)
        run('codesign','--verify','--deep','--strict',staged)
        signed=plistlib.loads(run('codesign','-d','--entitlements',':-',staged))
        for key in ('com.apple.application-identifier','com.apple.developer.team-identifier','com.apple.security.app-sandbox'):
            if signed.get(key) != entitlements[key]:raise ValueError('Signed entitlement mismatch: '+key)
        candidate=temp/'EasyAstroStudio.pkg'
        run('productbuild','--component',staged,'/Applications','--sign',args.installer_identity,*keychain,candidate)
        signature=run('pkgutil','--check-signature',candidate).decode()
        if TEAM not in signature:raise ValueError('Installer signature does not match the Apple team')
        # Publish the completed local result only after validation succeeds.
        shutil.copy2(candidate,output)
    report=dict(version=APPLE_VERSION,build=args.build_number,bundle_id=BUNDLE,team_id=TEAM,
                apple_id='6832157430',sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                status='Distribution-signed locally; Apple upload validation and review pending')
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    print('Package: '+str(output))
    print('Next: validate and deliver this PKG using Apple Transporter on this Mac.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--app-identity',required=True)
    parser.add_argument('--installer-identity',required=True)
    parser.add_argument('--keychain',type=Path,help='Restrict identity lookup and signing to one Keychain')
    parser.add_argument('--build-number',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:package(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1,'Packaging stopped: '+str(exc)+'\n'+(exc.stderr.decode(errors='replace') if isinstance(exc,subprocess.CalledProcessError) and exc.stderr else ''))


if __name__ == '__main__':main()
