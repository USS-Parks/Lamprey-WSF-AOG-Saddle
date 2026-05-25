# RC1.2 Bundle Assembly Notes

**Project:** Island Mountain MAI + Lamprey
**Release:** RC1.2 (post-DOUGHERTY re-bundle, successor to RC1.1-docs)
**Date of assembly:** 2026-05-24
**Freeze commit:** `059a6e3` (Merge DOUGHERTY lane to main)
**Bundle location:** `Island-Mountain-RC1-release/MAI-Lamprey-RC1/` (the previous RC1.1-docs assembly preserved alongside as `MAI-Lamprey-RC1-v1.1/`)
**Build host HEAD at assembly time:** `059a6e3` (clean)
**Plan reference:** [`RC1.2-REBUNDLE-CHECKLIST.md`](RC1.2-REBUNDLE-CHECKLIST.md) and [`COGENT-DEPLOYMENT-ROADMAP.md`](COGENT-DEPLOYMENT-ROADMAP.md) Session RC-10
**Predecessor:** [`RC1-BUNDLE-NOTES.md`](RC1-BUNDLE-NOTES.md) (RC-08, RC1 v2 assembly at `dceaabc`)

This document is a literal record of the RC-10 packaging pass.
Per the test-evidence-literalism rule, it distinguishes "bundle
exists" from "bundle has been tested" and names what was not done.

---

## 1. What changed vs RC1.1-docs

The RC1.1-docs assembly (commit `a6fa65e` re-roll on top of `b0fcdee`)
shipped the `dceaabc` freeze with doc-only patches. RC1.2 advances
the freeze to `059a6e3` to incorporate the full DOUGHERTY lane:

- 26 J-tagged sessions (`6621c02` J-01 ... `9d68ab0` J-15)
- The mai-sdk-rs HTTP + SSE pass that closed KNOWN-ISSUES Issue 15
- The DOUGHERTY response doc + RC1.2 checklist + GITDOCTOR-75 lane scaffold
- The rescan source PDF and the J-14 evidence directory

Binary hashes therefore change (see [`RC1.2-BUILD-NOTES.md`](RC1.2-BUILD-NOTES.md) §5).
Bundle file count grows from 670 to **808**.

## 2. Bundle location and size

| Item | Value |
|---|---|
| Path | `Island-Mountain-RC1-release/MAI-Lamprey-RC1/` |
| Total size, uncompressed | **24.7 MB** (was 19 MB in RC1.1) |
| Total file count | **808** (per `CHECKSUMS.txt`) |
| Top-level layout | `README-FIRST.md`, `bin/`, `source/`, `test-evidence/`, `CHECKSUMS.txt` |

Size breakdown:

| Entry | Size | Files | Contents |
|---|---|---|---|
| `source/` | 12.6 MB | 784 | filtered `mai/` workspace at `059a6e3` |
| `bin/` | 11.6 MB | 3 | `mai-api.exe`, `mai-ship-validate.exe`, `SHA256SUMS` |
| `test-evidence/` | 186 KB | 20 | `rc-05/` + `rc-06/` + `dougherty-rescan/` |
| `README-FIRST.md` | 13 KB | 1 | canonical first-run guide, mirrored at `source/docs/README-FIRST.md` |
| `CHECKSUMS.txt` | 84 KB | 1 | SHA-256 of every file in the bundle, except itself |

Size growth vs RC1.1 is driven by:
- 5.9 MB of John's GitDoctor screenshots are now in
  `source/test-evidence/dougherty-scan-2026-05-24/` because they
  were committed by Basho in `77e0759` (post-RC1.1).
- 48 KB rescan PDF in `source/docs/`.
- New GITDOCTOR-75 lane plan + roster (273 + 521 lines).
- New response doc + checklist + 26 J-session commits' worth of
  test files, adapters, lock files, and Dockerfile.

## 3. Assembly recipe executed

The RC-08 recipe applied verbatim except step 7 (no need to copy
RC1 docs into `source/docs/` — they are all tracked in the working
tree at `059a6e3`, so `git archive` already grabs them).

| Step | Command | Result |
|---|---|---|
| 1. Rename RC1.1 artefacts | `Move-Item MAI-Lamprey-RC1 -> MAI-Lamprey-RC1-v1.1` (folder + tar.gz + zip + SHA256SUMS) | 4 renames, RC1.1 preserved for audit |
| 2. Make staging | `mkdir -p MAI-Lamprey-RC1.2-staging/{source,bin,test-evidence}` | 3 empty subdirs |
| 3. Extract source via tempfile (PS binary-pipe workaround) | `git archive --format=tar -o $tmp 059a6e3; tar -x -f $tmp -C staging/source/` | 13.6 MB tar, 788 files extracted, 12.9 MB on disk |
| 4. Remove `et HEAD` | `Remove-Item source/'et HEAD'` | gone |
| 5. Remove `.claude/` | `Remove-Item source/.claude -Recurse` | gone (2 files: CLAUDE.md + skills/safe-edit/SKILL.md) |
| 6. Remove pytest cache | `Remove-Item source/pytest-cache-files-* -Recurse` | gone (1 file: nodeids) |
| 7. Copy README-FIRST.md to top | `Copy-Item source/docs/README-FIRST.md README-FIRST.md` | 13 KB |
| 8. (SKIP RC-08 step 7 — RC1 docs already tracked) | n/a | n/a |
| 9. Copy binaries | `Copy-Item target/release/{mai-api,mai-ship-validate}.exe bin/` | 11.6 MB |
| 10. Per-binary SHA256SUMS | `Get-FileHash ... > bin/SHA256SUMS` (lowercase, POSIX `*` format) | 2 lines |
| 11. Mirror test-evidence at top | `Copy-Item test-evidence/{rc-05,rc-06,dougherty-rescan} bundle/test-evidence/` | 20 files, 186 KB |
| 12. Rename staging to canonical | `Move-Item MAI-Lamprey-RC1.2-staging MAI-Lamprey-RC1` | OK after one-shot retry |
| 13. Top-level CHECKSUMS.txt | sorted Get-FileHash over 808 files | 84 KB, 808 lines, 11.5 s wall |
| 14. tar.gz archive | `tar -czf MAI-Lamprey-RC1.2.tar.gz MAI-Lamprey-RC1` (cd into release dir) | 11.51 MB, 1.1 s |
| 15. zip archive | `Compress-Archive -CompressionLevel Optimal` | 11.94 MB, 10.5 s |
| 16. External SHA256SUMS | written to `Island-Mountain-RC1-release/SHA256SUMS` | 2 lines covering both archives |

## 4. Archive hashes (canonical)

The **external** `Island-Mountain-RC1-release/SHA256SUMS` is authoritative
(per the RC1.1 self-reference precedent). Snapshot:

| Archive | Size | SHA-256 (lowercase) |
|---|---|---|
| `MAI-Lamprey-RC1.2.tar.gz` | 11.51 MB | `f637b99bbbca3d34fc450576c56c4626377e0539ecb70640b0fbafe3f1b91caf` |
| `MAI-Lamprey-RC1.2.zip` | 11.94 MB | `d56ef62390dde467bdd89b10e77916188483d3913abbb86e66eb75a00ab70a7d` |

These supersede the RC1.1 hashes:

| Archive | RC1.1 SHA-256 (stale) |
|---|---|
| `MAI-Lamprey-RC1-v1.1.tar.gz` | `35ada78f66f57901c1c3a438709712cbf0e8f43f60e5b8383eb2343c4a66c76a` |
| `MAI-Lamprey-RC1-v1.1.zip` | `6200c1ccfcd25132e417c03f465eef474ccf35cbd9a8e063256f0089d3ccee84` |

The RC1.1 archives are preserved at the same release dir with the
`-v1.1` suffix and their hashes copied into `SHA256SUMS-v1.1` so the
history is auditable.

## 5. Anti-exclusion sweep (manifest §4)

Same 10-pattern sweep as RC-08, all clean:

```
OK: no 'target'
OK: no '__pycache__'
OK: no '.pytest_cache'
OK: no '.mypy_cache'
OK: no '.ruff_cache'
OK: no 'et HEAD'
OK: no '.claude'
OK: no 'pytest-cache-files'
OK: no '.tmp'
OK: no '.tmp-ship08'
```

The four tracked-but-excluded items from RC-06 friction analysis
(`et HEAD`, `.claude/CLAUDE.md`, `.claude/skills/safe-edit/SKILL.md`,
`pytest-cache-files-txhvvf0c/v/cache/nodeids`) were extracted by
`git archive` as expected and then deleted in steps 4-6.

## 6. What was NOT done in RC-10

Per the test-evidence-literalism rule, this section is load-bearing:

- **The bundle was not unpacked and re-tested.** RC-06 was the
  rehearsal; no second rehearsal happened for RC1.2. RC-11's tester
  re-test (sending the bundle back to John) is what closes that loop.
- **No fresh full-workspace cargo test re-run.** Each J-session
  ran its own targeted tests before push; no `cargo test --workspace`
  was executed at `059a6e3` in RC-10. See [`RC1.2-TEST-EVIDENCE.md`](RC1.2-TEST-EVIDENCE.md).
- **No cross-host transfer was exercised.** Bundle lives on the same
  disk as the build host. Tarball/zip transmission, archive integrity
  across a network path, and unpacking on a different user account
  are RC-11's concern.
- **No `.git/` history included.** Same as RC-08 (`git archive` not
  `git clone`). A "with `.git/`" reissue is a 50-150 MB delta if
  John or another reviewer asks.
- **No Linux glibc binaries.** RC1.2 is Windows MSVC only. Linux is RC2.
- **No model weights.** Manifest §4.4 — out of scope.
- **No GPG / Authenticode signing.** SHA-256 integrity only.
- **No 72-hour burn-in evidence carried into the bundle.** SHIP-14
  tooling present under `source/scripts/burn-in-72h.{sh,ps1}` +
  `source/mai-api/src/ship/burn_in.rs`; no signed endurance report
  in `test-evidence/`. Matches RC-05 / RC-08 posture.

## 7. Acceptance vs RC-10 criteria

| Criterion | Result |
|---|---|
| Bundle rebuilt at the post-DOUGHERTY freeze | Yes — `059a6e3`, see §1 |
| Binary hashes refreshed and published | Yes — §4 of `RC1.2-BUILD-NOTES.md` |
| External `SHA256SUMS` updated | Yes — §4 above |
| RC1.1 artefacts preserved for audit | Yes — `-v1.1` suffix |
| Manifest conformance maintained | Yes — §5 anti-exclusion sweep clean |
| RC1-TESTER-FEEDBACK.md §2 updated | Yes — see commit message |

RC-11 (re-ship to John) is now unblocked.
