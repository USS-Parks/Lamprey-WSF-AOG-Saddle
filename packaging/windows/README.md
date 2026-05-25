# Windows packaging (scaffold)

This directory holds the Windows installer recipe for Lamprey MAI.

**Status:** scaffold only, NOT built or signed yet.
PACKAGING-01 (deferred) will harden this — code-signing certificate,
authenticode timestamping, MSI variant, fresh-machine build verification.

## Contents

- `lamprey-mai.iss` — Inno Setup 6 script. Bundles the three shipped
  exes (`lamprey-mai`, `lamprey-mai-api`, `lamprey-mai-admin`) and the
  visual assets (startup image, install-screen splash, ASCII banner).
- The wizard splash + small icon both point at
  `docs/assets/lamprey-mai-install-screen.png` — the gold "LAMPREY MAI"
  badge.

## Building locally

Pre-reqs: [Inno Setup 6](https://jrsoftware.org/isinfo.php) on `PATH`,
and a release build of the three exes available under
`packaging/windows/bin/`:

```powershell
cd mai
cargo build --release -p lamprey-mai -p lamprey-mai-api -p lamprey-mai-admin
mkdir packaging\windows\bin -Force | Out-Null
Copy-Item target\release\lamprey-mai*.exe packaging\windows\bin\
ISCC.exe packaging\windows\lamprey-mai.iss
```

The installer drops as
`packaging/windows/Output/lamprey-mai-setup-<version>.exe`.

## Splash assets

The installer-time splash is a separate concern from the launcher-time
splash. Both currently use canonical PNGs under `docs/assets/`:

| Surface                         | Asset                                       |
| ------------------------------- | ------------------------------------------- |
| Inno Setup wizard splash        | `lamprey-mai-install-screen.png` (gold badge) |
| `lamprey-mai.exe` startup splash | `lamprey-startup-image.png` (silhouette)     |
| Terminal banner after splash    | `lamprey-banner.txt` (ASCII)                |

The launcher's startup splash is baked into the exe via
`include_bytes!` (see `tools/mai-launcher/src/splash.rs`); duplicating
it into `{app}\assets\` at install time is for operator inspection,
not runtime.
