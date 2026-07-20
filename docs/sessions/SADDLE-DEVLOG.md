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

---

## SAD-21 — Rename protocol, trust, persistence, and deployment identities

**Status:** PASS — implementation commit
`a9e46f013120e9afc6a4afcb6ed21cebbecfa597`; verification closeout and first
verified remote checkpoint
`04a859d883268a1faa0b7b7b73e21a31d7e16b1e`; corrective identity closure
`5ca45e81c3de44d5cdc1e31e1561195b1da12cc2`; corrective closeout and verified
remote checkpoint `3e2fef91581c786f96911b4bb607bf12ef72828a`.

### Work completed

- Renamed active estate API routes and schemas to
  `saddle.islandmountain.io/v1`; controller finalizers and the cordon label now
  use the `saddle.islandmountain.io` namespace.
- Renamed node SPIFFE identities to `spiffe://saddle/node/<id>`, the default
  OpenBao trust prefix to `kv/data/saddle`, the internal forwarding header to
  `x-saddle-forwarded`, and the mutating admin role to `saddle-admin`.
- Cut daemon, edge, and CLI configuration to `SADDLED_*`, `SADDLE_NODE_*`,
  `SADDLECTL_*`, and `SADDLE_*` only. No normal-runtime fallback reads retired
  environment names.
- Renamed active trust, persistence, backup, fixture, test, conformance, CI,
  image/service, deployment, and operator-document identifiers. The live estate
  is now `deployment/saddle-harness`, its cluster manifest is
  `k3s/saddle.yaml`, and its active disaster-recovery and transport runbooks are
  Saddle-named.
- Added negative authorization assertions proving `x-loom-forwarded` remains
  ordinary unauthenticated caller input and `aog-admin` does not satisfy the
  Saddle admin role.
- Added deterministic runtime identity verification and evidence while leaving
  historical DEVLOG/audit vocabulary intact and leaving persisted-state
  conversion to SAD-22.

### Gate

- pre-cutover characterization across `saddled`, `saddle-noded`, estate/API,
  controller, wire, and hardening packages — PASS;
- `cargo fmt --check` — PASS;
- `cargo check --workspace --all-targets --locked` — PASS;
- `cargo clippy --workspace --all-targets --locked -- -D warnings -A clippy::pedantic`
  — PASS;
- `cargo test --workspace --locked` with Git-bundled OpenSSL and configured
  OpenBao coordinates — PASS, including real three-node mTLS, consensus,
  API/admin authorization, controller, scheduler, node, and renamed hardening
  paths; the existing aggressive/SLO tests remain explicitly ignored;
- `cargo audit` and `cargo deny check` — PASS; existing non-fatal deny warnings
  remain unchanged;
- deterministic SAD-20 and SAD-21 identity verify-only gates — PASS; SAD-21
  proves ten required markers, five renamed paths, zero unexplained old active
  identities, and two negative authorization assertions;
- all Saddle harness shell scripts parse under Git for Windows Bash and
  `docker-compose.exe -f deployment/saddle-harness/docker-compose.yml config -q`
  — PASS. A local `kubectl` schema dry-run could not discover an API server; no
  live cluster claim is made by this prompt;
- staged `git diff --check`, Gitleaks, explicit credential-pattern scan,
  anti-truncation, and full no-slop gates — PASS. The anti-truncation hook
  emitted its existing renamed-path `integer expected` warning but exited zero;
  independent staged tail/line-count verification covered 79 text files; and
- canonical commit footer — PASS.

### Evidence

- `test-evidence/saddle/SAD-21/runtime-identity-gate.json`, SHA-256
  `8f32aa53a9cda5502d32d1a3e1e5f7e0825bdc1ae3ad01f389e62b8f4431441e`;
- `tools/verify_saddle_runtime_identity.py`, SHA-256
  `e2415da37216f48a2f33ebce52d34bc388788e4106b40e6027be6abcbc34cb3e`;
  and
- implementation commit
  `a9e46f013120e9afc6a4afcb6ed21cebbecfa597`; and
- verification closeout and first verified remote checkpoint
  `04a859d883268a1faa0b7b7b73e21a31d7e16b1e`; and
- corrective active-identity closure
  `5ca45e81c3de44d5cdc1e31e1561195b1da12cc2`; and
- corrective closeout and verified remote checkpoint
  `3e2fef91581c786f96911b4bb607bf12ef72828a`.

### Next prompt

`SAD-22 — Versioned legacy-state migration`.

---

## SAD-22 — Versioned legacy-state migration

**Status:** PASS — implementation commit
`edc5b5a8328ce3dd47dfc1fe5ce2d156b63dc1c5`; verification closeout and first
verified remote checkpoint `f7f50efd77813e4f8b76057d38f76a99a610df60`.

### Work completed

- Added the offline `saddlectl migrate` inspect, dry-run, apply, verify, and
  rollback modes over a strict ascending, full-version-metadata estate
  snapshot.
- Bound native `Store::range("")`/`Store::restore` adapters without changing
  keys, stored version tuples, or the independent Raft snapshot format.
- Limited automatic conversion to the retired estate API group, controller
  finalizer namespace, and cordon label key. All other payload fields and
  non-JSON entries remain opaque.
- Added a journal containing the complete original versioned estate plus input,
  migrated, protected-payload, receipt-reference, and version-metadata digests.
  Apply refuses path aliases/existing outputs; verify and rollback fail closed
  on replay mismatch, protected-field drift, receipt tampering, label conflict,
  or incomplete legacy structural conversion.
- Added native-store integration coverage and a real independent `wsf-ledger`
  assertion: the chain head is unchanged across migration/rollback and the next
  receipt extends it normally.
- Added the operator runbook and a deterministic CLI gate exercising all five
  modes, an opaque non-JSON entry, exact rollback, and tamper rejection.

### Gate

- `cargo fmt --check` — PASS;
- `cargo check --workspace --all-targets --locked` — PASS;
- `cargo clippy --workspace --all-targets --locked -- -D warnings -A clippy::pedantic`
  — PASS;
- `cargo test --locked -p saddlectl` — PASS, including five migration tests and
  two existing authenticated CLI round trips;
- `cargo test --workspace --locked` with Git-bundled OpenSSL and configured
  live OpenBao coordinates — PASS, including real OpenBao paths, three-node
  mTLS/consensus, native store snapshot/restore, independent receipt-chain
  continuity, the SAD-22 tests, and all doctests; the existing five
  aggressive/SLO conformance tests and weave SLO remain explicitly ignored in
  the standard lane;
- `cargo audit` and `cargo deny check` — PASS; existing non-fatal deny warnings
  remain unchanged;
- deterministic SAD-21 runtime identity and SAD-22 migration gates — PASS;
- staged `git diff --check`, Gitleaks, explicit credential-pattern scan,
  anti-truncation, and full no-slop gates — PASS. The anti-truncation hook
  emitted its existing multi-value `integer expected` warnings but exited zero;
  and
- canonical commit footer — PASS.

### Evidence

- `test-evidence/saddle/SAD-22/legacy-state-migration-gate.json`, SHA-256
  `8b9f84a811ce4db18a006565bd43246f77a757c49ab79b8a3d3efd41abce3c9f`;
- `tools/verify_saddle_legacy_state_migration.py`, SHA-256
  `b8c4dabb439bbd8da200790f51e2ddf0b82782a658e9ceef5db5c40fe9f9263d`;
- `crates/saddlectl/src/migration.rs`, SHA-256
  `c1e80d92ee2c3df0a436e8845129ae728ed48423a41ea00a0c177ad514cbd24e`;
- refreshed SAD-21 count-based evidence SHA-256
  `5afe59a476faaf4d1fce642131f95ab2a57faad0e143f9d3ac37f4b73982ecf4`;
  and
- implementation commit
  `edc5b5a8328ce3dd47dfc1fe5ce2d156b63dc1c5`; and
- verification closeout and first verified remote checkpoint
  `f7f50efd77813e4f8b76057d38f76a99a610df60`.

### Next prompt

`SAD-23 — Active-name eradication gate`.

---

## SAD-23 — Active-name eradication gate

**Status:** PASS — M2 complete; implementation commit
`4f733ff7ae0e9bc30a1002838fd116c398637f22`; verification/M2 closeout and
first verified remote checkpoint `4de1ec3671d630845fb0b4856130506509801023`.

### Work completed

- Inventoried every tracked retired orchestrator-name match and classified it
  as historical provenance, a named migration fixture, or a verification input.
- Added a reviewed classification registry with an exact expected occurrence
  count per rule. New, deleted, moved, ambiguous, or unclassified matches fail
  closed instead of inheriting a directory-wide exception silently.
- Added a deterministic verifier that scans tracked paths and text content,
  generated Cargo identity metadata, compiled CLI help, both OpenAPI schemas,
  the tracked console/deployment/packaging/script surfaces, and the generated
  production console artifact.
- Preserved the SAD-21 retired-header negative authorization assertion and the
  SAD-22 legacy-state seam as named fixtures; neither is a runtime alias.

### Gate

- SAD-23 tracked repository scan — PASS: 952 tracked files, 946 text files, six
  binary files, 38 classified files, 309 count-locked explained occurrences,
  zero classification-count mismatches, and zero unexplained matches;
- generated Cargo metadata — PASS: 37 packages, 217 identity strings, zero
  retired-name occurrences;
- generated API schemas — PASS: `crates/wsf-api/src/openapi.json` and
  `docs/api/openapi.yaml`, zero retired-name occurrences;
- compiled `saddlectl --help` — PASS with zero retired-name occurrences;
- console tracked/UI and generated artifact gate — PASS: 39 tracked UI files;
  `npm.cmd --prefix console test` passed eight files/23 tests; production Vite
  build passed and all four generated artifact files scanned clean;
- deployment, packaging, and script surfaces — PASS: 46, 20, and 18 tracked
  files respectively;
- deterministic SAD-20 package, SAD-21 runtime, SAD-22 migration, and SAD-23
  eradication verify-only gates — PASS;
- `cargo fmt --check`, `cargo check --workspace --all-targets --locked`, and
  strict workspace all-target clippy — PASS;
- staged `git diff --check`, Gitleaks, explicit credential-pattern scan,
  anti-truncation, and full no-slop gates — PASS. The anti-truncation hook
  emitted its existing multi-value `integer expected` warnings but exited zero;
  and
- canonical commit footer — PASS.

### Evidence

- `test-evidence/saddle/SAD-23/active-name-eradication-gate.json`, SHA-256
  `937dd3b43f9e4f2a8a2883fd8165888b74aefda469d9f5dbc9e6ff7d89804adc`;
- `tools/saddle_active_name_classifications.json`, SHA-256
  `3605b3429386f275132410b93afed004c479aea300faebd109349de85756984f`;
- `tools/verify_saddle_active_name_eradication.py`, SHA-256
  `bf919e6aeeee2ab7e5694f580753164c16364fb69083f5a37ceed4a393ed1a1d`;
  and
- implementation commit
  `4f733ff7ae0e9bc30a1002838fd116c398637f22`; and
- verification/M2 closeout and first verified remote checkpoint
  `4de1ec3671d630845fb0b4856130506509801023`.

### Next prompt

`SAD-30 — Establish saddle-bridge and freeze cross-plane contracts`.

---

## SAD-30 — Establish saddle-bridge and freeze cross-plane contracts

**Status:** PASS — implementation commit
`9d173b2242720eb21e5f3ea5206022c3c77d05e8`; verification closeout and first
verified remote checkpoint `163beaeb0d842ff950ce9684ed2fb02d3af08ea5`.

### Work completed

- Added the 38th workspace package, `saddle-bridge`, as the explicit
  WSF-to-Saddle-to-AOG authority boundary. Added a Saddle principal audience
  and exact admission, placement, runtime, and action request operations.
- Froze `saddle.bridge/v1` with private-field, serialize-only
  `VerifiedSaddleRequest`, `AdmissionGrant`, `PlacementGrant`, `RuntimeGrant`,
  and `ActionGrant` types. Compile-fail doctests prove wire JSON cannot
  construct the authority-bearing types.
- Reused `fabric-token::verify_in_context` for WSF signature, issuer-key,
  tenant, bundle, time, and caveat verification; reused
  `MonotonicRevocationStore` for signed freshness and anti-rollback; consumed
  AOG's existing `AggregateDecision` through a policy adapter rather than
  recomposing HIPAA/ITAR/OCAP policy.
- Required current revocation authorization at initial verification and every
  grant transition. Each grant carries immutable tenant, lineage, monotonic
  revocation sequence, expiry, exact target/digests, and metadata-only receipt
  intent; each child is an authority subset of its parent.
- Added an atomic `ReplayStore` adapter with separate request/action namespaces
  and fail-closed storage errors. The built-in memory store is explicitly for
  tests/local use; production consumers can supply durable Saddle storage.
- Added the compatibility/reuse matrix, deterministic verifier/evidence, and
  adversarial property suite. Updated the current-state gap matrix honestly:
  the typed contract is complete, while real admission/scheduler/node/AOG
  wiring remains SAD-31 through SAD-35.

### Gate

- deterministic SAD-30 bridge verifier — PASS: 38-package workspace,
  `saddle.bridge/v1`, six frozen contract/error types, three reused authority
  seams, five adversarial property suites, and two compile-fail doctests;
- non-constructibility — PASS: verified request and grants implement neither
  `Deserialize` nor `Default` and expose no public field construction;
- authority narrowing — PASS across scope, expiry, every budget counter,
  exact placement/node/action, tenant, and lineage axes;
- replay/revocation — PASS: request and action replay deny, replay-store
  failure fences, and absent/stale/expired/revoked/advanced revocation state
  denies at the relevant transition;
- deny/fence — PASS: any AOG deny wins and a vacuous aggregate with zero
  applied modules fences;
- refreshed SAD-23 active-name gate — PASS: 958 tracked files, 952 text files,
  38 packages, 221 Cargo identity strings, 309 count-locked explained
  occurrences, and zero unexplained or generated-metadata matches;
- `cargo fmt --check`, locked full-workspace all-target check, and strict
  all-target clippy — PASS;
- full `cargo test --workspace --locked` with live OpenBao, Git-bundled OpenSSL,
  mTLS, consensus, revocation, restore/receipt-chain, and all doctests — PASS;
  five existing aggressive/SLO conformance tests and the existing
  weave-overhead SLO remain explicitly ignored in the standard lane;
- `cargo audit` and `cargo deny check` — PASS with existing nonfatal unmatched
  allowance, duplicate-dependency, and advisory-not-detected warnings only;
- staged diff, deterministic evidence verify, Gitleaks staged scan,
  anti-truncation, and staged/full no-slop gates — PASS. The integrity script
  emitted its existing multi-value `integer expected` warnings but exited zero;
  and
- canonical commit footer — PASS.

### Evidence

- `test-evidence/saddle/SAD-30/bridge-contract-gate.json`, SHA-256
  `cbf7c130203bda7187fe7a878c9ef83d4ee59bab20c5e5720295d4a22cfca489`;
- `tools/verify_saddle_bridge_contracts.py`, SHA-256
  `9413aec71408f5fba4e2661c6c6671305d9abdd9bcc386e085b35ae84407588b`;
- `crates/saddle-bridge/src/lib.rs`, SHA-256
  `1127e465fc0a1c3431b5a2efb7cd3f82100661d16a975ed8578e94d42a2f6533`;
- `crates/saddle-bridge/tests/contract_properties.rs`, SHA-256
  `6258990f629d2442a718e1222fc11e5ab9a289e6c0b9bc4baef2cbd5f081a692`;
- `docs/contracts/SADDLE-BRIDGE-COMPATIBILITY-MATRIX.md`, SHA-256
  `f9517d44e8f3b7768dd113be2e689eba5e718e8c62a6f54eca49ffc3d64fdb41`;
- refreshed `test-evidence/saddle/SAD-23/active-name-eradication-gate.json`,
  SHA-256 `67e36cf69f64e0abc7b7a5aefb9a6a61bc8b5f8823e7aad34c35d7f4cf92fa30`;
- implementation commit `9d173b2242720eb21e5f3ea5206022c3c77d05e8`;
  and
- verification closeout and first verified remote checkpoint
  `163beaeb0d842ff950ce9684ed2fb02d3af08ea5`.

### Next prompt

`SAD-31 — WSF-authenticated Saddle admission`.

## SAD-31 — WSF-authenticated Saddle admission

**Status:** PASS — implementation commit
`0b3d7a648c5807d58b4575ff15d2fad9840c837c`; verification closeout and first
verified remote checkpoint `8a6e3e1ec311afce6e261ec3c807be60c10fe291`.

### Work completed

- Routed every external Saddle create, update, and delete through a server-derived
  `SaddleAdmission` request context bound to the authenticated WSF principal,
  current signed monotonic revocation sequence, current policy bundle, one-use
  nonce, remaining budget, exact tenant, and final resource identity.
- Reused the SAD-30 `VerifiedSaddleRequest` and `AdmissionGrant` narrowing seam.
  The exact deny-wins AOG aggregate decision now produces an object- and
  mutation-bound grant which is durably committed in the Raft-backed audit
  intent before the desired-state write and retained in the finalized outbox.
- Added four adversarial Router-level tests proving missing/replayed, stale,
  spoofed/out-of-scope, and cross-tenant authority fails closed through the real
  API.
- Made the live revocation publisher advance a signed snapshot sequence instead
  of republishing sequence zero. Updated bounded live fixtures to declare the
  already-enforced gateway route/model authority and to leave a safe margin over
  the STS token-TTL minimum.
- Preserved `admit_system` as an explicit internal-controller seam for SAD-33;
  production removal or strict test confinement is not claimed by this prompt.

### Gate

- deterministic SAD-31 admission verifier — PASS: four real-API adversarial
  tests and source-bound evidence prove current bundle/revocation, exact final
  resource/tenant, nonce replay, deny-wins policy, and audit-before-mutation;
- missing nonce and replayed authority — 401 fail-closed before mutation;
- stale bundle and stale revocation — fail-closed through the real mutation API;
- spoofed signing anchor and out-of-scope final resource — fail-closed;
- cross-tenant authority — cannot mutate the other tenant's final resource;
- refreshed SAD-30 bridge contract gate — PASS after resource-scope narrowing;
- refreshed SAD-23 active-name gate — PASS: 38 packages, 222 Cargo identity
  strings, 309 count-locked explained occurrences, and zero unexplained or
  generated-metadata matches;
- `cargo fmt --check`, locked full-workspace all-target check, strict all-target
  clippy, and workspace documentation — PASS; documentation retained the
  pre-existing nonfatal rustdoc warnings;
- full sequential `cargo test --workspace --locked` with live OpenBao, Moto AWS
  STS, Git-bundled OpenSSL, mTLS, consensus, revocation, restore/receipt-chain,
  official OpenAI/Anthropic SDK clients, and all doctests — PASS; five existing
  aggressive/SLO conformance tests and the existing weave-overhead SLO remain
  explicitly ignored in the standard lane;
- `cargo audit` and `cargo deny check` — PASS with existing nonfatal unmatched
  allowance, duplicate-dependency, and advisory-not-detected warnings only;
- staged diff, deterministic evidence verify, Gitleaks staged scan,
  anti-truncation, and staged/full no-slop gates — PASS. The integrity script
  emitted its existing multi-value `integer expected` warnings but exited zero;
  and
- canonical commit footer — PASS.

### Evidence

- `test-evidence/saddle/SAD-31/admission-gate.json`, SHA-256
  `5f278a9e65e30ee04a5af87139934c9580840c7afa182df27795f4cd1b65f0e5`;
- `tools/verify_saddle_admission.py`, SHA-256
  `b0dd50c99809aa4857a20c2eab2243c7d97efad1f31af26037b25e2e9c2efe4a`;
- `crates/saddle-apiserver/src/auth.rs`, SHA-256
  `e3f3adce442bef0c259b2ac359a2a59944d5d1e4771dd41c9a3377ab0b29cc1e`;
- `crates/saddle-apiserver/src/admission.rs`, SHA-256
  `3442106f3680bef81eb60edd151e20ca3521870f62902a20ec90042a0f8ce195`;
- `crates/saddle-apiserver/tests/saddle_admission.rs`, SHA-256
  `365f77689f243cc1de2020977563d8e43e285f9b00f6044e23cf26ccf90c3f67`;
- `crates/saddle-controller/src/revocation.rs`, SHA-256
  `f191610d21dcdf512e799aecb48825e9c60f7d10f1b86b979a43809a1b053000`;
- refreshed `test-evidence/saddle/SAD-30/bridge-contract-gate.json`,
  SHA-256 `d3d700af8ad6eec2247fc30729323f950535ae1324e7644e572417d3a00c0d3d`;
- refreshed `test-evidence/saddle/SAD-23/active-name-eradication-gate.json`,
  SHA-256 `f9ad6d116cf304c8dc38ef301c306d3ed8a9619346110dc21dfa7c60796cb6c2`;
  and
- implementation commit `0b3d7a648c5807d58b4575ff15d2fad9840c837c`;
  and
- verification closeout and first verified remote checkpoint
  `8a6e3e1ec311afce6e261ec3c807be60c10fe291`.

### Next prompt

`SAD-32 — WSF-attested scheduling`.

## SAD-32 — WSF-attested scheduling

**Status:** PASS — implementation commit
`a87aed1604a81ea5680411dd932bc81ab2a3356e`; verification closeout and first
verified remote checkpoint `3da29ab4fffa6499584fce128a77c4451cf1fd84`.

### Work completed

- Added explicit workload scheduling constraints for required CPU, memory, GPU,
  and slots; connectivity; provider models; and optional exact platform
  measurement.
- Made heartbeat freshness, verified-attestation expiry, trust ring,
  classification ceiling, attestation floor, hardware/PCR evidence,
  measurement, air-gap compatibility, provider/model eligibility, and declared
  capacity hard fail-closed filters which execute before scoring.
- Added canonical `saddle.node-attestation/v1` evidence signed by the existing
  ML-DSA anchor over the exact node, ring, floor, platform/PCR profile, issue
  time, and expiry. The real scheduler controller verifies that signature and
  expiry before retaining an attested node snapshot.
- Made provider observations timestamped and fenced when missing, unhealthy, or
  stale. A coherent scheduling decision time now controls heartbeat,
  attestation, and provider freshness.
- Added adversarial pressure, failover, stale-heartbeat, stale-attestation,
  stale-provider, air-gap, capacity, and provider-model tests, plus registration
  tests rejecting attacker signatures and profile tampering.
- Preserved an explicit boundary: serialized `PlacementGrant` handoff and the
  internal controller system-identity seam remain SAD-33 work. This prompt does
  not claim hardware quote verification unless the signing anchor's issuance
  path is backed by it.

### Gate

- deterministic SAD-32 attested-scheduling verifier — PASS: four scheduler
  adversarial tests and two registration-tampering tests prove that pressure,
  failover, or stale cache cannot authorize an under-attested placement;
- refreshed SAD-23 active-name gate — PASS: 38 classified files and 309
  count-locked explained occurrences, with no unexplained active-name result;
- `cargo fmt --all --check`, locked full-workspace all-target check, strict
  all-target clippy, and workspace documentation — PASS; documentation retained
  the repository's pre-existing nonfatal rustdoc warnings;
- full sequential `cargo test --workspace --locked` with live OpenBao, Moto AWS
  STS, Git-bundled OpenSSL, mTLS, consensus, revocation, restore/receipt-chain,
  official OpenAI/Anthropic SDK clients, and all doctests — PASS; the existing
  five aggressive/SLO conformance tests and weave-overhead SLO remain explicitly
  ignored in the standard lane;
- `cargo audit` and `cargo deny check` — PASS with existing nonfatal unmatched
  allowance, duplicate-dependency, and advisory-not-detected warnings only;
- staged diff, deterministic evidence verification, Gitleaks staged scan,
  anti-truncation, verify-tree, and staged/full no-slop gates — PASS; and
- canonical commit footer — PASS.

### Evidence

- `test-evidence/saddle/SAD-32/attested-scheduling-gate.json`, SHA-256
  `396976ad3fd32cc06f1642545d855fb14de88419757edcb72948ba8316ae2d60`;
- `tools/verify_wsf_attested_scheduling.py`, SHA-256
  `ea70b4fd48c51289f44b84d0bd13743840e3ef5e00404bd6d0dd2b6d1d859159`;
- `crates/saddle-node/src/registration.rs`, SHA-256
  `88c1d3a29ac4010da5ec543758c9d2f7ffc494d8c539660d290b75971c342115`;
- `crates/saddle-controller/src/scheduler.rs`, SHA-256
  `1c7f944112f91fa05a4c9e54052dcf317e29f0fdec2d62a24ee92e9184f2abf9`;
- `crates/saddle-scheduler/src/filters.rs`, SHA-256
  `4762b4213a71e5e1a254ef9f66001afa892a21c4e3a31e49a3dc8347a5722542`;
- `crates/saddle-scheduler/tests/sad32_hard_placement.rs`, SHA-256
  `213878fec086563cf76e7ee47d5857dff4b84e14c1da1d7b613acc7dd287af32`;
- `docs/contracts/SADDLE-BRIDGE-COMPATIBILITY-MATRIX.md`, SHA-256
  `792a1237fe5998b8d46caa20982485c40b2035b12169f51c48d026ffc26b9065`;
- `PLANNING/SADDLE-CURRENT-STATE-GAP-MATRIX.md`, SHA-256
  `519d51fef3b8396aeb117595770db9871040969658ee8222ab27e73c097c9b7a`;
- refreshed `test-evidence/saddle/SAD-23/active-name-eradication-gate.json`,
  SHA-256 `2ecd1a5a80a9648493e2d324e90915b7abd2d7ff57969d1760e36e7956bd17fc`;
  and
- implementation commit `a87aed1604a81ea5680411dd932bc81ab2a3356e`;
  and
- verification closeout and first verified remote checkpoint
  `3da29ab4fffa6499584fce128a77c4451cf1fd84`.

### Next prompt

`SAD-33 — AOG workload integration`.

## SAD-33 — AOG workload integration

**Status:** PASS — implementation commit
`57616b479b66ea582369d85cd9d2a74fe684b09f`; verification closeout and first
verified remote checkpoint `7a13d765ab0e07db14e698327fa7067ce120e346`.

### Work completed

- Added an explicit approvals workload kind and fixed least-privilege AOG role
  and runtime-class mappings for gateway, toolproxy, approvals, agent, and
  inference workloads.
- Added canonical workload digests and exact service identities binding tenant,
  workload kind, node, and immutable placement UID. Replica count is excluded
  so scaling starts only new ordinals while runtime-affecting changes roll the
  existing binding.
- Added `NodeRuntime`, which verifies ML-DSA signature, expiry, revocation,
  tenant, workload UID/digest, placement UID, exact node identity, token ID,
  single fixed role, and classification immediately before driver start. Its
  reconciler stops missing, changed, or revoked assignments.
- Replaced unrestricted release-build scheduler admission with a private,
  server-minted, tenant/profile/TTL/controller-epoch `ControllerGrant`.
  Scheduler grants can only create runtime-bound pending placements, finalize
  their token ID without rewriting immutable binding fields, or delete them.
  The former system fixture remains available only in debug builds.
- Made the scheduler require a current same-tenant capability root, create the
  immutable placement before signing its child, store the exact child in live
  OpenBao, and roll back the child if placement finalization fails.
- Added a live integration gate using real admission/controller queues,
  scheduler reconciliation, OpenBao, and `ProcessDriver`. It proves all five
  workload classes start; agent scale 1→2 starts only the new ordinal; digest
  roll replaces and restarts the binding; sibling-token theft and scheduler
  field forgery fail closed; and capability/controller-epoch revocation removes
  or invalidates authority.
- Preserved the explicit compatibility boundary: the signed child capability is
  enforced at the node, but the frozen typed `PlacementGrant` and `RuntimeGrant`
  proof values are not yet the serialized controller-node handoff. SAD-34 adds
  action authorization/receipts; this typed handoff must close before SAD-35.

### Gate

- deterministic SAD-33 AOG workload integration verifier — PASS against live
  OpenBao, including release checks proving unrestricted scheduler authority is
  absent from release builds;
- deterministic SAD-32 attested-scheduling regression gate — PASS;
- refreshed SAD-23 active-name gate — PASS: 38 classified files and 309
  count-locked explained occurrences, with no unexplained active-name result;
- `cargo fmt --all --check`, locked full-workspace all-target check, strict
  all-target clippy, release controller/API check, and workspace documentation
  — PASS; documentation retained two pre-existing nonfatal controller rustdoc
  warnings;
- full sequential `cargo test --workspace --locked` with live OpenBao, Moto AWS
  STS, Git-bundled OpenSSL, mTLS, consensus, revocation, restore/receipt-chain,
  official provider SDK clients, and all doctests — PASS; the repository's
  existing aggressive/SLO tests remain explicitly ignored in the standard lane;
- `cargo audit` and `cargo deny check` — PASS with existing nonfatal unmatched
  allowance, duplicate-dependency, and advisory-not-detected warnings only;
- staged diff, deterministic evidence verification, Gitleaks staged scan,
  verify-tree, and staged no-slop gate — PASS; verify-tree retained its existing
  nonfatal multi-value `integer expected` warning; and
- canonical commit footer — PASS.

### Evidence

- `test-evidence/saddle/SAD-33/aog-workload-integration-gate.json`, SHA-256
  `6d3d58d97afb4b3081e7dfed7c1b86f5830e0b4b2bfa477b3090323640075ca7`;
- `tools/verify_aog_workload_integration.py`, SHA-256
  `8818954df65f785857ca395c00224ab126f58d9cd532ac5f3a705a82c89739d2`;
- `crates/saddle-node/src/runtime.rs`, SHA-256
  `3183ba7aa700db2bc8891ccf13c444cf63fb71dcded9794aa43b86652e81f2b1`;
- `crates/saddle-controller/src/scheduler.rs`, SHA-256
  `f3724c11756d12c7f23b10b7c0facff4e77974fe1adfd476a221236f60f85735`;
- `crates/saddle-apiserver/src/admission.rs`, SHA-256
  `d2904585a9adebab1e27cb1d32e18456592be77e3a2334d8f857f64890ba5ff9`;
- `crates/saddle-controller/src/objects.rs`, SHA-256
  `2d571a0dbdf3297e586fe615268b9a8d68faba800711f6a71305bec98788d7c9`;
- `crates/saddle-controller/tests/sad33_aog_workloads.rs`, SHA-256
  `dd82e12e0cbf092d8167d127570de177d1dd3331ce4505630b4c4465f3c08f21`;
- `docs/contracts/SADDLE-BRIDGE-COMPATIBILITY-MATRIX.md`, SHA-256
  `18dc26c746b1a2dfeefe0561a9bcce4651dc63dbf7f609771709a8110af7fdb3`;
- `PLANNING/SADDLE-CURRENT-STATE-GAP-MATRIX.md`, SHA-256
  `55052dbb21e27649a0d00330aaa83584cec9a3f3ad2c6131ab69c35c68d23d42`;
- refreshed `test-evidence/saddle/SAD-32/attested-scheduling-gate.json`,
  SHA-256 `0a0d518ed779e0440fa099b3021d6b25bc2c675524bd7e535518940896e4cafc`;
- refreshed `test-evidence/saddle/SAD-23/active-name-eradication-gate.json`,
  SHA-256 `3e8ef5fdf517fb8e6a848bc3f55da774c8f72f1fdab94bd472022a031dd14aca`;
  and
- implementation commit `57616b479b66ea582369d85cd9d2a74fe684b09f`;
  and
- verification closeout and first verified remote checkpoint
  `7a13d765ab0e07db14e698327fa7067ce120e346`.

### Next prompt

`SAD-34 — Per-action reauthorization and receipts`.

## SAD-34 — Per-action reauthorization and receipts

**Status:** PASS — implementation commit
`3d65900c870e10a812cc1468e3b005cfce96a931`; verification closeout and first
verified remote checkpoint `f2be87602bc68f02169211d3e9ad718937e6189a`.

### Work completed

- Added `ActionGate`, `PreparedAction`, and a metadata-only
  `ActionAuthorizationReceipt` at the frozen `saddle.bridge/v1` boundary.
- Bound receipt intent to the exact action request digest and rejected mismatches
  before replay consumption can produce effect authority.
- Reused `fabric-token`'s atomic reservation ledger to reserve the full requested
  spend against the runtime ceiling. The key intentionally omits destination so
  callers cannot multiply the budget across providers or tool targets.
- Required a trusted `ActionReceiptSink` to atomically reject duplicate receipt
  IDs and return a non-empty committed proof before a `PreparedAction` exists.
  The bridge coordinates this ordering but does not reimplement WSF receipt
  signing, chaining, or storage.
- Rechecked current signed monotonic revocation state and action expiry after the
  receipt commit and immediately before the private effect closure. The reserved
  budget commits conservatively before the effect so cancellation or uncertain
  downstream completion cannot become unmetered authority.
- Added real ML-DSA, signed-revocation, and `wsf-ledger` tests for model, tool,
  and control actions. They prove receipt-before-effect observation,
  cross-tenant theft and replay denial, revocation and expiry races, shared
  cross-destination budget denial, and failed/empty receipt proof denial.
- Preserved the explicit SAD-35 boundary: the generic enforcement layer is
  complete, while the persisted typed `PlacementGrant`/`RuntimeGrant` handoff
  and real gateway/toolproxy/control consumer composition remain for the live
  two-tenant gate. Legacy post-effect receipts are not cited as SAD-34 proof.

### Gate

- deterministic SAD-34 action-reauthorization verifier — PASS: five adversarial
  tests cover all three action kinds and every named failure race;
- saddle-bridge contract/property suite and compile-fail grant-construction
  doctests — PASS, including exact receipt/request digest binding;
- refreshed SAD-23 active-name gate — PASS: 38 classified files and 309
  count-locked explained occurrences, with no unexplained active-name result;
- `cargo fmt --all --check`, locked full-workspace all-target check, and strict
  all-target clippy — PASS;
- full elevated `cargo test --workspace --locked` with live OpenBao, official
  OpenAI/Anthropic SDK clients, controller/node lifecycle regressions, and all
  doctests — PASS; five documented aggressive/SLO conformance tests and the
  weave-overhead p99 test remain explicitly ignored in the standard lane;
- `cargo audit`, `cargo deny check`, and workspace documentation — PASS with the
  repository's existing nonfatal unmatched-allowance, duplicate-dependency,
  advisory-not-detected, and rustdoc warnings only;
- staged diff, deterministic evidence verification, Gitleaks staged scan,
  verify-tree, and staged no-slop gate — PASS; verify-tree retained its existing
  nonfatal multi-value `integer expected` warning; and
- canonical commit footer — PASS.

### Evidence

- `test-evidence/saddle/SAD-34/action-reauthorization-gate.json`, SHA-256
  `f66a97ca7fe8644f72e66746d316e64d0737b4276215d8dc3703af92b3922e59`;
- `tools/verify_action_reauthorization.py`, SHA-256
  `0b778807115c4a4a062b00b393173a32e5f643bc5b45a7f41d69e49be3ef322e`;
- `crates/saddle-bridge/src/lib.rs`, SHA-256
  `a5b32008f0923568e82241f755a3558c0875fbecca153f9923ef20695e3b6eb2`;
- `crates/saddle-bridge/tests/sad34_action_gate.rs`, SHA-256
  `cf1910aed91306072f4994b53ac1ab95e68f1e13854ccae54116f68acd20d7ae`;
- `crates/saddle-bridge/tests/contract_properties.rs`, SHA-256
  `db63fddee3d9c2807db63ecf1db9a7cef06355b4c97ca8a33620ae4479355801`;
- `docs/contracts/SADDLE-BRIDGE-COMPATIBILITY-MATRIX.md`, SHA-256
  `da11f0a7a7084fd0fdee5b808a2acd9c374d1bb5cacef436b39c894989a4978d`;
- `PLANNING/SADDLE-CURRENT-STATE-GAP-MATRIX.md`, SHA-256
  `c4b0deb9e6c1e4d4479225bffd0f8565dbd10a1a44af24bdde42a12330bcfb87`;
- refreshed `test-evidence/saddle/SAD-23/active-name-eradication-gate.json`,
  SHA-256 `e23e9aeb771516025cc35e5f06587657205287a2c6199db2f3a8298b05bd1a70`;
  and
- implementation commit `3d65900c870e10a812cc1468e3b005cfce96a931`;
  and
- verification closeout and first verified remote checkpoint
  `f2be87602bc68f02169211d3e9ad718937e6189a`.

### Next prompt

`SAD-35 — Live two-tenant bridge gate`.

## CI-R1 - Saddle workflow reconciliation

**Status:** PASS - implementation commit
`5900fad8be0eb6871340cdd16c933c33a8f3b2fc`; corrective commits
`4f550545f2ed8eb7fdb0befa426c3b940857e2fb`,
`2c5ca1ca5d34f857331404bd089a733c50fe4683`,
`3dfd0b9478fe16b4bfe08b03733cf6dfd0ea8be4`, and
`c16b07facadd03e2f7c493957d3da2f75d7d55af`; first checkpoint with every
applicable push workflow green
`c16b07facadd03e2f7c493957d3da2f75d7d55af`.

This was a focused repair requested after the obsolete inherited workflow set
failed against the independent Saddle repository. It does not complete or
supersede SAD-35.

### Work completed

- Replaced inherited MAI application, Python SDK, GPU release, and legacy ship
  validation jobs with Saddle CI, package, Compose, repository-boundary,
  Windows-workspace, and supply-chain workflows tied to the actual 38-package
  Cargo workspace.
- Removed obsolete workflow-only packaging, release, SDK, systemd, and GPU
  support surfaces; rewrote the root container and Debian staging contracts for
  `saddled`, `saddle-noded`, and `saddlectl`.
- Restored executable modes for every tracked shebang script and Debian rules
  file, and added a repository test that prevents mode regression.
- Changed lock parity to validate the locked Cargo graph through
  `cargo metadata --locked --no-deps`; paired Python requirement files are
  compared only when that optional surface exists.
- Reduced inherited dependency and advisory policy to the current workspace,
  regenerated deterministic SAD-12 and SAD-23 evidence, and added workflow
  contract tests for known packages, excluded surfaces, job topology, and
  generated-evidence ordering.
- Repaired remote-only boundary failures by building `saddlectl` and the console
  bundle before SAD-23 verification, canonicalizing the CLI artifact identity
  across Windows and Linux, and making the portability regression independent
  of how pytest is invoked.

### Local gate

- `cargo fmt --all --check`, locked workspace all-target check, strict
  all-target clippy, clean sequential `cargo test --workspace --locked`, and
  `scripts\\saddle-validation.ps1 -Suite all` - PASS.
- `cargo audit`, `cargo deny check`, locked workspace documentation, lock
  parity, route policy, Hadolint, package validation on PowerShell and Bash,
  SAD-12 independence, SAD-23 active-name eradication, SDK compatibility,
  deployment/packaging/CI contract tests, Gitleaks, staged/full no-slop, and the
  pre-push gate - PASS. Route policy retained its nonfatal stale declaration
  warnings; cargo-deny retained allowed duplicate-version warnings; rustdoc
  retained pre-existing nonfatal warnings.
- Root runtime, appliance, and harness container builds - PASS before the final
  verifier-only corrections. A later root-image retry was blocked by external
  Docker DNS resolution and is not cited as a pass.
- The local five-replica Compose estate passed V4 partition fencing, V5 mass
  deletion, V7 repeated kill/heal convergence, V8 replicated-object recovery,
  and V10 five-round recovery-time validation, then was torn down.
- Canonical commit footer verification - PASS for every outgoing commit.

### Remote gate

Intermediate Saddle Validation runs correctly failed while the repaired gate
exposed missing CLI generation, missing console generation, cross-platform
evidence drift, and a pytest import-path assumption. Each failure received a
bounded corrective commit and a fresh full push run. On final implementation
checkpoint `c16b07facadd03e2f7c493957d3da2f75d7d55af`:

- `commit-msg-check` run `29657053347` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29657053347
- `Saddle Validation` run `29657053380` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29657053380
- `Saddle CI` run `29657053345` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29657053345
- `Saddle Workspace Validation` run `29657053366` - PASS, including the full
  Windows validation suite and uploaded result artifact:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29657053366

### Node 24 follow-up

Follow-up commit `30a30dbc4027d4b27080c2a329acb9364155125f`
corrected the workflow runtime after local Node `v24.15.0` was confirmed. The
console build now requests Node 24 explicitly, and every JavaScript action uses
an officially declared Node 24 major: `actions/checkout@v7`,
`actions/setup-node@v7`, `actions/setup-python@v6`, and
`actions/upload-artifact@v7`. The CI contract suite now rejects older runtime
pins.

The production console build under Node 24, SAD-23 deterministic verification,
the 9-test CI contract suite, staged/full no-slop, route policy, and canonical
footer gates passed locally. All applicable push workflows then passed without
the prior Node 20 deprecation annotation:

- `commit-msg-check` run `29659752294` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29659752294
- `Saddle Validation` run `29659752302` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29659752302
- `Saddle CI` run `29659752286` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29659752286
- `Saddle Workspace Validation` run `29659752314` - PASS in 25m58s:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29659752314

### Next prompt

`SAD-35 - Live two-tenant bridge gate`.

## SAD-35 — Live two-tenant bridge gate

**Status:** PASS — implementation commit
`ef8b27236e1e4f24b27fbad9b249703299291bfc`; every applicable implementation-
checkpoint push workflow passed before this closeout was recorded.

### Work completed

- Added a signed, canonical, persisted `PlacementGrant`/`RuntimeGrant` handoff
  with binding, expiry, lineage, and current-revocation verification across
  redb close/reopen recovery.
- Required the verified typed handoff plus the existing signed child capability
  immediately before the actual Saddle process driver starts.
- Added tenant/runtime-class action sessions that narrow to single-use
  model/tool/control actions, share the runtime budget across destinations,
  commit WSF-ledger proof before effect, and recheck revocation at execution.
- Routed configured AOG gateway provider effects and toolproxy executor effects
  through the action registry. Authority failure returns fail-closed service
  errors; standalone compatibility constructors remain available for isolated
  package use.
- Added the live two-tenant test across OpenBao, six runtime sessions, redb
  restart, the process driver, gateway provider, tool executor, signed
  revocation, authority loss/recovery, shared budgets, and serialized off-host
  WSF receipt verification.
- Repaired an existing live metering-test race by giving concurrent tests
  distinct OpenBao AppRoles. The full workspace suite exposed and verifies the
  correction.
- Added the SAD-35 deterministic verifier and included the live gate in Saddle
  CI. The executable verifier is tracked with mode `100755`.
- The focused anti-slop review removed an unused public-trait derive; the
  remaining new types and adapters are exercised trust-boundary requirements.

### Local gate

- Node `v24.15.0` console `npm.cmd ci` and production build — PASS: exact lock,
  198 packages, zero reported vulnerabilities.
- `cargo fmt --all --check`, locked all-target workspace check, strict clippy,
  full live `cargo test --workspace --locked`, and all doctests — PASS.
- Canonical `scripts\saddle-validation.ps1 -Suite all` — PASS after the live
  metering AppRole isolation repair.
- `cargo audit`, `cargo deny check`, and locked workspace docs — PASS with only
  the repository's existing nonfatal duplicate/unmatched-allowance and rustdoc
  warnings.
- Python repository suite — PASS, 36 tests; official OpenAI and Anthropic SDK
  compatibility tests — PASS.
- SAD-12 independence, SAD-23 active names, SAD-35 deterministic evidence,
  lock parity, route policy, profile validation, executable modes, workflow
  contracts, Gitleaks, integrity verification, no-slop, and manual pre-push
  checks — PASS. Route policy retained only its declared stale-route warnings.

### Remote gate

On implementation checkpoint `ef8b27236e1e4f24b27fbad9b249703299291bfc`:

- `commit-msg-check` run `29664654505` — PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29664654505
- `Saddle Validation` run `29664654490` — PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29664654490
- `Saddle CI` run `29664654509` — PASS, including the live SAD-35 trust gate:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29664654509
- `Saddle Workspace Validation` run `29664654488` — PASS in 31m36s:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29664654488

### Evidence

- `test-evidence/saddle/SAD-35/two-tenant-bridge-gate.json`, SHA-256
  `667c32f8152e05d5ce7053ccc17378abdaeb17fa50a899f3410dd29d1f502125`;
- `tools/verify_two_tenant_bridge.py`, SHA-256
  `c08d3c1e86fdcf2871a2ef564260cbcf33384a009560567091af3e8ebf1f7fc0`;
- `crates/saddle-controller/tests/sad35_two_tenant_bridge.rs`, SHA-256
  `49dd520975e05d5809c74ce4b1371cd0cb06a69c695a83a0055d40230fd77de5`;
- `crates/saddle-bridge/src/lib.rs`, SHA-256
  `fcad3a5b92b96620ae9b629f89555ca0461e3e46327bb58d1e4b798378da3250`;
- `crates/aog-gateway/src/lib.rs`, SHA-256
  `7e8e252eae5e1388b59b576a7f00cb02b578b98e9ccba14161468ee0a13309e5`;
- `crates/aog-toolproxy/src/lib.rs`, SHA-256
  `c82bca76d2fb6487e59149c77e7e99ca1c02c5f5efb082f6b32f543e00713a4e`;
- `crates/saddle-node/src/runtime.rs`, SHA-256
  `b98f038f98a6b299c1e663588cc86259561296aea86522312991f8a6f680e08e`;
  and
- implementation commit `ef8b27236e1e4f24b27fbad9b249703299291bfc`.

### Next prompt

`SAD-40 — Declarative estate and conversion`.

## SAD-40 — Declarative estate and conversion

**Status:** PASS — implementation commit
`99b31ebe9415cdd066c0d5fed559ffe9a7747465`; final verified implementation
checkpoint `14672ead45b2f4effe65f42c27590cea1be0dcab`.

### Work completed

- Expanded the strict typed estate from 13 to 19 kinds with `ResourceQuota`,
  `PriorityClass`, `PlacementGroup`, `DisruptionBudget`, `RuntimeClass`, and
  `NodeLease`, including fail-closed schema and semantic validation.
- Applied estate-authority admission to runtime classes and protected priority
  classes, preserved status across updates, and envelope-sealed runtime
  credential references before persistence.
- Replaced the permissive conversion seam with a fail-closed registry and
  canonical `saddle.islandmountain.io/v1` hub. Unknown versions, kinds,
  non-advancing edges, cycles, malformed objects, and metadata collisions are
  rejected; legacy conversion rolls back exactly.
- Exercised optimistic concurrency, watches, and two-phase finalization through
  the real API and Raft-backed store. A 512-case deterministic conversion fuzz
  gate preserves authority, UID, generation, resource version, desired state,
  and status through round trip and rollback.
- Added the SAD-40 verifier to Saddle Validation and recorded deterministic
  evidence for all six resource round trips, sensitive-field sealing, real
  store behavior, conversion invariants, and fail-closed cases.

### Local gate

- `cargo fmt --all --check`, locked all-target workspace check, strict
  all-target clippy, and full `cargo test --workspace --locked` including
  doctests — PASS. Only the repository's deliberately ignored aggressive/SLO
  tests remained skipped.
- `cargo audit`, `cargo deny check`, config parsing, SAD-12 independence,
  SAD-23 active names, SAD-40 deterministic verification, Gitleaks, full/staged
  no-slop, integrity verification, and the pre-push gate — PASS. Cargo-deny
  retained only its existing nonfatal duplicate-version warnings.
- The SAD-40 resource suite passed seven typed round-trip and fail-closed cases;
  the API suite passed four integration cases including 512 deterministic fuzz
  inputs, exact rollback, CAS/watch/finalizer behavior, and persisted sealing.
- Canonical commit footer verification — PASS for every outgoing commit.

### Remote gate

The first Saddle Validation run, `29668154840`, correctly failed because the
new tracked files changed the deterministic SAD-12 inventory. Commit
`a337ba3e46fd210a13f37f9bdde22eaf5099c45b` refreshed that evidence. The next
Saddle Validation run, `29668240795`, correctly failed when SAD-23 found a
retired identity used as an active legacy fixture; commit
`14672ead45b2f4effe65f42c27590cea1be0dcab` made the fixture classification-clean
and regenerated the affected evidence. On that final implementation checkpoint:

- `commit-msg-check` run `29668445386` — PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29668445386
- `Saddle Validation` run `29668445380` — PASS, including SAD-12, SAD-23, and
  the new SAD-40 verifier:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29668445380
- `Saddle CI` run `29668445374` — PASS, including the five-replica Phase-V and
  live WSF/AOG/Saddle trust gates:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29668445374
- `Saddle Workspace Validation` run `29668445379` — PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29668445379

### Evidence

- `test-evidence/saddle/SAD-40/declarative-estate-gate.json`, SHA-256
  `782a33059c34a74754955e4cdcda485ddfed56f5b318a8fc13b3334d59fd6e76`;
- `tools/verify_sad40_declarative_estate.py`, SHA-256
  `2892b67f657ac96f575294c482873ed6bd51f17106ed48986c2de79c0aa66023`;
- `crates/saddle-estate/tests/sad40_resources.rs`, SHA-256
  `fea668cd144efcaf08c7c594622c40c2e70f817cf1d850a76cef7f4e5dbe0e56`;
- `crates/saddle-apiserver/tests/sad40_declarative_estate.rs`, SHA-256
  `1ba416cee18cbe8fc6c5010a02f94ef89b9eacbdef4388f345c9fbb405b19a66`;
  and
- implementation/correction commits `99b31ebe9415cdd066c0d5fed559ffe9a7747465`,
  `a337ba3e46fd210a13f37f9bdde22eaf5099c45b`, and
  `14672ead45b2f4effe65f42c27590cea1be0dcab`.

### Next prompt

`SAD-41 — Consensus truth and fencing`.

## SAD-HIST-04 - Published-history reconciliation closeout

**Status:** COMPLETE - reviewed lane merged and canonical ledgers closed

### Scope and publication

SAD-HIST-04 remained an isolated history-reconciliation lane. It reproduced
the SAD-HIST-02 sanitized archive proof with Gitleaks 8.30.1 and TruffleHog
3.95.9 before publication, then published exactly 38 sanitized refs beneath
`refs/heads/history/mighty-eel/...`. Active GitHub ruleset `19173522` prohibits
deletion, updates, and non-fast-forward changes and grants no bypass actor.

Live verification matched all remote tips and proved the 762-commit,
10,444-object graph: 4,885 blobs, 4,797 trees, and 762 commits. The original
secret-bearing blob and commit are absent. No mirror push, source-history merge,
replacement ref, graft, tag, or archive-parented active branch was used.

### Verification and integration

The implementation passed the complete applicable local verification stack.
Reviewed head `85b5c0925136ce7ea9865f197e1295db42ed07ca` then passed every applicable
GitHub check in pull request
[#4](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/pull/4), including
Saddle CI `29696226957`, Saddle Validation `29696226956`, Saddle Workspace
Validation `29696226935`, canonical footer `29696226937`, and supply chain
`29696226926`. The lane merged without squashing as
`2937f6494561fc607519de6c17c259bc7c684e51`.

`Cargo.toml` and `Cargo.lock` remain byte-identical to the reconciled base. The
protected archive refs are not parents or ancestors of active Saddle `main`.

### Canonical continuation

This closeout does not supersede or advance the canonical implementation
roster. `SAD-41 - Consensus truth and fencing` remains the next prompt.

## SAD-41 - Consensus truth and fencing

**Status:** PASS - implementation commit
`d3f26627b4912e8cd25c916dcbddfdf601a8af85`; final verified implementation
checkpoint `ca6ee6ba21b59ce14f51d2f0f19f87a58ab55b66`.

### Work completed

- Made controller leadership authority contingent on a current quorum-confirmed
  gate. Minority, removed, or stale leaders cannot serve authoritative writes.
- Added linearizable leader-transition handling, safe known-member membership
  changes with quorum overlap, removed-member fencing, and exact late-learner
  state recovery.
- Added versioned BLAKE3-checksummed snapshots whose install replaces the
  keyspace exactly and preserves revision and deletion truth. Invalid versions,
  lengths, and checksums fail closed.
- Bounded the watch cache and made lagged consumers fail closed before an exact
  current-revision relist, preventing stale watch state from becoming an allow.
- Added a five-case Jepsen-style gate covering 6 concurrent clients with 32
  attempts each, leader transition, a four-node membership rotation, 100 watch
  overflow events, malformed/non-quorum membership changes, and minority
  partition fencing. No acknowledged write was lost and no stale authoritative
  allow was served.
- Reconciled the newly published SAD-HIST lane without rewriting history. The
  history verifier now proves recorded dependency and product digests at their
  historical commits instead of freezing later mainline files; SAD-12, SAD-23,
  and SAD-HIST-03 deterministic evidence was refreshed for the merged tree.

### Local gate

- Focused `sad41_consensus_truth` suite - PASS, 5/5 tests; deterministic SAD-41
  verifier - PASS.
- `cargo fmt --all --check`, locked workspace check, strict all-target clippy,
  full `cargo test --workspace --locked` including doctests, `cargo audit`,
  `cargo deny check`, and locked workspace docs - PASS. Only the repository's
  deliberately ignored aggressive/SLO/nightly tests remained skipped; existing
  nonfatal cargo-deny duplicate and rustdoc warnings were unchanged.
- Node `v24.15.0` console install from lock and production build - PASS, 198
  packages and zero reported vulnerabilities.
- Full Python repository suite - PASS, 52/52 tests; focused history-publication
  regression suite - PASS, 3/3 tests.
- SAD-12 independence, SAD-23 active names, SAD-40 estate, SAD-41 consensus,
  SAD-HIST-03 reconciliation, and SAD-HIST-04 publication verifiers - PASS.
  Gitleaks, integrity, formatting/diff checks, executable modes, the configured
  full no-slop scan, and the manual pre-push hook also passed.
- Canonical commit-footer verification - PASS for every outgoing commit.

### Remote gate

On final implementation checkpoint
`ca6ee6ba21b59ce14f51d2f0f19f87a58ab55b66`:

- `commit-msg-check` run `29700204044` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29700204044
- `Saddle Validation` run `29700204042` - PASS, including the repository
  boundary and SAD-41 deterministic verifier:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29700204042
- `Saddle CI` run `29700204069` - PASS, including Rust quality, supply-chain,
  Phase-V live estate, live WSF/AOG/Saddle trust, integration, and the SAD-41
  consensus/conformance gate:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29700204069
- `Saddle Workspace Validation` run `29700204040` - PASS on Windows:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29700204040

### Evidence

- `test-evidence/saddle/SAD-41/consensus-truth-gate.json`, SHA-256
  `c0ba07e62a105afe45b912ec28d1eedb8ba674a5b437904b19bf54778e7130de`;
- `tools/verify_sad41_consensus_truth.py`, SHA-256
  `a07c566a0f2111d9affb4235e02ae1d648bdb10f6822c1547c3bc64ea60e7c7e`;
- `crates/saddle-controller/tests/sad41_consensus_truth.rs`, SHA-256
  `61bedc6a1ba8e0d676f2fc51a595ba4ff128fc98ae1839d00cff80341bc38367`;
  and
- implementation commit `d3f26627b4912e8cd25c916dcbddfdf601a8af85`, history
  integration commit `12d6c8da5703a5398dee9276b3a087fd588b2ad9`, and merged-boundary
  verification commit `ca6ee6ba21b59ce14f51d2f0f19f87a58ab55b66`.

### Windows CI leader-rotation repair

- `Saddle Workspace Validation` run `29708461122` exposed a legitimate leader
  transfer from bootstrap node 1 to node 3 after voter expansion. The SAD-41
  test incorrectly pinned subsequent writes to node 1 and unwrapped the
  resulting `ForwardToLeader` response.
- The test now discovers the quorum-confirmed leader, drives snapshot and
  membership rotation through that node, removes and fences that elected
  leader, and derives the survivor set from the actual removed member.
  Production code is unchanged.
- Follow-up Windows run `29709831561` transferred leadership again during the
  write sequence. Final repair `f502b0881518b186a869b19f1271c41861419412`
  now reacquires quorum-confirmed leadership for every write, learner add, and
  membership operation, tolerating Raft forwarding without weakening any
  precondition or fencing assertion.
- The exact failed scenario passed 11/11 local runs; the complete SAD-41 gate
  passed 5/5; its deterministic verifier, strict focused clippy, formatting,
  and diff checks passed. The evidence hash above was refreshed accordingly.

### Next prompt

`SAD-42 - Level-triggered reconciliation`.

## SAD-42 - Level-triggered reconciliation

**Status:** PASS - implementation commit
`870947c6c05329c47165eef7e4ae07fa6dd5eca9`; evidence-boundary repair
`0aeb54bfcb76cad7f110761629003faf915150a3`; final verified checkpoint
`f502b0881518b186a869b19f1271c41861419412`.

### Work completed

- Replaced event-history dependence with level-triggered reconciliation from
  current estate state. Duplicate, reordered, and dropped events converge
  through informer full relist and periodic resync.
- Added deterministic per-key jittered exponential backoff, bounded retry,
  visible dead-letter state, and redrive without defeating active backoff.
- Added reconcile deadlines and shutdown cancellation so hung or abandoned
  futures cannot retain controller authority.
- Preserved restart-recoverable finalizer truth and proved external withdrawal
  precedes admitted deletion through the live vkey finalizer seam.
- Added deterministic fault injection covering 256 histories, 86 overflow
  histories, 52 restart histories, and 100 watch-overflow events per injected
  history under seed `0x5ad42000c0def17e`.
- Repaired the SAD-HIST evidence boundary after the SAD-42 workflow change, then
  made the SAD-41 membership-rotation test follow and fence the actual
  quorum-confirmed leader instead of assuming bootstrap node 1 retained
  leadership. Production behavior was unchanged by that CI repair.

### Local gate

- SAD-42 controller library, replay, and fault-history suites - PASS;
  deterministic reconciliation verifier - PASS.
- Full Python repository suite after the evidence-boundary repair - PASS,
  52/52 tests.
- Exact formerly failing SAD-41 leader-rotation scenario - PASS, 11/11 local
  runs; complete SAD-41 gate - PASS, 5/5; deterministic SAD-41 verifier and
  strict focused clippy - PASS.
- Formatting, diff checks, configured staged/full no-slop hooks, and outgoing
  canonical-footer audits - PASS. Disposable local build and downloaded CI
  artifacts were removed after verification.

### Remote gate

On final verification checkpoint
`f502b0881518b186a869b19f1271c41861419412`:

- `commit-msg-check` run `29710953629` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29710953629
- `Saddle Validation` run `29710953654` - PASS, including repository boundary
  and deterministic evidence checks:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29710953654
- `Saddle CI` run `29710953650` - PASS, including Rust quality, supply chain,
  Phase-V live estate, live WSF/AOG/Saddle trust, integration, and conformance:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29710953650
- `Saddle Workspace Validation` run `29710953648` - PASS on Windows, including
  the complete workspace suite and leader-rotation regression:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29710953648

### Evidence

- `test-evidence/saddle/SAD-42/reconciliation-gate.json`, SHA-256
  `44ab8f5ebb8307494575d4a20bb8d858c6b63ba5effe4993f640b98c67931ae0`;
- `tools/verify_sad42_reconciliation.py`, SHA-256
  `b130b242151b36a283919631101b0dbd4115224f79ae1ed1cf689d58c856d97a`;
- `crates/saddle-controller/tests/sad42_reconciliation.rs`, SHA-256
  `607f1d3136eba74566e575a6a249aff966cb09114a02ed0cc50f62e17ed3cea0`;
  and
- implementation commit `870947c6c05329c47165eef7e4ae07fa6dd5eca9`, evidence
  repair `0aeb54bfcb76cad7f110761629003faf915150a3`, and final verified
  checkpoint `f502b0881518b186a869b19f1271c41861419412`.

### Next prompt

`SAD-43 - Professional scheduler framework and fairness`.

## SAD-43 - Professional scheduler framework and fairness

**Status:** PASS - implementation commit
`2a2dd39959654ea159056f94573e13ddad893e22`; tracked-evidence repair
`fe615e1ab6b61f6e2658510d8c5d3269263a4b45`; final verified checkpoint
`062b1e1592c5946a4fe884101fc7093146321df4`.

### Work completed

- Added a public professional scheduling framework with the ordered QueueSort,
  PreFilter, Filter, PostFilter, PreScore, normalized Score, Reserve/Unreserve,
  Permit, PreBind, Bind, and PostBind lifecycle. Plugins declare identity,
  version, timeout, and failure posture; failures and panics fail closed.
- Added one coherent revisioned scheduling state with workload
  UID/generation/replica compare-and-swap identity, clone-before-commit atomic
  reservations and binding, complete rollback, and recomputed allocation
  invariants after every committed transition.
- Preserved SAD-32's deny-wins trust predicates and added tenant/estate,
  runtime-class, lease/cordon, quota, full resource-vector, placement-group,
  topology, and capacity filters that never relax under pressure.
- Added weighted dominant-resource fairness across CPU, memory, ephemeral
  storage, GPU, NPU, accelerator memory and slots, spend, and extended
  resources, combined with guarantees, priority, age, and a declared feasible
  starvation bound.
- Added bounded permit approve/wait/reject/expiry behavior, all-or-nothing gang
  reservation and binding, deterministic multi-victim disruption-aware
  preemption, topology/locality and spread scoring, consolidation, and
  authoritative metered budget/ROI scoring.
- Added bounded active, backoff, unschedulable, and permit-wait queues with
  explicit wake events, plus CI and local-validation integration.
- Added a 10-case deterministic gate with seed `0x5ad43000c0def17e`, 256
  adversarial multi-tenant histories, and 64 operations per history. It proves
  no sovereignty bypass, double bind, quota/capacity oversubscription, leaked
  reservation, or feasible-work starvation.
- Refreshed deterministic evidence whose tracked-file or workflow digests
  legitimately changed. The verifier is executable and hashes UTF-8 text after
  canonical LF normalization so identical Linux and Windows checkouts produce
  the same evidence.
- Repaired the stale post-rename Gitleaks allowlist path for the already reviewed
  synthetic OpenBao anchor fixture; the strict scan then reported no leaks.

### Local gate

- Focused SAD-43 suite - PASS, 10/10 tests; 256 histories x 64 operations;
  deterministic verifier generation and byte verification - PASS.
- Complete `saddle-scheduler` suite - PASS, 64/64 tests.
- `cargo fmt --all --check`, locked all-target workspace check, strict all-target
  clippy, and full `cargo test --workspace --locked` including doctests - PASS.
  The full Windows run used Git for Windows' bundled OpenSSL for the mTLS tests;
  only the repository's deliberately ignored aggressive, SLO, and nightly tests
  remained skipped.
- `cargo audit`, `cargo deny check`, and locked workspace documentation - PASS;
  existing nonfatal duplicate-dependency and rustdoc warnings were unchanged.
- Console install from lock, 23/23 tests, production build, and npm audit - PASS
  with 198 packages and zero reported vulnerabilities.
- Full Python repository suite - PASS, 52/52 tests.
- SAD-12 independence, SAD-23 active-name, SAD-40 estate, SAD-41 consensus,
  SAD-42 reconciliation, SAD-43 scheduler, SAD-HIST-03 reconciliation, and
  SAD-HIST-04 publication verifiers - PASS.
- Gitleaks, integrity, formatting/diff checks, executable modes, configured
  staged/full no-slop hooks, route policy, manual pre-push, and outgoing
  canonical-footer audits - PASS. The stricter historical helper continued to
  report nine pre-existing provenance identifiers in the untouched history
  reconciler; the configured repository hook remained authoritative and clean.

### Remote gate

On final verification checkpoint
`062b1e1592c5946a4fe884101fc7093146321df4`:

- `commit-msg-check` run `29729863242` - PASS:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29729863242
- `Saddle Validation` run `29729863276` - PASS, including repository boundary,
  all deterministic evidence records, and SAD-43:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29729863276
- `Saddle CI` run `29729863283` - PASS, including Rust quality, supply chain,
  integration, contract/conformance, live trust, and Phase-V scale,
  revocation-SLO, split-brain, and chaos/soak gates:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29729863283
- `Saddle Workspace Validation` run `29729863298` - PASS on Windows in the full
  all-suite profile, including the LF-normalized SAD-43 evidence check:
  https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29729863298

### Evidence

- `test-evidence/saddle/SAD-43/professional-scheduler-gate.json`, SHA-256
  `cece294b1ab37aecf790e1d4b076f2159aa8f0b08bb7bfc5db58fd6bab7d5580`;
- `tools/verify_sad43_professional_scheduler.py`, SHA-256
  `db21d3564a9fed8b19babcdce3332dcb725dca4c26215e59071f00916cb3a972`;
- `crates/saddle-scheduler/src/professional.rs`, SHA-256
  `2ce6f47cc7e812f1fa409804adaad62793aae3e23d9c740740d5e7a1c5dd7461`;
- `crates/saddle-scheduler/tests/sad43_professional_scheduler.rs`, SHA-256
  `d164a32d66fe01da4f6a716e21c3d06c4c9ef01451ab597b2c88a61cb79c15bc`;
  and
- implementation commit `2a2dd39959654ea159056f94573e13ddad893e22`,
  tracked-evidence repair `fe615e1ab6b61f6e2658510d8c5d3269263a4b45`,
  and final verified checkpoint
  `062b1e1592c5946a4fe884101fc7093146321df4`.

### Next prompt

`SAD-44 - Node runtime and attestation liveness`.
