# Saddle Verification Ledger

This ledger is the command-level verification source for the independent Saddle PSPR. A PASS entry is valid only for the exact revision or pre-commit tree named in the entry.

## Status Vocabulary

- **PASS:** prescribed evidence executed successfully at the named state.
- **FAIL:** prescribed evidence executed and failed.
- **BLOCKED:** external prerequisite unavailable; no completion claim allowed.
- **PENDING:** not yet executed.

## SAD-00

**State under test:** target base `ba665a4a40802f132df729b7abc80350d11a7171` plus the SAD-00 documentation changes.

| Evidence | Result | Notes |
|---|---|---|
| Target remote fetch | PASS | Live `origin/main` resolved to `ba665a4a40802f132df729b7abc80350d11a7171`. |
| Seed remote fetch | PASS | Live seed `origin/main` resolved to `df119fb6321e60e8cfffc1b36281ba95f9f5004a`. |
| Isolated worktree | PASS | `session/SADDLE-STS-1`; initially clean. |
| Toolchain inventory | PASS | Recorded in `SADDLE-TOOLCHAIN.md` and machine-readable evidence. |
| Product source absence | PASS | SAD-00 imports no WSF, AOG, or scheduler source. |
| Local Markdown links | PASS | Zero broken local Markdown links. |
| `git diff --check` | PASS | No whitespace errors. |
| Secret-pattern scan | PASS | PowerShell high-confidence pattern scan and Gitleaks 8.30.1 both report zero findings. |
| Staged no-slop gate | PASS | Repository pre-commit hook run explicitly in Git for Windows Bash. |
| Commit footer | PASS | `d959bf0d8e7e14fdd2c73ff9bf42609a1748bd42` ends with the exact canonical footer. |
| Remote checkpoint | PASS | Remote `main` advanced to `d959bf0d8e7e14fdd2c73ff9bf42609a1748bd42`. |

## SAD-01

**State under test:** target `578d3ab` plus planning and ledger updates that
select the exact source object `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`.

| Evidence | Result | Notes |
|---|---|---|
| Seed remote lookup | PASS | Live `Mighty-Eel-OS` `refs/heads/main` resolved to `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`. |
| Git object identity | PASS | Selected object is a published Git `commit`; no local worktree or branch is the source. |
| Signature and footer | PASS | Git reported a good SSH signature for `basho.parks@gmail.com`, and the exact canonical footer is present. |
| Reconciled T5/T6 lineage | PASS | The selected object follows the T6 implementation checkpoint `5e541e5324269a051d3304e94ae868080d876a25`. |
| Open source hardening disposition | PASS | `LSH-D1`–`LSH-D5` and `LSH-X1`–`LSH-X6` map to named Saddle prompts in `SADDLE-SEED-CHECKPOINT-2026-07-17.md`. |
| Source import absence | PASS | SAD-01 adds only planning and verification records; no WSF/AOG/Saddle product source or runtime data is imported. |
| `git diff --check` | PASS | SAD-01 documentation tree has no whitespace errors. |
| Secret scans | PASS | Gitleaks 8.30.1 and explicit private-key/token/credential-URL checks report zero matches. |
| Staged no-slop gate | PASS | Configured target pre-commit hook reports `no-slop: clean (staged)`. |
| Commit footer | PASS | `7f30ea691f91b3ea8774b7fd121fbc8580b1d69f` ends with the exact canonical footer. |
| Remote checkpoint | PASS | Target `main` advanced from `578d3ab8ae7425d3cd1b3f69bd25f934e7c3485a` to `7f30ea691f91b3ea8774b7fd121fbc8580b1d69f`. |

## SAD-02

**State under test:** target `c5e6fc7cc4f1a9a82456e36914e4cb146df26b37` plus
the deterministic source-manifest generator and its generated evidence.

| Evidence | Result | Notes |
|---|---|---|
| Generator syntax | PASS | Python compiled `tools/generate_saddle_source_manifest.py` without writing bytecode. |
| Seed object binding | PASS | Generator refused any dirty or non-pinned seed checkout and used `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`. |
| Cargo dependency closure | PASS | 33 direct WSF/AOG/fabric/orchestration roots resolve to 37 internal packages. |
| Tracked-object scan | PASS | 1,491 tracked paths and 1,323 source-like paths were examined from Git objects. |
| Per-file hashes and path lists | PASS | JSON ledger records Git object ID, mode, byte count, SHA-256, relevance, disposition, and reason for every path. |
| Candidate disposition | PASS | 1,008 candidates: 636 import, 13 extract, 256 historical evidence, 103 exclude; zero undispositioned. |
| `mai-scheduler` review | PASS | 13 explicit extraction candidates and 38 explicit exclusions across all 51 tracked paths. |
| Submodules and symlinks | PASS | Zero submodules and zero symlinks at the seed pin. |
| Deterministic regeneration | PASS | `--verify` regenerated a byte-for-byte equal manifest. |
| Source import absence | PASS | Target adds only its generator, planning records, and hash ledger; no seed product file is materialized. |
| `git diff --check` | PASS | Final staged SAD-02 tree has no whitespace errors. |
| Secret scans | PASS | Gitleaks 8.30.1 and explicit private-key/token/credential-URL checks report zero matches. |
| Staged no-slop gate | PASS | Configured target pre-commit hook reports `no-slop: clean (staged)`. |
