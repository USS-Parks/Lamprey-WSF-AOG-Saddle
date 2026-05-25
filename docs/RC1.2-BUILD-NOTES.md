# RC1.2 Build Notes

**Project:** Island Mountain MAI + Lamprey
**Release:** RC1.2 (post-DOUGHERTY re-bundle)
**Freeze commit:** `059a6e3` (Merge DOUGHERTY lane to main, 2026-05-24)
**Build host:** Windows 11 Home, x86_64-pc-windows-msvc
**Build session:** RC-10
**Predecessor build:** RC1.1-docs (`b0fcdee` doc-only pass; binary hashes from RC-03 freeze `dceaabc`)

Literal record of the release-binary rebuild performed during RC-10.
Per the project's test-evidence-literalism rule, this file records
what actually ran on this host — not what the build "should" do.

---

## 1. Build command

```
cargo build --release -p mai-api --bins
```

`mai-ship-validate` is a `[[bin]]` inside the `mai-api` package
(`mai-api/Cargo.toml:82-84`, `path = "src/bin/mai_ship_validate.rs"`),
not a separate workspace member. `--bins` builds the `mai-api`
default binary plus the `mai-ship-validate` binary in the same
compilation unit.

## 2. Build environment

| Field | Value |
|---|---|
| Toolchain | rustc 1.95.0 / cargo 1.95.0 |
| OS | Windows 11 Home (build 26200) |
| Target triple | x86_64-pc-windows-msvc |
| Working directory | `mai/` (main checkout, not the RC-10 worktree, to reuse the 67.6 GB `target/` from prior incremental builds) |
| HEAD at build | `059a6e3` (origin/main) |
| Working tree state | clean |

## 3. Timing

| Phase | Value |
|---|---|
| Start | 2026-05-24T20:00:35-07:00 |
| End | 2026-05-24T20:04:29-07:00 |
| Wall clock | **3 min 53 s** |
| Cargo summary | `Finished `release` profile [optimized] target(s) in 3m 53s` |

Faster than RC-03's first-run 3 m 14 s claim was on a fresh tree;
this build was incremental on a warm `target/` directory and only
needed to recompile `mai-core` → `mai-vault` → `mai-compliance` →
`mai-hil` → `mai-adapters` → `mai-scheduler` → `mai-api` after the
J-08 / J-13 changes. No new crate downloads.

## 4. Artefacts and hashes

| Binary | Size | SHA-256 (lowercase, POSIX) |
|---|---|---|
| `mai-api.exe` | 9.96 MB | `c2f3f0606179a5e947a249902c0d405f10024c106c311e897bf5a7e50de7138a` |
| `mai-ship-validate.exe` | 1.67 MB | `bf350b03f59f977314e358598deb680d5684e1400268e26c5a83e7b39dee64ab` |

Both binaries staged into `Island-Mountain-RC1-release/MAI-Lamprey-RC1/bin/`
with a `SHA256SUMS` file at the same path carrying the two lines above.

## 5. Hash delta vs RC-03 / RC1.1-docs

Both binaries DIFFER from the RC-03 / RC1.1-docs build at `dceaabc`:

| Binary | RC-03 / RC1.1-docs hash | RC1.2 hash | Delta source |
|---|---|---|---|
| `mai-api.exe` | `4e201a8498d3e46361c83fc4eff6e04c1021fca3187b04a4d9f55f398b1462b6` | `c2f3f0606179a5e947a249902c0d405f10024c106c311e897bf5a7e50de7138a` | J-08 (`606e821` error-path handlers) + J-13 (`99bfd5a` `/v1/health/system`) touched `mai-api/src/`; other J-sessions did not |
| `mai-ship-validate.exe` | `a32ddc2891a7690cb015a9d1ed06cb84d4160f92976e61ac50cb14069e9ae8f8` | `bf350b03f59f977314e358598deb680d5684e1400268e26c5a83e7b39dee64ab` | linked against the updated `mai-api` package; J-08 / J-13 propagate through the shared crate |

Size delta is minor (`mai-api.exe` 9.9 → 9.96 MB, `mai-ship-validate.exe`
1.7 → 1.67 MB). No new dependencies in `mai-api`'s build graph
between `dceaabc` and `059a6e3` (J-16 added `reqwest` to `mai-sdk-rs`
only, which is a separate workspace member that `mai-api` does not consume).

## 6. Warnings and errors

`Finished `release` profile [optimized] target(s) in 3m 53s`.
**Zero warnings, zero errors** in the cargo output. Pre-build linting
(`cargo fmt --check`, `cargo clippy --workspace -- -D warnings -A clippy::pedantic`)
was NOT run in this session; it was last run as part of each J-session's
quality gates per `workflow_quality_gates_fast_check` memory.

## 7. What was NOT exercised in RC-10's build

Per the test-evidence-literalism rule:

- **No Linux glibc build.** RC1.2 ships Windows MSVC binaries only,
  same as RC1.1-docs. A Linux re-issue is RC2 work.
- **No release-stripped or signed binaries.** Stripping / Authenticode
  signing is RC2 / Production Appliance territory.
- **No `cargo fmt --check` or `cargo clippy --workspace -- -D warnings -A clippy::pedantic`
  in this session.** Each J-session ran these before push; not re-run for RC-10.
- **No `cargo build --release` cold-cache rebuild.** This was an
  incremental build on top of the pre-existing 67.6 GB `target/`.
  A fresh-clone build is expected to take ~6-8 min based on RC-03
  data (`3m 14s` clean) plus the new `reqwest` transitive deps
  that landed in J-16.
