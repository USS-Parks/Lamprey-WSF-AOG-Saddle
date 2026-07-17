# Saddle Seed Reconciliation Report

**Date:** 2026-07-16

**Purpose:** Resolve the published-versus-local Mighty Eel OS seed state far enough to choose a safe import procedure for the independent Saddle repository.

**Result:** Neither currently named seed SHA is eligible as the approved import pin. The local T5 implementation is a verified transplant candidate onto the latest published baseline, but it is not itself the complete or published seed state. T6 and the remaining hardening prompts require explicit disposition.

## 1. Authority and Scope

This report supports `SAD-01` in `SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`. It is a read-only reconciliation artifact, not STS authorization and not approval to commit, push, import, or deploy.

The authoritative hardening records inspected were:

- `PLANNING/LAMPREY-SADDLE-WSF-AOG-SECURITY-HARDENING-PSPR.md` in the Mighty Eel OS workspace;
- `docs/sessions/LAMPREY-SADDLE-HARDENING-DEVLOG.md` in the seed repository; and
- the current Git state of the seed repository and its `mai-LSH-1` and `ci-recovery-20260716` worktrees.

## 2. Observed Git State

| Ref or worktree | SHA | Relationship and meaning | Import eligible? |
|---|---|---|---:|
| Seed `origin/main` | `df119fb6321e60e8cfffc1b36281ba95f9f5004a` | Published T4 lineage plus five later CI, Raft-lifecycle, and repository-identity repair commits | No; inventory baseline only |
| Seed local `main` | `6b8118975d6e17a1e4e1c7458c8c2594516c224b` | One T5 commit based directly on the older T4 checkpoint `7e256b6`; ahead 1 and behind 5 versus `origin/main` | No; local-only and omits published repairs |
| `session/LSH-1` | `01dfba2e0afd73067df941db01c810b1fa4a79de` | Older G1/G2 closeout branch | No; superseded for seed selection |
| `ci-recovery-20260716` | `df119fb6321e60e8cfffc1b36281ba95f9f5004a` | Clean worktree at published `origin/main` | Useful inventory checkout only |

The merge base of local `main` and `origin/main` is `7e256b6f8eaf969970a2bcad8e8bb204f2b3b88f`. The divergence is exactly one local commit versus five published commits.

## 3. T5 Commit Assessment

Commit `6b8118975d6e17a1e4e1c7458c8c2594516c224b`, `Authenticate and bind approval decisions`, changes:

- `Cargo.lock`;
- `crates/aog-approvals/Cargo.toml`;
- `crates/aog-approvals/src/lib.rs`;
- `crates/aog-conformance/tests/robustness_conformance.rs`;
- `crates/aog-toolproxy/src/lib.rs`;
- `crates/aog-toolproxy/src/receipt.rs`; and
- `docs/sessions/LAMPREY-SADDLE-HARDENING-DEVLOG.md`.

The commit contains the required footer exactly:

`Authored and reviewed by Basho Parks, copyright 2026`

An embedded SSH signature with fingerprint `SHA256:PE4Wpbp27IeZC6y4dd97YDNLiFrDvky2KOWSqvdkTEc` was observed. The sandbox could not read the user's `allowed_signers` file, so signer trust was not independently established in this run; Git reported signature status `U` rather than a verified-good trust result.

### 3.1 Mergeability

A three-way merge of T5 onto `df119fb…` found:

- all six code/manifest files merge without conflict; and
- only `docs/sessions/LAMPREY-SADDLE-HARDENING-DEVLOG.md` conflicts, because the published lane appended the CI recovery checkpoint after the common T4 base while T5 appended its own execution record at the same location.

The ledger conflict is semantic bookkeeping, not a code conflict. It must be resolved by preserving the full published CI-recovery record and appending the T5 record with corrected implementation and remote-checkpoint SHAs. Selecting either side wholesale would destroy valid history.

### 3.2 Integrated Verification

The T5 code patch was applied without committing to a disposable clone at `df119fb…`. The conflicting DEVLOG change was omitted for code verification. The resulting six-file code/manifest diff passed:

| Gate | Result |
|---|---|
| `cargo test -p aog-toolproxy -p aog-approvals` | PASS: 62 toolproxy tests, 6 approval tests, and doc tests |
| `cargo test -p aog-conformance --test robustness_conformance` | PASS: 11/11 |
| `cargo test -p aog-controller --test managed_toolproxy` | PASS: 1/1 |
| `cargo clippy -p aog-toolproxy -p aog-approvals -p aog-conformance -p aog-controller --all-targets -- -D warnings -A clippy::pedantic` | PASS |
| `cargo fmt --check` | PASS |
| `git diff --cached --check` | PASS |

This proves that the T5 code is compatible with the five published post-T4 repair commits for the tested scope. It does not replace full workspace, live-system, hardening-closeout, or Saddle-independent-repository gates.

## 4. T6 and Remaining Hardening State

The hardening PSPR and DEVLOG agree that T6 is the final M3 prompt. Current source inspection confirms the production seam is absent:

- `CredentialMinter` exists as a trait in `aog-toolproxy`;
- all discovered `CredentialMinter` implementations and `.with_minter(...)` compositions are test fixtures inside `aog-toolproxy`;
- `ApprovalInbox` and `InboxGate` exist in `aog-approvals`, but no production caller composes the complete verified caller, live credential authority, approval, executor, and receipt path; and
- the T6 live matrix for benign, injected, mutating, concurrent, cancelled, oversized, and secret-bearing calls has not run.

M3 is therefore open even after T5 is transplanted. The hardening plan also retains M4 `LSH-D1` through `LSH-D5` and M5 `LSH-X1` through `LSH-X6`. Its own governance forbids repository-wide closure until at least D5 and X4 close the remaining coverage.

These prompts do not need to disappear before Saddle can own the source, but every one must have an explicit disposition: close in the seed, transfer to a named Saddle prompt and acceptance gate, or remain a documented external prerequisite. Silent omission is forbidden.

## 5. Seed-Pin Decision

| Candidate | Decision | Reason |
|---|---|---|
| `df119fb…` | Reject as final pin | Published and internally coherent, but omits verified T5 work and leaves the ledger saying T5 is next. |
| `6b81189…` | Reject as final pin | Contains T5 but is local-only and omits five published repair commits. |
| `df119fb…` plus the T5 code patch | Conditional integration candidate | Targeted gates pass; the DEVLOG must be merged honestly and the integrated result committed, published, and reverified. |
| A new published SHA after reconciliation | Required final form | Must contain both post-T4 repairs and T5, record exact ledger state, and explicitly close or carry T6 plus D1-D5/X1-X6. |

### Recommended sequence

1. Start from the current published seed `origin/main`, not local `main` and not `session/LSH-1`.
2. Transplant the T5 commit, resolving only the DEVLOG conflict by preserving both histories.
3. Re-run the exact T5 gates, the relevant post-T4 CI/Raft gates, full workspace gates appropriate to the seed, and signature/footer checks.
4. Publish the integrated T5 implementation and exact-SHA ledger closeout under the seed repository's own authorization rules.
5. Prefer completing T6 before freezing the import. If ownership is deliberately transferred instead, record T6 as a blocking Saddle bridge/conformance item with its full original live gate; do not downgrade it to a unit-test task.
6. Record D1-D5 and X1-X6 in the Saddle carry-forward ledger unless they close first.
7. Select the resulting published remote SHA as the sole immutable import candidate and regenerate all source counts, dependency closure, path dispositions, and hashes from that Git object.

## 6. SAD-01 Acceptance State

`SAD-01` is **not complete** because no immutable SHA has been approved. This report does close the ambiguity analysis:

- the correct integration base is `df119fb…`;
- the T5 payload is `6b81189…` and is compatible with that base for all prescribed targeted gates;
- the only merge conflict is the DEVLOG append point;
- T6 is a real absent production seam, not merely stale documentation; and
- M4/M5 open prompts are enumerated for mandatory disposition.

No tracked source may be imported from a working directory or from the disposable verification clone. The eventual import source remains one approved, published Git commit object.

## 7. SAD-01 Resolution — 2026-07-17

This addendum supersedes only the incomplete acceptance conclusion in §6 while
preserving the 2026-07-16 reconciliation evidence. The required reconciliation
was completed in the seed repository: T5 was transplanted onto the published
baseline and reverified, then T6's production tool-governance path passed its
live OpenBao and full workspace gates.

The approved immutable import pin is published seed `origin/main` commit
`fedf005a30ad388ab156dc8bd693a3aa3f0702ea`. It has a good SSH signature and
the exact canonical footer. The prior local-only `6b81189…` candidate and the
earlier published `df119fb…` inventory baseline remain rejected as import pins.

The complete SAD-01 decision, signature evidence, and non-downgrade mapping for
every open `LSH-D*` and `LSH-X*` prompt are recorded in
`SADDLE-SEED-CHECKPOINT-2026-07-17.md`. `SAD-02` must derive the full coverage
ledger from this Git object; no working-tree materialization is permitted.
