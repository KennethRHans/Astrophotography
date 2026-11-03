# Easy Astro Studio: Microsoft Store submission preparation

This is a preparation kit, not a published Store release. Microsoft certification
and a real Partner Center identity are still required. No Microsoft credentials
or signing keys are needed in the source repository.

## Package identity

Create/enroll in a Microsoft Partner Center developer account and reserve the
app display name. Select the MSIX/packaged app submission route. From Product
management > Product identity, copy these exact, case-sensitive public values:

- Package/Identity/Name -> identity JSON `name`
- Package/Identity/Publisher -> `publisher` (usually CN= followed by a GUID)
- Package/Properties/PublisherDisplayName -> `publisher_display_name`
- Reserved app display name -> `display_name`

The supplied Astrivanta identity is saved in identity.json. For this app, use
that file directly. To build for a different product, copy identity.example.json
to identity.local.json and fill in its assigned values.
That local file is ignored by Git. These values are public identifiers, not secrets.

After building dist/EasyAstroStudio with Build-Windows.cmd, run:

```powershell
./Build-MSIX.ps1 -IdentityFile store/identity.json -Python .venv/Scripts/python.exe
```

Install the Windows 10/11 SDK to provide MakeAppx and MakePRI. Production output
is msix-artifacts/submission/*-Store-UNSIGNED.msix. MakeAppx validates its manifest
and block map. Microsoft signs the accepted Store package; buying a CA signing
certificate is not required for this route. The unsigned candidate is intended
for Partner Center upload, not ordinary double-click installation.

Alternatively, run the Windows package workflow manually and enter all four
public identity values in the workflow inputs. The workflow builds/tests a separate development identity and also builds the
submission candidate using the supplied inputs or the saved store/identity.json.
The EasyAstroStudio-Store-Upload artifact contains only the Store candidate and
its identity/hash/runtime validation reports. Extract the ZIP and upload the
*-Store-UNSIGNED.msix file to Partner Center Packages, rather than uploading the
ZIP, JSON reports or a Development MSIX file.

## Development output and automated validation

Without Partner Center values, use `./Build-MSIX.ps1 -TestIdentity`. Its output
contains DEVELOPMENT in both the package name and BuildInfo.json. Do not submit
this identity to Partner Center or promote it as a public installer.

The CI test signs a separate disposable copy with a short-lived self-signed
certificate, trusts it only on the ephemeral build runner, installs it with
Add-AppxPackage, launches through Windows package activation, verifies real
package identity and runs processing/project/export checks. It then launches
again to verify the saved Light theme survives reopening. It removes the test
package and certificate. No private key is exported or distributed, and the
unsigned artifact is not modified by that test. RuntimeValidation.json records
what passed. This is not Microsoft's certification or a Windows 11 GPU test.

Run the Windows App Certification Kit against the real-identity package before
submission, and test the Store-delivered/private-flight build on a physical
Windows 11 machine, including the RTX 5070 OpenCL path. The hosted runner has no
OpenCL GPU. A native Store package and the old EXE install can coexist; keep one
installation while testing to avoid confusing shortcuts. Upgrade/uninstall is
managed by Windows for the MSIX product. Do not remove a user's older EXE install
or migrate their files without their explicit choice.

## Listing material prepared in this folder

LISTING-DRAFT.md contains proposed description, features and certification notes.
PRIVACY-DRAFT.md records the app's actual data flows and the decisions still
needed before publishing a privacy policy. Review it and publish an approved
policy at a stable HTTPS URL, then supply the URL in the Store listing and app.
The feedback form collects optional name/email and a message through Formspree,
so this requirement applies even though astronomy processing is local.

Add actual screenshots of the current app (dark/light, exposure review and an
image you own), support contact/URL, privacy URL, market/pricing choices and the
Partner Center age-rating questionnaire. Confirm rights to the supplied artwork
and review ThirdPartyNotices in the package before public redistribution.

## Certification notes

This is a Win32/Python desktop app packaged as MSIX, x64, Windows 11 or later.
It uses medium integrity/full trust for local FITS file I/O, temporary disk-backed
stacking and the system's OpenCL driver. No administrative launch, services,
startup tasks, camera control, broadFileSystemAccess or elevation capability is
requested. internetClient covers user-initiated feedback; external links open
in the default browser. A current graphics driver is needed for optional GPU
processing; CPU fallback is supported. The app does not install GPU drivers.

## Microsoft references

- https://learn.microsoft.com/windows/msix/desktop/desktop-to-uwp-manual-conversion
- https://learn.microsoft.com/windows/apps/publish/publish-your-app/msix/app-package-requirements
- https://learn.microsoft.com/windows/apps/publish/store-policies
