# Easy Astro Studio 1.60 — Mac App Store upload preparation

Bundle ID: `com.astrivanta.easyastrostudio`
Team: `XHRHMQ4A9G`
App Store Connect Apple ID: `6832157430`

The sandbox ZIP is a tested development build, not an upload package. The final
PKG requires your Apple distribution identities and provisioning profile on a Mac.
This checkout does not contain those private credentials. The packaging tool does
not upload or submit the app; Transporter and Apple perform additional validation.

## 1. Create the signing credentials on your Mac

Install Xcode from the Mac App Store, open it once, accept its license, and add
your enrolled Apple account under Xcode Settings → Accounts. Select your team.

In Keychain Access, choose Certificate Assistant → Request a Certificate From a
Certificate Authority. Enter your Apple account email and name, leave CA Email
blank, and select **Saved to disk**. This creates a certificate signing request
(CSR) and a private key on this Mac. Keep the private key on the Mac.

In [Apple Developer → Certificates](https://developer.apple.com/account/resources/certificates/list),
click **+** and create each distribution certificate (names may appear under the
Mac App Store group):

- **Mac App Distribution** (application signing; older name “3rd Party Mac Developer Application”).
- **Mac Installer Distribution** (package signing; “3rd Party Mac Developer Installer”).

Upload the CSR when requested, download each `.cer`, and double-click to install
it. Under Keychain Access → My Certificates, each certificate should expand to
show its private key. Downloading a certificate created on another Mac does not
bring its private key with it.

In [Apple Developer → Profiles](https://developer.apple.com/account/resources/profiles/list),
click **+**, select **Mac App Store** distribution, choose the existing explicit
App ID `com.astrivanta.easyastrostudio`, and select the application distribution
certificate. Generate and download the `.provisionprofile`. Do not choose a
Mac Development or Developer ID profile.

Never post a private key, P12, password, or Apple account credentials in chat.

## 2. Get the release kit and tested app

Use the latest sandbox artifact from `codex/macos-1.5` that includes
`Contents/Resources/ThirdPartyNotices/inventory.json`. Download the repository
source at the matching commit, including `scripts/package_app_store.py` and
`app_version.py`. Unzip both on the Mac. This release adds a native app icon and
bundled dependency notices. The Store signing step adds the profile, the Store
build marker, the application category and the distinct upload build number.
It re-signs all nested Mach-O code and bundles before signing the root app.

The app version remains **1.60**. Use build number **1** for the first upload if
no build for this version has already been uploaded; increment for each retry
that Apple has accepted for processing.

## 3. Produce the signed PKG locally

Open Terminal in the downloaded source folder. List the application signing
identity (the certificate must have a matching private key):

```sh
security find-identity -v -p codesigning
```

The installer identity appears in Keychain Access → My Certificates. Use the
exact installed identity names, including your name and team in parentheses.
Replace the example paths and names below; keep the quotes:

```sh
python3 scripts/package_app_store.py \
  --app '/path/to/EasyAstroStudio.app' \
  --profile '/path/to/EasyAstroStudio.provisionprofile' \
  --app-identity '3rd Party Mac Developer Application: Kenneth Hans (XHRHMQ4A9G)' \
  --installer-identity '3rd Party Mac Developer Installer: Kenneth Hans (XHRHMQ4A9G)' \
  --build-number 1 \
  --output "$HOME/Desktop/EasyAstroStudio-1.60-build1.pkg"
```

If Xcode installed an `Apple Distribution: … (XHRHMQ4A9G)` application identity,
use that exact name instead. The script requires macOS signing tools but no
third-party Python packages. It works on a copy and leaves the tested app intact.
It refuses an existing output path. The accompanying JSON records the version,
build, team, bundle ID and SHA-256 of the completed package. Success is local
signature validation, not Apple certification or proof of acceptance.

## 4. Validate and upload

Install **Transporter** from the Mac App Store and sign in with the enrolled
account. Add the generated `.pkg`, validate it, and deliver it to App Store
Connect. Use App Store Connect → Easy Astro Studio → macOS version **1.60**;
select the uploaded build after processing completes. An upload is not a release.
Send any Apple validation error text for correction before submitting for review.
Developer ID notarization is for distribution outside the Store and is not a
replacement for Mac App Store signing.

Before review, complete the listing, screenshots, support/privacy URLs, App
Privacy answers, pricing/availability and age rating in App Store Connect. Review
the app's optional feedback, plate-solving and Gaia flows when answering privacy
questions; the app does not automatically upload astronomy files. Validate
privacy-manifest/required-reason-API declarations against the actual bundled
Python/Qt dependencies and Apple's current validator feedback. This preparation
has not established that every App Review requirement is satisfied.

The Store marker hides the external Cash App tipping button; it does not add
purchases or change processing. Bundled notices provide installed dependency
license texts/inventory; review Qt LGPL compliance and other redistribution
obligations before public release. Native document-type opening/association is
not added by this packaging step.

## Duplicate certificate names / ambiguous identity

The updated tool resolves the application identity to its SHA-1 fingerprint and
requires that certificate to be authorized by the provisioning profile. You can
also supply the exact fingerprint as `--app-identity`. This avoids choosing the
wrong certificate when different certificates have identical display names.

If duplicate names exist in System and login Keychains, append the following to
the packaging command to restrict both application and installer signing to login:

```sh
--keychain "$HOME/Library/Keychains/login.keychain-db"
```

Keep your certificate/private key pairs. There is no need to delete them to fix
name ambiguity. If the profile authorizes no installed valid certificate, generate
a replacement profile selecting the installed application distribution certificate.

## Transporter: revoked certificate and deployment-target errors

Apple may report hundreds of repeated errors when one certificate is revoked.
A local `security find-identity` listing is not proof of current Apple revocation
status. In Apple Developer → Certificates, select an active Mac App Distribution
certificate with an installed private key, or create/install a new one. Regenerate
the Mac App Store provisioning profile selecting that certificate, download it and
replace the profile passed to the tool. Do not revoke other certificates merely
to resolve duplicate names. The installer certificate need not be replaced unless
Apple flags it too. Re-sign the original sandbox app; do not re-upload the old PKG.

The updated tool sets `LSMinimumSystemVersion` on the copied app before signing.
It inspects every bundled Mach-O load command and takes the highest deployment
target, with a floor of macOS 12.0 for Apple Silicon-only Store submissions. This
can yield a higher minimum than 12.0 depending on Python, Qt and native libraries.
It records the minimum and chosen signing fingerprint in the JSON report.
The same metadata is now populated in future preview/sandbox builds. Existing
sandbox downloads can be repackaged with the updated script; no app download is
needed to correct these metadata fields.

Use a new output path and build number (for example build 2) for the corrected
package. Local signature success still does not establish Apple acceptance.
Transporter can reveal additional errors after the revoked-signature errors clear.

Installer signing also supports `--installer-identity` as a SHA-1 fingerprint.
When multiple installer certificates have the same name, explicitly select the
active certificate confirmed in Apple Developer. The tool validates the selected
identity's certificate type/team and refuses ambiguous names before signing. It
records the chosen installer fingerprint in the JSON. Local identity discovery
does not establish online revocation status.
