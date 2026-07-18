# Saddle Source and Rename Manifest

**Purpose:** Make the independent source import and the Loom-to-Saddle replacement mechanically executable.
**Authority:** Supporting specification for `SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`.
**Status:** **SAD-02 PASS — generated from the approved immutable seed pin.**
The machine-readable path, disposition, and SHA-256 ledger is
`test-evidence/saddle/SAD-02/source-manifest.json`; `SAD-03` owns the
no-secret staged-import proof before any source enters the target.

## 1. Current repository evidence

Observed on 2026-07-16:

| Repository/state | SHA | Meaning |
|---|---|---|
| Target `USS-Parks/Lamprey-WSF-AOG-Saddle` `origin/main` | `cbf2622e924b207f545e344b6b2976613fada12b` | Founding documents only; no product source |
| Seed `USS-Parks/Mighty-Eel-OS` `origin/main` | `df119fb6321e60e8cfffc1b36281ba95f9f5004a` | Latest published seed snapshot inspected for this baseline |
| Seed local `main` | `6b8118975d6e17a1e4e1c7458c8c2594516c224b` | Diverged local T5 work; ahead one and behind five relative to `origin/main` |

`df119fb…` is an **inventory baseline, not an approved import pin**. `SADDLE-SEED-RECONCILIATION-2026-07-16.md` establishes that local T5 commit `6b81189…` is a targeted-gate-clean transplant candidate onto `df119fb…`, with only the DEVLOG append point conflicting. It is still local-only and M3 remains open through the absent T6 production seam. `SAD-01` must produce a new published checkpoint containing both histories and explicitly close or carry every remaining hardening prompt before selecting the immutable import SHA. No local-only commit may be silently canonized.

### 1.1 SAD-01 approved pin

`SAD-01` selected published seed `origin/main`
`fedf005a30ad388ab156dc8bd693a3aa3f0702ea` as the sole import source. It is a
signed Git commit whose parent source implementation checkpoint is
`5e541e5324269a051d3304e94ae868080d876a25`, which closes the T6 production
tool-governance gate. The counts in the 2026-07-16 baseline remain historical
inventory evidence only. `SAD-02` regenerated every count, dependency closure,
path disposition, and content hash from the approved object; no local
filesystem state supplemented it. See `SADDLE-SEED-CHECKPOINT-2026-07-17.md`
for the open-finding carry-forward register.

### 1.2 SAD-02 generated ledger

The generator ran against clean seed checkout
`fedf005a30ad388ab156dc8bd693a3aa3f0702ea`, verified that its `HEAD` exactly
matches the requested object, and read tracked blobs only through Git. The
result contains every one of the 1,491 tracked paths, not a filesystem walk.

| Evidence | Value |
|---|---|
| Generator | `tools/generate_saddle_source_manifest.py` |
| Generator SHA-256 | `b8d92466f8366506edf010515b0935b7db27fdbad24175f73b3595c4a91cfeb1` |
| Evidence ledger | `test-evidence/saddle/SAD-02/source-manifest.json` |
| Evidence SHA-256 | `a2598787f8e69791d4a49b52cae7047c4a91683e15c9d4ec3703ea4767d27d6f` |
| Tracked paths | 1,491 |
| Source-like paths | 1,323 |
| Candidate paths | 1,008 |
| Cargo closure packages | 37 |
| Undispositioned matching paths | 0 |
| Submodules / symlinks | 0 / 0 |

Every ledger entry records Git object ID, mode, byte count, SHA-256,
source-like status, relevance reasons, disposition, and disposition reason.
The ledger is deterministic: regeneration from the same clean checkout and
seed object must compare byte-for-byte equal.

## 2. Approved package closure

At `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`, Cargo metadata reports:

- 33 direct WSF/AOG/fabric/orchestration root packages;
- 37 packages in the complete internal dependency closure; and
- four additional internal closure packages: `mai-agent`, `mai-compliance`,
  `mai-core`, and `mai-router`.

The 33 roots contain 285 tracked files and the four internal closure packages
contain 103 tracked files. The minimum native package import therefore covers
388 tracked files before root manifests, contracts, console, deployment, CI,
integrity tooling, docs, and evidence.

### 2.1 Saddle orchestration packages — import complete, then rename

| Seed package/path | Tracked files | Saddle destination |
|---|---:|---|
| `aog-apiserver` / `crates/aog-apiserver` | 23 | `saddle-apiserver` / `crates/saddle-apiserver` |
| `aog-conformance` / `crates/aog-conformance` | 6 | `saddle-conformance` / `crates/saddle-conformance` |
| `aog-controller` / `crates/aog-controller` | 49 | `saddle-controller` / `crates/saddle-controller` |
| `aogctl` / `crates/aogctl` | 4 | `saddlectl` / `crates/saddlectl` |
| `aogd` / `crates/aogd` | 13 | `saddled` / `crates/saddled` |
| `aog-estate` / `crates/aog-estate` | 4 | `saddle-estate` / `crates/saddle-estate` |
| `aog-federation` / `crates/aog-federation` | 2 | `saddle-federation` / `crates/saddle-federation` |
| `aog-node` / `crates/aog-node` | 12 | `saddle-node` / `crates/saddle-node` |
| `aog-noded` / `crates/aog-noded` | 4 | `saddle-noded` / `crates/saddle-noded` |
| `aog-scheduler` / `crates/aog-scheduler` | 10 | `saddle-scheduler` / `crates/saddle-scheduler` |
| `aog-store` / `crates/aog-store` | 14 | `saddle-store` / `crates/saddle-store` |
| `aog-wire` / `crates/aog-wire` | 5 | `saddle-wire` / `crates/saddle-wire` |

These are identity migrations, not rewrites. Characterization tests must pass before and after each move. Cargo package names, Rust crate paths, binary names, documentation links, CI targets, image names, and deployment references move together.

### 2.2 AOG governance packages — import complete, retain AOG identity

| Package/path | Tracked files | Treatment |
|---|---:|---|
| `aog-gateway` / `crates/aog-gateway` | 29 | Retain; model/data-path governance |
| `aog-toolproxy` / `crates/aog-toolproxy` | 7 | Retain; governed tool execution |
| `aog-approvals` / `crates/aog-approvals` | 2 | Retain; human approval decisions |
| `aog-tool-runtime` / `crates/aog-tool-runtime` | 3 | Retain; live production tool-governance composition |

AOG remains the agentic-governance plane. Only the scheduler/orchestrator formerly branded Loom moves to Saddle identity.

### 2.3 WSF and fabric packages — import complete, retain identity

| Package/path | Files | Package/path | Files |
|---|---:|---|---:|
| `fabric-cache` | 2 | `fabric-contracts` | 9 |
| `fabric-crypto` | 7 | `fabric-envelope` | 3 |
| `fabric-identity` | 3 | `fabric-proof` | 8 |
| `fabric-revocation` | 3 | `fabric-token` | 10 |
| `wsf-api` | 19 | `wsf-bridge` | 5 |
| `wsf-broker` | 10 | `wsf-cache` | 3 |
| `wsf-hardening` | 3 | `wsf-ledger` | 3 |
| `wsf-seal` | 5 | `wsf-tenants` | 3 |
| `hipaa-pack` | 2 |  |  |

All paths above are under `crates/`. Tests, fixtures, examples, build scripts, and schemas inside each path are part of the import.

### 2.4 Internal dependency closure — import complete initially

| Package/path | Tracked files | Why it is in closure |
|---|---:|---|
| `mai-agent` | 11 | Tool registry, roles, budgets, and agent seams used by AOG |
| `mai-compliance` | 47 | Deny-wins policy and classifiers used by WSF/AOG |
| `mai-core` | 30 | Shared types required by `mai-agent` and `mai-compliance` |
| `mai-router` | 15 | AOG routing/classification pipeline |

The first import preserves these packages byte-for-byte at the seed pin. Later extraction or renaming requires its own compatibility prompt; it is not bundled into the source cut.

### 2.5 Scheduler reuse candidate outside the dependency closure

`mai-scheduler` is not a Cargo dependency of the product closure. At the pin it
contains 51 tracked paths focused on inference-request routing, GPU topology,
batching, KV-cache locality, and power-aware placement. The existing
orchestration scheduler contains nine Rust files and approximately 2,105 Rust
lines focused on estate placement and fail-closed attestation.

Do not import `mai-scheduler` blindly and do not discard it without review.
`SAD-02` dispositioned its modules as follows:

- extract GPU topology, extended-resource, locality, and power-scoring techniques when they strengthen Saddle workload placement;
- keep inference batching, KV-cache, and request-level routing in the AOG runtime domain unless a declared Saddle plugin needs them; and
- reject absence-as-optimism or any signal that cannot be traced to a current node/resource observation.

The generated ledger explicitly marks 13 `mai-scheduler` paths `extract`:

- `src/topology/{analysis,collector,graph,mod,refresh}.rs`;
- `src/scoring/topology_score.rs`, `src/power.rs`, and `src/types.rs`;
- four GPU-topology fixtures; and
- `tests/topology_integration.rs`.

The other 38 `mai-scheduler` paths are `exclude-with-reason`: their
inference-request routing, batching, KV-cache, or model-serving behavior stays
in the AOG workload domain. This is reuse analysis, not permission to weaken
the full professional scheduler target.

## 3. Required non-package import surface

### 3.1 Import and adapt as a unit

- root Rust build/reproducibility files: `Cargo.toml`, `Cargo.lock`, `deny.toml`, `.cargo/`, toolchain files if present, `.editorconfig`, `.gitignore`, `.dockerignore`;
- secret-scanning configuration: `.gitleaks.toml`, `.secrets.baseline`, and the serial detector tooling, after verifying the baseline contains no suppressed live secret;
- all four contract specifications in `contracts/`;
- the complete 39-file `console/` tree;
- `.githooks/`, `.integrity/`, and applicable `.github/` policy/workflows, rewritten for the target repository and renamed packages;
- tracked deployment, configuration, script, test, and CI support surfaces;
  `deployment/loom-harness` is imported for later rename to
  `deployment/saddle-harness`;
- the WSF/AOG-related simulator, trace, smoke, burn-in, packaging, GPU-release,
  and ship-validation tool surfaces; and
- WSF/AOG/Saddle architecture, operations, runbooks, security findings, session DEVLOGs, and claim evidence selected by the coverage ledger; and
- license, notice, provenance, and release-policy material needed to redistribute every imported file.

### 3.2 Generated full path disposition

The generated ledger applies both content/path relevance scanning and explicit
build/CI/deployment closure rules. It records the complete path lists and
per-file SHA-256 values in JSON rather than presenting a lossy hand-maintained
subset here.

| Disposition | Paths | Meaning |
|---|---:|---|
| `import` | 635 | Native closure or required independent build, deployment, CI, tool, policy, and placeholder surface; still subject to SAD-03. |
| `extract` | 13 | `mai-scheduler` topology/power primitives preserved for Saddle SAD-43. |
| `historical-evidence` | 250 | Relevant history and evidence preserved without turning seed claims into Saddle completion claims. |
| `exclude-with-reason` | 110 | Unrelated MAI surfaces, unsafe negative fixtures, generated cache material, token-bearing historical evidence, or source that remains deliberately in AOG/runtime scope. |
| `out-of-scope-no-match` | 483 | Tracked paths with no relevant content/path match and no closure/build dependency. |

The six tracked `deployment/appliance/fixtures/unsafe-*` files are explicitly
excluded. They are negative-test profiles and may be recreated only with
ephemeral values under SAD-03. The four tracked `.env.example` files are
explicitly marked `import` only as placeholders; a single secret finding blocks
their inclusion.

`deployment/openbao-staging/bundle-cache/bundle.json` is also excluded. It is
generated staging cache material, not an importable source input; SAD-03's
ephemeral material procedure replaces it with fresh runtime-only state.

Six historical detector, bootstrap, DEVLOG, or compose-capture files that carry
credential- or token-shaped fixture material are excluded as well. Their seed
SHA-256 records remain in the generated ledger, while any future Saddle
evidence must be regenerated with sanitized or ephemeral values.

### 3.3 Explicit initial exclusions

The following seed areas remain outside the verified package dependency closure
unless a specific ledger row says otherwise:

- `mai-adapters`, `mai-api`, `mai-hil`, `mai-vault`, `mai-sdk-rs`, and `mai-sdk-python`;
- legacy app, adapter, dashboard, packaging, simulator, and test surfaces unrelated to the imported stack; and
- MAI appliance profiles whose executables remain MAI-specific.

An exclusion is not permanent if `SAD-02` proves a live source/build/evidence dependency. Conversely, a textual mention alone does not justify importing an unrelated product. Relevant extracted primitives retain provenance hashes and license notices.

## 4. Tracked-only, zero-secret import method

The import source is a Git object at the approved seed SHA—not a local filesystem copy. The executable import must:

1. resolve and record the seed commit and its signature/status;
2. materialize only tracked allowlisted paths from that commit;
3. verify each materialized file against a generated SHA-256/BLAKE3 manifest;
4. reject symlinks escaping the repository and reject submodules;
5. exclude `.git`, `.env` files except verified placeholders, private keys, generated PKI, OpenBao state, caches, logs, build output, and local configuration;
6. run at least two independent secret detectors plus explicit private-key/cloud-token/credential-URL checks before staging;
7. replace required certificates and keys with runtime generation scripts; and
8. scan the staged target tree again before any commit.

If a real credential appears, the import stops. Suppression alone is not closure: the credential must be assessed for rotation and history remediation under explicit authority.

### 4.1 Deterministic regeneration

Run the generator from a clean checkout whose `HEAD` is exactly the approved
seed SHA. The second command must report PASS before a manifest is accepted.

```text
python tools/generate_saddle_source_manifest.py \
  --seed-repo <clean-mighty-eel-os-checkout> \
  --seed-sha fedf005a30ad388ab156dc8bd693a3aa3f0702ea \
  --output test-evidence/saddle/SAD-02/source-manifest.json

python tools/generate_saddle_source_manifest.py \
  --seed-repo <clean-mighty-eel-os-checkout> \
  --seed-sha fedf005a30ad388ab156dc8bd693a3aa3f0702ea \
  --output test-evidence/saddle/SAD-02/source-manifest.json \
  --verify
```

## 4.1 SAD-14 bounded packaging closure addendum

SAD-14's imported `scripts/build-package.sh` and
`tools/packaging_tests/` establish a bounded packaging dependency that the
original generated ledger had correctly recorded as textually out of scope.
The original SAD-02 manifest remains immutable. The independent repository now
uses `tools/materialize_saddle_packaging_surface.py` to consume the original
seed objects and produce
`test-evidence/saddle/SAD-14/packaging-surface-import-proof.json` for exactly
20 required package README, Debian metadata, maintainer-script, and systemd
unit paths.

Seventeen selected blobs are byte-for-byte seed material. Three active package
metadata paths adapt only their repository URL to Saddle's independent target;
the proof records both source and target SHA-256 values. The excluded
`deployment/appliance/fixtures/unsafe-*` paths remain absent: their validator
conditions are recreated in memory with ephemeral values, not imported as
credential-shaped fixture files. The legacy package names remain pending the
Phase 2 Saddle identity rename.

## 4.2 SAD-15 M1 source reconciliation

The fresh-checkout M1 comparison identified eleven source-ledger paths absent
from the initial cut. `tests/benchmarks/results/.gitkeep` is restored as the
verified empty source blob. The remaining ten are not portable independent
source: eight are stale OpenBao staging anchors, key-hash/AppRole configuration,
or legacy bootstrap/response automation, and two are historical logs carrying
parent-local environment paths. They remain absent by explicit M1 policy, with
their original SHA-256 values and reasons recorded in the M1 completeness
proof. `deployment/openbao-staging/README.md` is a Saddle-owned boundary
record, not an imported runtime configuration.

The M1 verifier binds all 885 original selected paths: 870 byte-for-byte raw
matches, five approved transformations, and ten explicit non-portable-source
exclusions. It additionally binds the 20-path SAD-14 package closure. This is
an additive reconciliation; the immutable SAD-02 manifest and its original
dispositions remain preserved as historical provenance.

## 5. Loom-to-Saddle active identity map

The baseline broad scan finds 120 tracked files with Loom identity patterns. That includes immutable history and active code. Active source/deployment/workflow residues are concentrated in the 12 orchestration packages, `wsf-hardening`, `deployment/loom-harness`, three workflow files, and active operator documents.

| Seed identity | Saddle identity/rule |
|---|---|
| Human-facing `Loom` | `Saddle` |
| Package prefix on orchestration crates | `saddle-*` per §2.1 |
| `aogd` / `aog-noded` / `aogctl` | `saddled` / `saddle-noded` / `saddlectl` |
| `deployment/loom-harness` | `deployment/saddle-harness` |
| `loom-harness` images/services/jobs | `saddle-harness` |
| `LOOM_*` runtime variables | `SADDLE_*`; old variables accepted only by the explicit migration shim |
| `x-loom-forwarded` | `x-saddle-forwarded`; still never treated as caller authority |
| `spiffe://loom/...` | `spiffe://<configured-trust-domain>/saddle/...` |
| `kv/data/loom/...` | configurable Saddle OpenBao prefix, default `kv/data/saddle/...` |
| `loom.aog/<finalizer>` | `saddle.islandmountain.io/<finalizer>` |
| `loom.io/unschedulable` | `saddle.islandmountain.io/unschedulable` |
| `aog.islandmountain.io/v1` estate resources | version-converted to `saddle.islandmountain.io/v1`; AOG runtime APIs keep AOG identity |
| `LOOM-DR-RUNBOOK.md` | `SADDLE-DR-RUNBOOK.md` |
| `loom-*` test IDs and temporary prefixes | `saddle-*`, except named legacy-conversion fixtures |
| Metrics/log fields | `saddle_*` metrics and `saddle.*` structured namespaces |

The SPIFFE trust domain and OpenBao prefix are deployment configuration, not hard-coded global authority. The migration supports inspect/dry-run/apply/verify/rollback and emits Saddle identities only.

## 6. Rename acceptance gate

The rename is complete only when:

- Cargo metadata contains the exact Saddle orchestration package set and no old orchestration package aliases;
- generated schemas and API discovery serve `saddle.islandmountain.io/v1` for estate resources;
- binaries, help output, environment docs, containers, workflows, metrics, and runbooks use Saddle;
- legacy state converts without changing tenant, authority, object UID, generation, resource version, placement, receipt reference, or revocation meaning;
- old names are accepted only inside the bounded migration tool/fixtures and are never emitted by normal runtime; and
- a repository-wide scan returns zero unexplained Loom identity matches outside immutable historical provenance.

## 7. Authority cutover

The import does not create indefinite dual ownership. Until the approved seed is frozen, Mighty Eel OS remains authoritative. After M1 independent-build and M2 rename gates pass, the owner approves a cutover checkpoint. From that checkpoint forward, WSF/AOG/Saddle changes land here first; Mighty Eel OS consumes signed releases or pinned contracts and receives no automatic backflow.
