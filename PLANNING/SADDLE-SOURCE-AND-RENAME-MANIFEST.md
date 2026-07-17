# Saddle Source and Rename Manifest

**Purpose:** Make the independent source import and the Loom-to-Saddle replacement mechanically executable.
**Authority:** Supporting specification for `SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`.
**Status:** SAD-01 approved immutable seed pin; SAD-02 must regenerate all
counts, hashes, and dispositions at that pin before import.

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
tool-governance gate. The counts in this section remain historical inventory
evidence only. `SAD-02` must regenerate every count, dependency closure, path
disposition, and content hash from the approved object; no local filesystem
state may supplement it. See `SADDLE-SEED-CHECKPOINT-2026-07-17.md` for the
open-finding carry-forward register.

## 2. Baseline package closure

At `df119fb…`, Cargo metadata reports:

- 47 workspace packages total;
- 32 product packages under `crates/`;
- four additional internal packages in the complete dependency closure; and
- 36 packages in the independent import closure.

The 32 product packages contain 282 tracked files. The four support packages contain 103 tracked files. The minimum native package import therefore covers 385 tracked files before root manifests, contracts, console, deployment, CI, integrity tooling, docs, and evidence.

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

`mai-scheduler` is not a Cargo dependency of the product closure. It contains 46 Rust files and approximately 15,467 Rust lines focused on inference-request routing, GPU topology, batching, KV-cache locality, and power-aware placement. The existing orchestration scheduler contains nine Rust files and approximately 2,105 Rust lines focused on estate placement and fail-closed attestation.

Do not import `mai-scheduler` blindly and do not discard it without review. `SAD-02` must disposition its modules:

- extract GPU topology, extended-resource, locality, and power-scoring techniques when they strengthen Saddle workload placement;
- keep inference batching, KV-cache, and request-level routing in the AOG runtime domain unless a declared Saddle plugin needs them; and
- reject absence-as-optimism or any signal that cannot be traced to a current node/resource observation.

This is reuse analysis, not permission to weaken the full professional scheduler target.

## 3. Required non-package import surface

### 3.1 Import and adapt as a unit

- root Rust build/reproducibility files: `Cargo.toml`, `Cargo.lock`, `deny.toml`, `.cargo/`, toolchain files if present, `.editorconfig`, `.gitignore`, `.dockerignore`;
- secret-scanning configuration: `.gitleaks.toml`, `.secrets.baseline`, and the serial detector tooling, after verifying the baseline contains no suppressed live secret;
- all four contract specifications in `contracts/`;
- the complete 39-file `console/` tree;
- `.githooks/`, `.integrity/`, and applicable `.github/` policy/workflows, rewritten for the target repository and renamed packages;
- product deployment roots: `appliance`, `live-integration`, `loom-harness` (renamed), `openbao-staging` tracked templates, `policy-packs`, `shadow`, `supply-chain`, and `wsf-ha`;
- WSF/AOG/Saddle architecture, operations, runbooks, security findings, session DEVLOGs, and claim evidence selected by the coverage ledger; and
- license, notice, provenance, and release-policy material needed to redistribute every imported file.

### 3.2 Coverage baseline outside packages

The planning scan found 116 tracked source-like files outside the package closure that directly mention WSF, AOG, Loom, Saddle, or `fabric-*`:

| Area | Matching files |
|---|---:|
| Root | 4 |
| `.cargo` | 1 |
| `.github` | 3 |
| `.integrity` | 3 |
| `console` | 21 |
| `contracts` | 4 |
| `deployment` | 24 |
| `docs` | 29 |
| `mai-vault` | 1 |
| `test-evidence` | 25 |
| `tools` | 1 |

This search is only a lower bound. `SAD-02` must also follow build references, links, workflow inputs, Docker copy paths, schema imports, and claim-to-evidence links. Every match receives `import`, `extract`, `historical-evidence`, or `exclude-with-reason`; zero entries may remain undispositioned.

### 3.3 Explicit initial exclusions

The following seed areas are outside the verified package dependency closure and are not copied merely because they share the monorepo:

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
