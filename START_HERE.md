# Easy Astro Studio — Apple upgrade handoff (Windows 1.7.0)

Prepared for Ken / Astrivanta. This is a development handoff, not a Mac installer.
**Wait for Ken's explicit instruction before implementing the Apple upgrade,
building a Mac release, signing/notarizing, or submitting it to the App Store.**

When Ken requests the upgrade, start with APPLE_HANDOFF_1_7.md. Port the behavior
selectively into the current Apple source. Do not replace the Apple application
with this Windows snapshot. Preserve Mac Metal processing, sandbox access,
security-scoped bookmarks, native file dialogs, signing, entitlements and existing
Apple-only features. Confirm the current Apple baseline before editing.

Contents:
- APPLE_HANDOFF_1_7.md: behavior, integration points and Apple validation checklist.
- windows-source/: exact tested Windows source, with prepared reference assets,
  upstream renderer licenses and its matching source archive.
- SOURCE.json: pinned source commit, verification evidence and build URLs.
- SHA256SUMS.json: paths and SHA-256 hashes for every other packaged file.

No private FITS files, user projects, API keys, browser profiles or downloaded
survey images are included. This package does not update either installed app.

Suggested message for the Apple developer when you are ready:

> Please use this handoff to bring Object Reference from Windows 1.7.0 into the
> current Apple app. Read START_HERE.md and APPLE_HANDOFF_1_7.md first. Preserve
> Mac-specific features and sandbox/Metal behavior. Test on Apple hardware before
> proposing a release. Do not submit to the App Store without my instruction.
