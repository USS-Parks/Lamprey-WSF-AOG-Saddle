# Saddle Execution DEVLOG

**Initiative:** Independent Kubernetes-level Saddle scheduler/orchestrator bridging WSF and AOG

**Canonical PSPR:** `PLANNING/SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`

**Execution worktree:** `C:\Users\17076\Documents\Claude\Mighty Eel OS\Lamprey-WSF-AOG-Saddle-worktrees\saddle-STS-1`

**Execution branch:** `session/SADDLE-STS-1`

**Target remote:** `https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle.git`

## Authorization

Full STS execution plus commit and push authorization was granted by the owner on 2026-07-17:

> Run the ENTIRE PSPR STS. You have my authorization. Commit and push ALL to main, after validating and verifying greens across the board.

This authorization is durable for every in-scope implementation, verification, ledger closeout, and push required by the PSPR. It does not authorize force-push, history rewriting, deployment, credential rotation, paid services, or unrelated repository changes.

## Execution Rules

- Follow prompt dependency order.
- Do not mark a prompt complete until its prescribed gate passes.
- Use focused commits with the canonical footer.
- Push verified checkpoints to `main`.
- Preserve source provenance and open security status honestly.
- Never import secrets, working-tree-only files, ignored files, private keys, runtime state, or generated credentials.
- Record every command-level gate, result, changed file set, commit SHA, and remote checkpoint here and in `docs/verification/SADDLE-VERIFICATION.md`.

---

## SAD-00 — Bootstrap execution governance

**Status:** PASS — implementation and remote checkpoint `d959bf0d8e7e14fdd2c73ff9bf42609a1748bd42`.

### Initial state

- Initial target HEAD: `ba665a4a40802f132df729b7abc80350d11a7171`.
- Initial target `origin/main`: `ba665a4a40802f132df729b7abc80350d11a7171`.
- Initial branch: `session/SADDLE-STS-1`.
- Initial worktree status: clean.
- Seed `origin/main`: `df119fb6321e60e8cfffc1b36281ba95f9f5004a`.
- Seed local T5 commit: `6b8118975d6e17a1e4e1c7458c8c2594516c224b`.
- Seed merge base: `7e256b6f8eaf969970a2bcad8e8bb204f2b3b88f`.
- Observation time: `2026-07-17T12:30:55Z`.

### Work completed

- Created the isolated execution worktree and branch.
- Created this DEVLOG and the canonical verification ledger.
- Recorded the exact target and seed revisions.
- Recorded the available toolchain and known local tool limitations.
- Updated repository authority files from drafted/not-authorized to active STS execution.
- Preserved the rule that source import begins only after the seed and no-secret gates close.

### Changed files

- `AGENTS.md`;
- `CLAUDE.md`;
- `README.md`;
- `PLANNING/SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`;
- `docs/sessions/SADDLE-DEVLOG.md`;
- `docs/verification/SADDLE-TOOLCHAIN.md`;
- `docs/verification/SADDLE-VERIFICATION.md`; and
- `test-evidence/saddle/SAD-00/toolchain.json`.

### Gate

- isolated worktree created from exact remote main — PASS;
- worktree clean before prompt edits — PASS;
- target HEAD, remote SHA, branch, seed remote SHA, and seed divergence recorded — PASS;
- toolchain record written — PASS;
- no product source imported — PASS;
- Markdown links and whitespace checks — PASS;
- PowerShell secret-pattern scan — PASS, zero matches;
- Gitleaks no-Git working-tree scan — PASS, zero leaks;
- staged no-slop hook through Git for Windows Bash — PASS.

### Next prompt

`SAD-01 — Resolve the authoritative seed checkpoint`.

### Commit state

The SAD-00 implementation was committed as `d959bf0d8e7e14fdd2c73ff9bf42609a1748bd42`. The commit carries the exact canonical footer, the full-tree no-slop pre-push gate passed in Git for Windows Bash, and remote `main` advanced from `ba665a4a40802f132df729b7abc80350d11a7171` to `d959bf0d8e7e14fdd2c73ff9bf42609a1748bd42` on 2026-07-17.

---

## SAD-01 — Resolve the authoritative seed checkpoint

**Status:** PASS — remote checkpoint `7f30ea691f91b3ea8774b7fd121fbc8580b1d69f`.

### Decision

- Approved seed remote/object:
  `Mighty-Eel-OS` `origin/main` at
  `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`.
- The selected commit is published, is a Git `commit`, has a good SSH signature
  for `basho.parks@gmail.com` with fingerprint
  `SHA256:PE4Wpbp27IeZC6y4dd97YDNLiFrDvky2KOWSqvdkTEc`, and carries the exact
  canonical footer.
- Its parent source implementation checkpoint is
  `5e541e5324269a051d3304e94ae868080d876a25`, which contains reconciled T5 and
  the fully live-validated T6 production tool-governance composition.
- The former local-only T5 branch and the pre-reconciliation `df119fb…`
  baseline remain ineligible.

### Work completed

- Recorded the immutable source pin in
  `PLANNING/SADDLE-SEED-CHECKPOINT-2026-07-17.md`.
- Preserved the historical reconciliation report and appended its current
  resolution rather than rewriting the original evidence.
- Updated the source/rename manifest to distinguish its historic inventory
  baseline from the approved object.
- Mapped all still-open seed hardening prompts `LSH-D1` through `LSH-D5` and
  `LSH-X1` through `LSH-X6` to named Saddle gates. No open source finding is
  silently treated as closed.
- Imported no product source, generated state, runtime data, credentials, or
  private key material.

### Gate

- live remote `refs/heads/main` lookup — PASS;
- selected Git object type, SSH signature, and canonical footer — PASS;
- one immutable source SHA recorded — PASS;
- all remaining source hardening prompts explicitly carried — PASS; and
- target change set remains planning/ledger-only — PASS;
- local Markdown links and `git diff --check` — PASS; and
- Gitleaks plus explicit private-key/token/credential-URL scans — PASS, zero
  findings; and
- staged target no-slop gate — PASS.

### Next prompt

`SAD-02 — Generate the full source-coverage manifest`.

### Commit state

SAD-01 was committed as `7f30ea691f91b3ea8774b7fd121fbc8580b1d69f` with the
exact canonical footer. The configured target full-tree no-slop pre-push gate
passed, and remote `main` advanced from
`578d3ab8ae7425d3cd1b3f69bd25f934e7c3485a` to
`7f30ea691f91b3ea8774b7fd121fbc8580b1d69f` on 2026-07-17.

---

## SAD-02 — Generate the full source-coverage manifest

**Status:** PASS — remote checkpoint `d506e80aee79717b1a48817d471ce9e89ca934c2`.

### Work completed

- Added `tools/generate_saddle_source_manifest.py`, a deterministic generator
  that refuses a dirty seed worktree or a `HEAD` other than the approved full
  SHA and reads tracked blobs only through Git.
- Ran the generator against
  `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`; it recorded all 1,491 tracked
  paths, 1,323 source-like paths, and 1,008 WSF/AOG/Saddle/closure candidates.
- Calculated the complete 37-package internal closure rooted in the 33 direct
  WSF/AOG/fabric/orchestration packages, including `aog-tool-runtime` and the
  four required `mai-*` support packages.
- Recorded Git object IDs, modes, byte sizes, SHA-256 values, relevance
  reasons, and exact `import`, `extract`, `historical-evidence`, or
  `exclude-with-reason` disposition for every candidate path.
- Explicitly dispositioned all 51 `mai-scheduler` paths: 13 topology/power
  extraction candidates for `SAD-43` and 38 inference/KV/batching paths that
  remain in AOG's workload domain.
- Followed CI/workflow path references into deployment, configuration, scripts,
  tests, and relevant support tools rather than relying on text search alone.
- Added explicit source-path handling for four `.env.example` placeholders and
  six deliberately unsafe deployment fixtures. The placeholders remain blocked
  on `SAD-03`; unsafe fixtures are excluded and must use ephemeral values if
  recreated for negative testing.

### Gate

- Cargo metadata closure — PASS, 37 packages;
- full tracked-object inventory — PASS, 1,491 paths;
- per-file SHA-256 and disposition ledger — PASS;
- candidate path dispositions — PASS, 1,008 candidates and zero
  undispositioned paths;
- submodule and symlink inventory — PASS, zero of each;
- deterministic regeneration comparison — PASS, byte-for-byte equal; and
- no seed product source materialized in the target — PASS;
- local Markdown links and final staged whitespace check — PASS;
- Gitleaks plus explicit private-key/token/credential-URL scans — PASS, zero
  findings; and
- staged target no-slop gate — PASS.

### Evidence

- `test-evidence/saddle/SAD-02/source-manifest.json`;
- SHA-256:
  `a2598787f8e69791d4a49b52cae7047c4a91683e15c9d4ec3703ea4767d27d6f`; and
- generator SHA-256:
  `b8d92466f8366506edf010515b0935b7db27fdbad24175f73b3595c4a91cfeb1`.

### Next prompt

`SAD-03 — Prove the no-secret import path`.

### Commit state

SAD-02 was committed as `d506e80aee79717b1a48817d471ce9e89ca934c2` with
the exact canonical footer. The generator syntax, deterministic regeneration,
staged whitespace, Gitleaks, explicit private-key/token/credential-URL, and
staged no-slop gates passed. The configured target full-tree no-slop pre-push
gate also passed in Git for Windows Bash, and remote `main` advanced from
`c5e6fc7cc4f1a9a82456e36914e4cb146df26b37` to
`d506e80aee79717b1a48817d471ce9e89ca934c2` on 2026-07-17.

---

## SAD-03 — Prove the no-secret import path

**Status:** PASS — remote checkpoint `bbb19934c7b1866c44d8719c00fc575b09b43988`.

### Work completed

- Added a tracked-blob-only import proof that validates every selected source
  path's mode, Git object, byte size, and SHA-256 before temporary archive
  construction and isolated index staging.
- Added a dependency-free secondary detector alongside strict default-rule
  Gitleaks; both scanners emit only finding metadata and hash-pinned reviewed
  exceptions, never matched values.
- Validated the 49 `hashed_secret` values in `.secrets.baseline` as SHA-1
  detector digests before narrowly excluding that metadata file from the
  Gitleaks input.
- Corrected the source ledger: the generated staging bundle cache and six
  credential- or token-bearing historical captures are excluded, while their
  provenance remains recorded.
- Added runtime-only test-material generation for disposable CA, server/client
  certificates, private keys, and OpenBao/Saddle/Raft/audit/receipt state.
  The generated certificates verified against the generated CA; the temporary
  private material was removed immediately afterward.

### Gate

- clean pinned seed checkout and Git-blob provenance validation — PASS;
- deterministic temporary archive and raw-blob staged index — PASS, 898 paths
  and tree `6f963caa9c5cdf44fe07f53cf48af4798ba21065`;
- private-key path, non-placeholder `.env`, runtime state, generated cache,
  symlink, and submodule exclusion — PASS;
- strict default-rule Gitleaks — PASS, zero unsuppressed findings;
- independent Saddle static detector — PASS, zero unsuppressed findings;
- reviewed exceptions are exact path/rule/line/fingerprint records with a
  synthetic-fixture assessment — PASS; and
- generated server and client certificates verify against the ephemeral test
  CA — PASS; generated private material removed — PASS.

### Evidence

- `test-evidence/saddle/SAD-03/import-allowlist.json`, SHA-256
  `d1b4106a3ee2e883a1807836b714bb823b97270de05e9a9cf60692dd872886b8`;
- `test-evidence/saddle/SAD-03/no-secret-import-proof.json`, SHA-256
  `a00a15cbe9ddd3de48e7ac97f55bda77a8613478f102cb9c5e102ebdd78a9f1c`;
- `test-evidence/saddle/SAD-03/gitleaks-reviewed-exceptions.json`; and
- `test-evidence/saddle/SAD-03/secondary-reviewed-exceptions.json`.

### Commit state

SAD-03 was committed as `bbb19934c7b1866c44d8719c00fc575b09b43988` with the
exact canonical footer. The final manifest regeneration, staged import proof,
repository-local Gitleaks scan, explicit staged private-key/token/credential
scan, and full target no-slop hook all passed. Target `main` advanced from
`9ccc4ea5cbdae16274e2163b2cafc4992a474cc1` to
`bbb19934c7b1866c44d8719c00fc575b09b43988` on 2026-07-17.

### Next prompt

`SAD-10 — Establish the independent workspace`.

---

## SAD-10 — Establish the independent workspace

**Status:** PASS — implementation published in combined remote checkpoint `93f2d2f7fb9cba29e27a3bf57fe5554a58de97da`.

### Work completed

- Materialized the exact 37-package Cargo closure from immutable seed Git blobs:
  all approved `crates/*` packages plus `mai-agent`, `mai-compliance`,
  `mai-core`, and `mai-router`.
- Verified each of the 391 raw source blobs against its manifest path, Git
  object, mode, byte size, and SHA-256 before writing it to Saddle.
- Imported `Cargo.lock`, `deny.toml`, and `.cargo/audit.toml` byte-for-byte.
  The root `Cargo.toml` is traceably adapted only by narrowing its member list
  from the 48-member seed workspace to the recorded 37-member closure; its
  source and target hashes are recorded in the proof.
- Added a `.gitattributes` rule scoped to the seed-authentic mixed-line-ending
  block in `mai-core/src/power/demotion.rs`, preserving its blob bytes without
  weakening whitespace checks for any other path.
- Recorded that the pinned seed contains no root toolchain or license file;
  Saddle did not invent a licensing decision during this source-cut prompt.
- Added a deterministic materializer that rejects dirty or wrong-SHA seeds,
  validates seed-tree provenance, refuses unsafe paths or modes, and verifies
  the Cargo package-name set rather than only a count.

### Gate

- source seed `fedf005a30ad388ab156dc8bd693a3aa3f0702ea` clean and exact — PASS;
- 391 raw blobs plus the adapted root manifest and path-scoped preservation
  policy materialized deterministically — PASS, 393 workspace paths total;
- idempotent verify-only provenance pass — PASS; and
- `cargo metadata --format-version=1 --no-deps --locked` — PASS, exactly 37
  recorded packages and zero external local paths.

### Evidence

- `test-evidence/saddle/SAD-10/workspace-import-proof.json`, SHA-256
  `0acad7b7d263f873192f4987db19a48d3a8f870905e07a0457712fb9ecaa53af`;
- `tools/materialize_saddle_workspace.py`, SHA-256
  `1af15f58ceebe22d5a268b017a95f8c04b5a3724b5ffaaff4e7582bd2bd59b39`;
- `.gitattributes`, SHA-256
  `b96765281171faef55eaf004fe0a11c641c1523733350a84966b2ed7f5f85635`; and
- target `Cargo.toml` SHA-256
  `08f778821b12355ec8de2fa672a8460290e0140161fd45ed62f1c26e536090e1`.

### Next prompt

`SAD-11 — Import contracts, console/client, deployments, CI, tools, docs, and evidence`.

---

## SAD-11 — Import contracts, console/client, deployments, CI, tools, docs, and evidence

**Status:** PASS — implementation published at remote checkpoint `93f2d2f7fb9cba29e27a3bf57fe5554a58de97da` with SAD-10.

### Work completed

- Materialized the remaining ledger-selected support surface from the immutable
  seed: 242 direct raw imports plus 250 historical-evidence blobs.
- Retained Saddle's canonical `README.md`; the superseded source README is
  recorded as an identity-preserving adaptation rather than copied into Saddle.
- Added six concise Saddle-owned boundary/status records. They preserve imported
  link integrity without claiming source completion, release, security, or
  production status for Saddle.
- Added a deterministic support-surface materializer. It verifies every raw
  blob before writing and derives a `.gitattributes` exception only for the 52
  source-authentic raw paths whose preserved bytes need it.
- Updated the SAD-10 materializer so its base attribute rule is verified as a
  required prefix; SAD-11 can therefore extend the policy without weakening or
  overwriting the independently verified native-workspace cut.

### Gate

- seed binding and support-surface materializer write plus verify-only runs — PASS;
- 885 ledger-selected `import` and `historical-evidence` paths materialized
  across SAD-10 and SAD-11, with zero missing or unexpected paths — PASS;
- canonical README and historical-status guards prevent a Saddle completion
  claim from source history — PASS;
- staged `git diff --check`, explicit staged pre-commit, and full pre-push
  no-slop gates — PASS.

### Evidence

- `test-evidence/saddle/SAD-11/support-surface-import-proof.json`, SHA-256
  `ba4ca9202b36a7812eef36e25145748a8011b5a693e73bc5b834842805189f87`;
- `tools/materialize_saddle_support_surfaces.py`, SHA-256
  `6a1fb6e07dba99a9e6bced7275edf808a8f94b13097bc4be96f495066adeae2b`;
- current `.gitattributes` source-preservation policy, SHA-256
  `697d7b4b8984b24a739a53c9d8437c2a941eb3be6a1bec62657dd0fe49084573`; and
- SAD-10 compatibility verifier `tools/materialize_saddle_workspace.py`,
  SHA-256 `2c54d33336f5f26ff8286b35aa51d07eca3c9726e7d3eff0c9ad92b89b6a62d2`.
- implementation commit `93f2d2f7fb9cba29e27a3bf57fe5554a58de97da`, with
  verified target remote checkpoint at the same SHA.

### Next prompt

`SAD-12 — Remove parent-repository coupling`.

---

## SAD-12 — Remove parent-repository coupling

**Status:** PASS — implementation published at remote checkpoint `0f2dfdf87539736984d59b15dd038982e46d9c06`.

### Work completed

- Changed the workspace repository identity and the supply-chain keyless
  verification identity to `USS-Parks/Lamprey-WSF-AOG-Saddle`.
- Removed external parent-working-copy paths and release/source lookups from
  active project guidance. Historical provenance remains confined to the
  preserved planning, documentation, and evidence records.
- Added a deterministic independence verifier for tracked executable and
  configuration surfaces. It resolves Cargo path dependencies and rejects
  parent repository references, external local paths, submodules, and symlinks.
- Regenerated `Cargo.lock` offline for the independent 37-package closure.
  The previous seed lockfile required an update before `cargo check --locked`
  could succeed from a clean tree.

### Gate

- verifier write and verify-only passes — PASS: 913 tracked paths, 609 active
  paths, zero parent references, external Cargo paths, submodules, or symlinks;
- exact staged index tree `2b84b274fa9435db46bd6bb96984c20e8ad9a1c0`
  archived outside both parent workspaces — PASS: no `.git` entry, no reparse
  points, and zero active forbidden references;
- clean archive `cargo metadata --no-deps --locked` — PASS: 37 packages,
  37 workspace members, and zero external local paths;
- clean archive `cargo check --workspace --locked` — PASS; and
- signing-script syntax, staged `git diff --check`, staged pre-commit, and
  full pre-push no-slop gates — PASS.

### Evidence

- `test-evidence/saddle/SAD-12/independence-gate.json`, SHA-256
  `462ed6a6bde03b0d1750a032953a206e1c76c6dbf94eea3d2205687c096486a6`;
- `test-evidence/saddle/SAD-12/clean-checkout-build-proof.json`, SHA-256
  `0e58dc99b904106f321bfe5f71ac0409ae04c79cb248a58a15a79ed54202c0ec`;
- `tools/verify_saddle_independence.py`, SHA-256
  `be8d4606cced4fcd4d7369c6578a7188c0dde6c80e80f40ced60814ef442d356`; and
- regenerated `Cargo.lock`, SHA-256
  `39ffb3dce2112c287be0f7d7d2f020d1d6a3d10c3d3eddf231c548c767d48701`.

### Next prompt

`SAD-13 — Restore the complete Rust gate`.

---

## SAD-13 — Restore the complete Rust gate

**Status:** PASS — implementation published at remote checkpoint `2459b5a800493e74afde96adf43bcd5d4fe31d5b`.

### Work completed

- Ran the complete Rust gate from the independent 37-package workspace using
  the regenerated locked closure.
- No import-induced workspace source repair was required: formatting, build,
  lint, test, dependency-policy, and documentation commands all completed
  successfully.

### Gate

- `cargo fmt --check` — PASS;
- `cargo check --workspace --locked` — PASS;
- `cargo clippy --workspace --all-targets --locked -- -D warnings -A clippy::pedantic` — PASS;
- `cargo test --workspace --locked` with the configured live OpenBao test
  endpoint — PASS: 187 successful result summaries and zero failures;
- `cargo audit` and `cargo deny check` — PASS; and
- `cargo doc --workspace --no-deps --locked` — PASS. Rustdoc emitted existing
  intra-doc/link-markup warnings but returned no error and generated all
  workspace documentation outputs;
- staged pre-commit and full pre-push no-slop gates — PASS; and
- canonical commit footer plus target remote checkpoint
  `2459b5a800493e74afde96adf43bcd5d4fe31d5b` — PASS.

### Next prompt

`SAD-14 — Restore console and deployment gates`.

---

## SAD-14 — Restore console and deployment gates

**Status:** PASS — implementation published at remote checkpoint `e7627a474bb7af8119ae7a7825c5d6146e4ba6c2`.

### Work completed

- Installed the console from its committed lockfile and restored its test and
  production-build gate.
- Generated disposable Saddle PKI/state material under `C:\tmp`, verified both
  leaf certificates against the generated CA, used shell-only throwaway Compose
  credentials, and removed all private material immediately afterward. No
  appliance `.env` file was present or created.
- Repaired the deployment import boundary without rewriting SAD-02 history:
  materialized the 20-path package closure consumed by the imported package
  script/tests, with three active repository metadata links adapted to Saddle.
- Kept the six excluded unsafe profile fixtures out of the repository; their
  validator conditions now exist only as in-memory, ephemeral test inputs.

### Gate

- `npm ci`, `npm run test`, and `npm run build` in `console/` — PASS: 23 tests
  and a production Vite bundle;
- generated ephemeral material, certificate verification, appliance demo profile
  validation, and `docker compose ... config -q` — PASS with no `.env`;
- CI-defined WSF HA production plus appliance/shadow demo profile validation — PASS;
- appliance and package regression tests — PASS: 128 passed, 1 documented skip;
- `scripts/build-package.sh --validate-only --skip-dashboard` in isolated
  temporary staging — PASS: required package layout present;
- packaging materializer write plus verify-only passes — PASS: 20 paths and
  three repository-identity adaptations;
- Gitleaks and the independent secondary scanner over the new packaging surface
  — PASS: zero findings; and
- staged deterministic independence gate — PASS: 936 tracked paths, 629 active
  paths, and zero forbidden parent references, external Cargo paths,
  submodules, or symlinks;
- staged pre-commit and full pre-push no-slop gates — PASS; and
- canonical commit footer plus target remote checkpoint
  `e7627a474bb7af8119ae7a7825c5d6146e4ba6c2` — PASS.

### Evidence

- `tools/materialize_saddle_packaging_surface.py`, SHA-256
  `946b291a3f45da1e6b40c8c803681f1049672aa9861c6a698db4f90967be09e6`;
- `test-evidence/saddle/SAD-14/packaging-surface-import-proof.json`, SHA-256
  `92c289a8d9521ca0bf660ac692e5115df846b5a70324476695e88f5ac1701cfa`; and
- `test-evidence/saddle/SAD-14/independence-gate.json`, SHA-256
  `562b3b7a69a6ecba492562b64496777380968d9872726c23e86bac304acb98df`.

### Next prompt

`SAD-15 — M1 independent-source checkpoint`.

---

## SAD-15 — M1 independent-source checkpoint

**Status:** PASS — the M1 gate ran from a clean remote clone at
`62b076ea480894e177f504a4fbea3ec638a54b3c`; its evidence closeout was
published at `8ab9eea32e7ee6859ac1a639449587e2b3febe46`.

### Fresh-checkout gate

- cloned `origin/main` depth-one outside either parent workspace: clean status,
  939 tracked paths, and exact published source SHA;
- M1 reconciliation proof passed: 885 selected source paths, 870 raw blob
  matches, five approved transformations, ten explicit non-portable exclusions,
  and all 20 SAD-14 packaging-addendum paths;
- immutable SAD-02 manifest verification passed: 1,491 tracked seed paths and
  1,008 candidates; the source manifest SHA-256 is
  `eb7e97e405b4eb28e94b469e094e74e3fbd6451657ea69fc5f470b1472130ac4`;
- seed and target root-license checks both found zero files, preserving the
  documented source fact without inventing a license decision;
- deterministic independence verification passed: 631 active paths and zero
  parent references, external Cargo paths, submodules, or symlinks;
- locked Rust gate passed: formatting, 37-package metadata, workspace check,
  strict all-target clippy, 187 successful test result summaries with zero
  failures against the configured live OpenBao endpoint, audit, deny, and docs;
- console and deployment gates passed: committed-lock install audit clean, 23
  console tests, production build, generated-certificate verification, WSF HA
  production plus appliance/shadow demo validation, and appliance Compose
  config with shell-only throwaway credentials and no `.env`;
- appliance/package regressions passed: 128 passed and one documented skip;
  staging-only package validation passed in isolated `C:\tmp` material;
- tracked-blob no-secret proof passed for 898 paths with zero unsuppressed
  Gitleaks and independent-secondary findings; the 20-path packaging addendum
  also had zero findings from both scanners; and
- the configured full Git-for-Windows-Bash no-slop hook passed from the fresh
  checkout. The low-level raw helper intentionally remains stricter than that
  hook for immutable historical audit evidence and is not the project gate.

### Evidence

- `test-evidence/saddle/SAD-15/m1-completeness-proof.json`, SHA-256
  `26dd07c7ec860cffd7025165dec9e854106932d6b18bee73d279f37453cfbb7c`;
- `test-evidence/saddle/SAD-15/independence-gate.json`, SHA-256
  `70022ca187a3b6df85cbd682c5579bf9fb95a679482b809b23c51f452c1f0909`; and
- reproducible source checkpoint
  `62b076ea480894e177f504a4fbea3ec638a54b3c`; and
- published SAD-15 evidence closeout checkpoint
  `8ab9eea32e7ee6859ac1a639449587e2b3febe46`.

### Next prompt

`SAD-20 — Rename orchestration packages and binaries`.

---

## SAD-20 — Rename orchestration packages and binaries

**Status:** PASS — implementation commit
`74e09b53038da895dc26dc71283428e25a2bbd82` and verification closeout/verified
remote checkpoint `a6cdb0ed215797870dd4b483aeec868cba8147a2`.

### Work completed

- Moved the exact twelve-package orchestration map to `saddle-*`, `saddled`,
  `saddle-noded`, and `saddlectl` crate paths, Cargo package names, Rust crate
  identifiers, and binary targets.
- Updated dependent Cargo/Rust references plus CI and the existing conformance
  harness build/command references so no compatibility alias is required.
- Preserved the four actual AOG governance packages: `aog-approvals`,
  `aog-gateway`, `aog-toolproxy`, and `aog-tool-runtime`.
- Replaced active human-facing Loom ownership inside the moved packages while
  leaving the SAD-21 protocol/environment/persistence/deployment-directory
  migration and the SAD-22 legacy-state boundary unbundled.
- Added a deterministic identity verifier and evidence artifact. The verifier
  distinguishes active package identity from the immutable seed generator's
  historical source-package vocabulary.

### Gate

- Before-rename characterization of all twelve orchestration packages — PASS;
- deterministic SAD-20 identity write plus verify-only passes — PASS: twelve
  exact packages, three exact binaries, four retained AOG packages, zero old
  Cargo packages/binaries/directories, and zero active old package tokens;
- `cargo fmt --check` — PASS;
- `cargo check --workspace --all-targets --locked` — PASS;
- `cargo clippy --workspace --all-targets --locked -- -D warnings -A clippy::pedantic`
  — PASS;
- `cargo test --workspace --locked` with Git-bundled OpenSSL and the configured
  live OpenBao endpoint — PASS, including renamed mTLS, consensus, controller,
  scheduler, node, API, CLI, and live trust paths;
- `cargo audit` and `cargo deny check` — PASS; existing non-fatal deny warnings
  remain unchanged;
- `docker compose -f deployment/loom-harness/docker-compose.yml config -q` —
  PASS for the renamed binary commands; the directory/service identity remains
  SAD-21 scope;
- staged `git diff --check`, Gitleaks, explicit credential-pattern scan,
  anti-truncation, and full no-slop gates — PASS; and
- implementation commit canonical footer — PASS.

Git's automatic hook launch attempted to use an unavailable WSL distribution.
The staged and full hooks had already passed explicitly under Git for Windows
Bash, so the implementation commit used `--no-verify` only to bypass that shell
resolution failure; no repository gate was waived.

### Evidence

- `test-evidence/saddle/SAD-20/package-identity-gate.json`, SHA-256
  `c0584a98643bc36b9b9df9845db6ea976909c1060c4f90215d07ec21e6c473c8`;
- `tools/verify_saddle_package_identity.py`, SHA-256
  `56979529691bad760f18809c3affea1fba01ae9eac3066f1a12f877f663bdf81`;
  and
- implementation commit
  `74e09b53038da895dc26dc71283428e25a2bbd82`; and
- verification closeout and first verified remote checkpoint
  `a6cdb0ed215797870dd4b483aeec868cba8147a2`.

### Next prompt

`SAD-21 — Rename protocol, trust, persistence, and deployment identities`.
