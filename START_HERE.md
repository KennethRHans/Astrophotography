# Combined Apple handoff — Object Reference + adaptive FITS opening

This package supersedes the earlier separate Object Reference handoff. It includes
BOTH pending features, with one pinned Windows source snapshot and all renderer
assets needed for offline inspection. Ken has not yet updated the Apple app with
these changes. Port both together when Ken asks to begin the Apple upgrade.

**Preparation only: do not implement, build a Mac release, sign/notarize, or submit
an Apple update until Ken gives that instruction.**

Read in this order:
1. APPLE_COMBINED_HANDOFF.md — scope, integration order and combined checks.
2. APPLE_HANDOFF_1_7.md — full Object Reference integration/security/licensing notes.
3. APPLE_HANDOFF_1_7_1.md — adaptive opening transfer, UI and project compatibility.
4. windows-source/ — tested source snapshot containing BOTH features.

SOURCE.json records the exact tested revisions. SHA256SUMS.json verifies every
other packaged file. Prepared reference.html, the unmodified Aladin module,
licenses and its matching source archive are included. No private FITS, projects,
comparison photos, API keys, browser profiles or signing certificates are included.

This is a development handoff, not a Mac installer. The snapshot is Windows code
for selective porting; preserve the current Apple app's Metal path, sandbox/file
access, bookmarks, application identity, preferences, signing and packaging. Do
not copy its PREVIEW_BUILD flag, Windows version or test preference namespace.

Suggested message when you are ready:

> Please upgrade the current Apple app using this combined handoff. Implement
> BOTH Object Reference and the adaptive linked-RGB FITS opening preview. Read
> START_HERE.md and the three handoff documents first. Preserve Apple-specific
> behavior, old project appearances and original FITS pixels. Test on Apple
> hardware before proposing a release. Do not submit to the Store without my
> instruction.
