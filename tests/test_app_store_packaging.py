import datetime as dt
import importlib.util
from pathlib import Path
import plistlib
import sys
import pytest
import macos_distribution

spec=importlib.util.spec_from_file_location('package_app_store',Path(__file__).resolve().parents[1]/'scripts/package_app_store.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)


def profile():
    return dict(Platform=['OSX'],TeamIdentifier=[release.TEAM],ExpirationDate=dt.datetime(2099,1,1),Entitlements={
        'com.apple.application-identifier':release.TEAM+'.'+release.BUNDLE,
        'com.apple.developer.team-identifier':release.TEAM})


def test_distribution_entitlements_and_build_validation():
    p=profile();ent=release.validate_profile(p,'1.60','1')
    assert ent['com.apple.security.app-sandbox'] is True
    assert ent['com.apple.security.files.user-selected.read-write'] is True
    assert ent['com.apple.security.network.client'] is True
    assert 'com.apple.security.app-sandbox' not in p['Entitlements']
    for build in ('0','bad','1;echo','123456789'):
        with pytest.raises(ValueError):release.validate_profile(p,'1.60',build)


@pytest.mark.parametrize('change',[
    {'Platform':['iOS']}, {'TeamIdentifier':['OTHER']}, {'ExpirationDate':dt.datetime(2000,1,1)},
    {'ProvisionedDevices':['test']}, {'ProvisionsAllDevices':True},
    {'Entitlements':{'com.apple.application-identifier':'OTHER.app'}},
])
def test_wrong_distribution_profiles_rejected(change):
    p=profile();p.update(change)
    with pytest.raises(ValueError):release.validate_profile(p,'1.60','1')


def test_development_entitlement_rejected():
    p=profile();p['Entitlements']['get-task-allow']=True
    with pytest.raises(ValueError):release.validate_profile(p,'1.60','1')


def test_macho_discovery_ignores_resources_and_symlinks(tmp_path):
    binary=tmp_path/'Contents/MacOS/EasyAstroStudio';binary.parent.mkdir(parents=True)
    binary.write_bytes(bytes.fromhex('cffaedfe')+b'code')
    (tmp_path/'resource.txt').write_text('content')
    (tmp_path/'alias').symlink_to(binary)
    assert release.macho_paths(tmp_path)==[binary]


def test_store_marker_requires_frozen_bundle(tmp_path,monkeypatch):
    executable=tmp_path/'Test.app/Contents/MacOS/Test';executable.parent.mkdir(parents=True)
    info=executable.parent.parent/'Info.plist';info.write_bytes(plistlib.dumps({'EASMacAppStoreBuild':True}))
    monkeypatch.setattr(sys,'platform','darwin');monkeypatch.setattr(sys,'executable',str(executable))
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    assert macos_distribution.app_store_build()
    monkeypatch.setattr(sys,'frozen',False)
    assert not macos_distribution.app_store_build()


def test_store_build_omits_external_tipping_control(tmp_path,monkeypatch):
    from test_session_updates import app_and_window,settle
    monkeypatch.setattr(macos_distribution,'app_store_build',lambda:True)
    app,window=app_and_window(tmp_path)
    assert window.coffee_button.isHidden()
    assert not window.feedback_button.isHidden()
    window.close();settle(app,window)


def test_duplicate_names_resolve_to_profile_authorized_fingerprint():
    import hashlib
    chosen=b'profile-authorized-cert';other=b'other-cert'
    chosen_hash=hashlib.sha1(chosen).hexdigest().upper();other_hash=hashlib.sha1(other).hexdigest().upper()
    name='3rd Party Mac Developer Application: Kenneth Hans ('+release.TEAM+')'
    listing=f'1) {other_hash} "{name}"\n2) {chosen_hash} "{name}"\n3) {chosen_hash} "{name}"'
    p=profile();p['DeveloperCertificates']=[chosen]
    assert release.resolve_app_identity(name,p,listing)==chosen_hash
    assert release.resolve_app_identity(chosen_hash.lower(),p,listing)==chosen_hash
    with pytest.raises(ValueError):release.resolve_app_identity(other_hash,p,listing)
    p['DeveloperCertificates']=[chosen,other]
    with pytest.raises(ValueError):release.resolve_app_identity(name,p,listing)
    assert release.resolve_app_identity(chosen_hash,p,listing)==chosen_hash
