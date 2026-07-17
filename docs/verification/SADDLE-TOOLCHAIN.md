# Saddle Execution Toolchain

**Recorded:** 2026-07-17T12:30:55Z

**Platform:** Windows, PowerShell 5.1 execution surface with Git for Windows Bash for repository shell hooks.

| Tool | Version/status | Execution rule |
|---|---|---|
| Git | `2.54.0.windows.1` | Repository operations; live fetch/push use the configured GitHub remote. |
| Git Bash | `5.3.9` | Authoritative runner for Bash hooks and integrity scripts. |
| Rust compiler | `rustc 1.96.1 (31fca3adb 2026-06-26)` | Workspace compilation. |
| Cargo | `1.96.1 (356927216 2026-06-26)` | Rust build/test/lint. |
| OpenSSL | `3.5.6` from Git for Windows | Prepend `C:\Program Files\Git\usr\bin` to `PATH` for Rust mTLS gates. |
| Python | `3.14.4` | Verification and support tooling where repository scripts require Python. |
| Node.js | `v24.15.0` | Console/client build tooling. |
| npm | `11.12.1` via `npm.cmd` | PowerShell script execution policy blocks `npm.ps1`; invoke `npm.cmd`. |
| Docker CLI | `29.6.1` | Live profiles; Docker configuration access must be verified before claiming daemon availability. |
| cargo-deny | `0.19.7` | Dependency/license/advisory policy. |
| cargo-audit | `0.22.1` | Rust advisory scan. |
| Gitleaks | `8.30.1` | Primary import secret scanner. |
| TruffleHog | unavailable | Do not claim it ran. SAD-03 must supply an independent second scanner. |
| detect-secrets | broken launcher | Installed entrypoint lacks its Python package. Do not claim it ran. |
| jq | unavailable on PowerShell `PATH` | Prefer repository-native Rust/Python parsing or Git Bash bundled tools if present. |
| Semgrep | unavailable | Not a required SAD-00 gate. |

## Known Environment Constraints

- The sandbox cannot read the user's global Git ignore and SSH `allowed_signers` files. Exact commit messages and embedded signature fingerprints remain inspectable; trust verification may require the unsandboxed Git environment.
- Repository hooks invoked directly by Windows Git may resolve through unavailable WSL. Run the same hook script explicitly with `C:\Program Files\Git\bin\bash.exe`; never use hook-routing failure as permission to skip the gate.
- Docker CLI presence is not proof that the daemon, images, networks, or live dependencies are available.
