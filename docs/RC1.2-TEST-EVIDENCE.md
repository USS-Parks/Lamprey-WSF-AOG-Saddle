# RC1.2 Test Evidence

**Project:** Island Mountain MAI + Lamprey
**Release:** RC1.2
**Freeze commit:** `059a6e3`
**Predecessor evidence:** [`RC1-TEST-EVIDENCE.md`](RC1-TEST-EVIDENCE.md) (RC-05 at `dceaabc`, 1 717 pass / 0 fail / 2 ignored)
**Date:** 2026-05-24
**Session:** RC-10

Per the test-evidence-literalism rule, this file records what was
actually exercised at the new freeze and what was not. It does
**not** repackage RC-05's claims as if they applied here.

---

## 1. What was exercised in RC-10

| Pass | Detail |
|---|---|
| Release binary build at `059a6e3` | `cargo build --release -p mai-api --bins`, 0 warnings 0 errors, 3 min 53 s. See [`RC1.2-BUILD-NOTES.md`](RC1.2-BUILD-NOTES.md). |
| Bundle assembly + checksum sweep at `059a6e3` | `git archive` + RC-06 exclusion sweep + 808-file `CHECKSUMS.txt` + tar.gz + zip + external `SHA256SUMS`. Recipe verbatim per [`RC1.2-BUNDLE-NOTES.md`](RC1.2-BUNDLE-NOTES.md) §3. |
| Per-J-session test passes during the DOUGHERTY lane | Each J-session (J-01..J-26 + J-10b + J-14 + J-15) ran its own targeted tests before push. See per-session commit messages (`git log 6621c02^..059a6e3`). Examples: J-09 grew assertion counts 14 → 58 / 13 → 64; J-10 added the `tests/integrity/test_assertion_gate.py` CI gate; J-12 ran 539 pytest pass / 65 skip across `adapters/`; J-13 added 2 integration tests in `mai-api/tests/health_system_j13.rs`; J-16b added 18 wiremock tests in `mai-sdk-rs/tests/http_client.rs`; J-17 added 7 wiremock tests in `mai-sdk-rs/tests/streaming.rs`. |
| Self-review test pass at RC-09 | 6/6 `compliance_demos`, 3/3 `compliance_perf` (composer P99 300 ns / audit 119 494/s / report 1.687 ms — see [`RC1-SELF-REVIEW-TRACK-C.md`](RC1-SELF-REVIEW-TRACK-C.md) §1.1). |

## 2. What was NOT exercised in RC-10

Per the test-evidence-literalism rule, this section is load-bearing.

| Not exercised | Why / where it happens |
|---|---|
| Fresh `cargo test --workspace --no-fail-fast` at `059a6e3` | RC-05 ran the equivalent at `dceaabc` (1 539 pass / 0 fail / 2 ignored, 5 min 30 s). RC-10 is a packaging session; full re-run deferred to RC-11 (tester re-test). |
| Fresh `cargo test -p mai-compliance --test compliance_perf --release` | RC-05 + RC-09 self-review both ran this; composer P99 between 300 ns and 600 ns, audit 119 494 – 127 929/s, report 1.588 – 1.687 ms. None re-run at `059a6e3` in RC-10. |
| Fresh Python pytest at `059a6e3` | RC-05 ran 94 SDK + 20 dashboard + 61 scaffold = 175 pass. Adapter pytest grew during the DOUGHERTY lane (J-12 reported 539 pass / 65 skip across `adapters/`). Not re-run at the merged freeze in RC-10. |
| 72-hour burn-in evidence | SHIP-14 driver present at `source/scripts/burn-in-72h.{sh,ps1}` and `source/mai-api/src/ship/burn_in.rs`. No signed endurance report has been produced at any freeze. Matches RC-05 / RC-08. |
| GPU runtime paths | No `nvidia-smi` on the Windows build host; flat-topology fallback used in earlier passes. RC-10 did not introduce GPU coverage. |
| Linux glibc target | RC1.2 is Windows MSVC only. Linux re-issue is RC2. |
| Real vault / real regulated data | `StubVault` + `NullSealer` defaults remain. Production wires happen at acquirer integration time per `BUYER-INTEGRATION-GUIDE.md`. |
| Network exposure | `127.0.0.1` only. No firewall-traversal or remote-host coverage. |
| Bundle re-extract and verbatim README-FIRST walk | RC-06 was the rehearsal at `dceaabc`. RC-10 did not repeat the walk at `059a6e3`. RC-11 is what re-tests on an outside machine. |
| External scanner re-run at `059a6e3` | J-14 (`b899a84`) is the rescan; it was run at `8d412c6` (J-17 close), one commit before the merge `059a6e3`. No additional changes to scanned code between those points — `b60e007` is docs-only and `059a6e3` is a merge commit. The J-14 SUMMARY at [`test-evidence/dougherty-rescan/SUMMARY.md`](../test-evidence/dougherty-rescan/SUMMARY.md) is the canonical external-scan result for RC1.2. |

## 3. Confidence statement

RC1.2's posture is: every code change in scope was tested at its
J-session commit; the merge to `059a6e3` is mechanical (FF on
the J-15 chain plus a 1-conflict merge resolved on documentation).
No code change landed in the merge commit itself. The release
binaries built cleanly at `059a6e3` with zero warnings. The bundle
manifest sweep is clean.

What this does NOT prove: that the merged-state workspace passes
its full test suite at `059a6e3` in a single re-run. That assertion
is owed to RC-11's tester re-test, where John (or any Track B
reviewer) runs `cargo test --workspace` on a fresh machine against
the bundle.

If a tester re-runs `cargo test --workspace` against the RC1.2
bundle and any test fails, that failure is a real RC1.2 finding —
it would not be a regression from RC-05 (different freeze, different
test surface), but a new RC1.2 issue to triage in RC-12.
