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
| Commit footer | PASS | `d506e80aee79717b1a48817d471ce9e89ca934c2` ends with the exact canonical footer. |
| Remote checkpoint | PASS | Target `main` advanced from `c5e6fc7cc4f1a9a82456e36914e4cb146df26b37` to `d506e80aee79717b1a48817d471ce9e89ca934c2`. |

## SAD-03

**State under test:** source pin `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`,
the corrected SAD-02 ledger, and the isolated 898-path staged-import simulation.

| Evidence | Result | Notes |
|---|---|---|
| Seed binding | PASS | Clean checkout required at the full approved source SHA. |
| Source-blob verification | PASS | Every allowlisted path's mode, Git object, byte size, and SHA-256 matched the SAD-02 ledger. |
| Archive and staged index | PASS | Deterministic temporary archive hashed to `e07a17ab4ab682aa912aa7fb4e15ca748788e8dfaa26523578f9ca963790d117`; isolated raw-blob index tree is `6f963caa9c5cdf44fe07f53cf48af4798ba21065`. |
| Forbidden-path boundary | PASS | Private-key paths, non-placeholder `.env`, generated cache, runtime state, symlink, and submodule material are absent. |
| Gitleaks | PASS | Strict default rules report zero unsuppressed findings; 49 baseline SHA-1 detector digests were validated before narrow baseline exclusion. |
| Independent static detector | PASS | 898 paths scanned with zero unsuppressed findings. |
| Reviewed synthetic fixtures | PASS | Exact path/rule/line/fingerprint exception files contain reasons; the sole path omission is separately validated detector-baseline metadata. |
| Runtime material generator | PASS | Disposable CA/server/client material generated; `openssl verify` accepted both leaf certificates; private output removed after test. |
| SAD-02 regeneration | PASS | Corrected manifest deterministically regenerated and verified at 1,491 tracked paths, 1,008 candidates, and 37 closure packages. |
| Commit footer | PASS | `bbb19934c7b1866c44d8719c00fc575b09b43988` ends with the exact canonical footer. |
| Remote checkpoint | PASS | Target `main` advanced from `9ccc4ea5cbdae16274e2163b2cafc4992a474cc1` to `bbb19934c7b1866c44d8719c00fc575b09b43988`. |

## SAD-10

**State under test:** clean pinned seed `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`,
the SAD-02 source ledger, and the initial Saddle native workspace cut.

| Evidence | Result | Notes |
|---|---|---|
| Seed-tree provenance | PASS | Every selected raw path matched the ledger's Git object, mode, byte size, and SHA-256 at the pinned seed. |
| Native closure materialization | PASS | 391 raw blobs plus the adapted root `Cargo.toml` and path-scoped preservation policy produced 393 workspace paths for the recorded 37-package closure. |
| Root workspace adaptation | PASS | Only the workspace member list changed: 48 seed members narrowed to the 37 approved closure members; source and target hashes are retained in the proof. |
| Source-preservation policy | PASS | `.gitattributes` suppresses trailing-space checks only for the imported seed-authentic mixed-line-ending block in `mai-core/src/power/demotion.rs`. |
| Toolchain and license source fact | PASS | The pinned seed has no root toolchain or license file; no license was invented during SAD-10. |
| Reproducibility | PASS | The materializer's verify-only pass accepted every materialized file and the deterministic evidence record. |
| Cargo metadata | PASS | `cargo metadata --format-version=1 --no-deps --locked` resolved exactly 37 recorded packages with zero external local paths. |
| Commit footer | PASS | `850628da4cffc92fc17e22811377a7c8eece1101` ends with the exact canonical footer. |
| Remote checkpoint | PASS | SAD-10 published in the combined implementation checkpoint `93f2d2f7fb9cba29e27a3bf57fe5554a58de97da`. |

## SAD-11

**State under test:** clean pinned seed `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`,
the SAD-02 source ledger, the verified SAD-10 native closure, and the staged
Saddle support/documentation/evidence cut.

| Evidence | Result | Notes |
|---|---|---|
| Seed-tree provenance | PASS | The materializer checked every SAD-11 raw path against its pinned-seed Git object, mode, byte size, and SHA-256. |
| Support-surface materialization | PASS | 492 raw blobs: 242 remaining direct imports and 250 historical-evidence records. |
| Ledger coverage | PASS | SAD-10 plus SAD-11 materialize all 885 `import` and `historical-evidence` ledger paths; zero missing and zero unexpected paths. |
| Canonical README boundary | PASS | Saddle retains its existing README; the superseded source README is recorded as an adaptation, not copied. |
| Historical-status boundary | PASS | The generated historical-status notice and six Saddle-owned boundary records make no Saddle completion, release, security, or production claim. |
| Source whitespace preservation | PASS | `.gitattributes` is generated from the 52 verified raw blobs requiring a path-specific exception; authored paths retain normal whitespace checks. |
| Reproducibility | PASS | Materializer write and verify-only passes both accepted the deterministic SAD-11 evidence record. |
| `git diff --cached --check` | PASS | Final staged SAD-11 tree reported zero whitespace violations. |
| Staged no-slop gate | PASS | Explicit Git for Windows Bash pre-commit hook reported `no-slop: clean (staged)`. |
| Full no-slop gate | PASS | Explicit Git for Windows Bash pre-push hook reported `no-slop: clean (full)`. |
| Commit footer | PASS | `93f2d2f7fb9cba29e27a3bf57fe5554a58de97da` ends with the exact canonical footer. |
| Remote checkpoint | PASS | Target `main` advanced from `0b83c81ef3a7d92973d2fdb35be74d31b2558ee2` to `93f2d2f7fb9cba29e27a3bf57fe5554a58de97da`. |

## SAD-12

**State under test:** the staged independent workspace after parent-coupling
removal, including the closure-specific offline lockfile regeneration.

| Evidence | Result | Notes |
|---|---|---|
| Parent-reference scan | PASS | Deterministic verifier examined 913 tracked paths and 609 active executable/configuration paths; zero forbidden parent references. |
| Cargo path dependencies | PASS | All tracked Cargo `path` dependencies resolve within Saddle; zero external local paths. |
| Git topology | PASS | Zero submodule tree entries, zero `git submodule status` entries, and zero tracked symlinks. |
| Lockfile closure | PASS | Offline regeneration produced the 37-package closure lockfile; the clean archive accepts `--locked`. |
| Clean archive topology | PASS | Exact staged tree `2b84b274fa9435db46bd6bb96984c20e8ad9a1c0` extracted outside parent workspaces had no `.git` entry, reparse point, or active forbidden reference. |
| Clean Cargo metadata | PASS | `cargo metadata --format-version=1 --no-deps --locked` reported 37 packages, 37 workspace members, and zero external local paths. |
| Clean Cargo check | PASS | `cargo check --workspace --locked` completed from the clean archive. |
| Supply-chain script syntax | PASS | Git for Windows Bash accepted `deployment/supply-chain/sign.sh` with `bash -n`. |
| `git diff --cached --check` | PASS | Final staged SAD-12 tree reported no whitespace violations. |
| Staged no-slop gate | PASS | Explicit Git for Windows Bash pre-commit hook reported `no-slop: clean (staged)`. |
| Full no-slop gate | PASS | Explicit Git for Windows Bash pre-push hook reported `no-slop: clean (full)`. |
| Commit footer | PASS | `0f2dfdf87539736984d59b15dd038982e46d9c06` ends with the exact canonical footer. |
| Remote checkpoint | PASS | Target `main` advanced from `40fc7ce9328d56c335a1e9fe09d1def37fec0593` to `0f2dfdf87539736984d59b15dd038982e46d9c06`. |

## SAD-13

**State under test:** the independently materialized, 37-package Saddle
workspace after SAD-12's clean-checkout independence proof.

| Evidence | Result | Notes |
|---|---|---|
| `cargo fmt --check` | PASS | The complete workspace formatting check returned clean. |
| Locked workspace check | PASS | `cargo check --workspace --locked` completed with the configured local `protoc` and Git-for-Windows OpenSSL path. |
| Strict all-target clippy | PASS | `cargo clippy --workspace --all-targets --locked -- -D warnings -A clippy::pedantic` completed without lint failures. |
| Unit/property/integration suite | PASS | `cargo test --workspace --locked` with the configured live OpenBao endpoint reported 187 successful result summaries and zero failures. |
| RustSec and dependency policy | PASS | `cargo audit` and `cargo deny check` completed successfully; deny emitted only non-failing stale-allowance and duplicate-package warnings. |
| Workspace documentation | PASS | `cargo doc --workspace --no-deps --locked` generated documentation for all workspace outputs. Rustdoc diagnostic warnings were emitted for existing intra-doc/link-markup annotations, but the command returned no error. |
| Staged no-slop gate | PASS | Explicit Git for Windows Bash pre-commit hook reported `no-slop: clean (staged)`. |
| Full no-slop gate | PASS | Explicit Git for Windows Bash pre-push hook reported `no-slop: clean (full)` with the worktree trusted for the sandbox ownership boundary. |
| Commit footer | PASS | `2459b5a800493e74afde96adf43bcd5d4fe31d5b` ends with the exact canonical footer. |
| Remote checkpoint | PASS | Target `main` advanced from `c25e7753e00efa3dfd0eb7ea94201561513a9bd0` to `2459b5a800493e74afde96adf43bcd5d4fe31d5b`. |

## SAD-14

**State under test:** the independent Saddle workspace after the bounded
package-closure addendum required by its imported console/deployment gate.

| Evidence | Result | Notes |
|---|---|---|
| Locked console install | PASS | `npm ci` installed 198 committed-lockfile packages with zero npm audit vulnerabilities. |
| Console tests and production build | PASS | `npm run test` reported 23 passing tests; `npm run build` completed Vite's production bundle. |
| Ephemeral trust material | PASS | Generated CA, server, and client certificates verified; private material was deleted from `C:\tmp` immediately after use. |
| Appliance Compose validation | PASS | The demo profile and `docker compose --profile demo ... config -q` passed with shell-only throwaway credentials and no appliance `.env`. |
| CI trust-profile validation | PASS | WSF HA passed production rules; appliance and shadow passed demo rules. |
| Validator and package regressions | PASS | `pytest deployment/appliance/tests/ tools/packaging_tests/ -q`: 128 passed, 1 documented skip. |
| Staging-only package build | PASS | `scripts/build-package.sh --validate-only --skip-dashboard` produced the required temporary package layout. |
| Bounded packaging import | PASS | Separate deterministic proof records 20 original SAD-02 out-of-scope paths, 17 raw blobs, and three repository-identity adaptations. |
| Packaging secret scans | PASS | Gitleaks and the independent secondary scanner both returned zero findings across the new 20-file package surface. |
| Staged independence | PASS | Deterministic verifier recorded 936 tracked paths, 629 active paths, and zero forbidden parent references, external Cargo paths, submodules, or symlinks. |
| Staged no-slop gate | PASS | Explicit Git for Windows Bash pre-commit hook reported `no-slop: clean (staged)`. |
| Full no-slop gate | PASS | Explicit Git for Windows Bash pre-push hook reported `no-slop: clean (full)`. |
| Commit footer | PASS | `e7627a474bb7af8119ae7a7825c5d6146e4ba6c2` ends with the exact canonical footer. |
| Remote checkpoint | PASS | Target `main` advanced from `ecb11f0abbfa9df087d15a12a1cf04f64870138a` to `e7627a474bb7af8119ae7a7825c5d6146e4ba6c2`. |

## SAD-15

**State under test:** a depth-one, clean checkout of published source checkpoint
`62b076ea480894e177f504a4fbea3ec638a54b3c`, outside both parent workspaces.

| Evidence | Result | Notes |
|---|---|---|
| M1 source completeness | PASS | Deterministic reconciliation accepted 885 selected source paths: 870 raw hash matches, five approved transformations, ten non-portable source exclusions, and the 20-path SAD-14 package addendum. |
| Immutable source manifest | PASS | Pinned-seed manifest verification reported 1,491 tracked paths and 1,008 candidates; SHA-256 `eb7e97e405b4eb28e94b469e094e74e3fbd6451657ea69fc5f470b1472130ac4`. |
| License provenance | PASS | Both seed and Saddle root-license checks found zero files; M1 did not invent a licensing decision. |
| No-secret source | PASS | The 898-path tracked-blob proof reported zero unsuppressed Gitleaks and secondary-detector findings; exact 20-path packaging scans also reported zero findings. |
| Fresh independence | PASS | Deterministic verifier reported 631 active paths and zero parent references, external Cargo paths, submodules, or symlinks. |
| Locked Rust gates | PASS | `cargo fmt --check`, 37-package locked metadata/check, strict all-target clippy, 187 successful test summaries with zero failures, audit, deny, and docs all passed. |
| Console, deployment, and package gates | PASS | Locked console install had zero audit vulnerabilities; 23 console tests and build passed; WSF HA/appliance/shadow profiles, Compose config, 128 package regressions plus one documented skip, and isolated package staging all passed. |
| Fresh no-slop policy | PASS | Configured full Git-for-Windows-Bash pre-push hook reported `no-slop: clean (full)` from the fresh checkout. |
| Fresh tree hygiene | PASS | No tracked modifications followed the gate; only the two deliberately generated SAD-15 evidence files were untracked before closeout staging. |
| M1 evidence artifacts | PASS | `m1-completeness-proof.json` SHA-256 `26dd07c7ec860cffd7025165dec9e854106932d6b18bee73d279f37453cfbb7c`; `independence-gate.json` SHA-256 `70022ca187a3b6df85cbd682c5579bf9fb95a679482b809b23c51f452c1f0909`. |
