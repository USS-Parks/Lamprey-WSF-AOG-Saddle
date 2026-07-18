# Saddle WSF + AOG Independent Major Project — Canonical Plan / Sequential Prompt Roster

**Initiative:** Establish Saddle as the independent Kubernetes-level scheduler and orchestrator that bridges the full WSF trust plane and AOG agentic-governance plane.
**Priority:** **P0 / project Priority 1.** The Saddle orchestration engine and its conformance gates outrank seat UX and non-critical expansion.
**Target repository:** `USS-Parks/Lamprey-WSF-AOG-Saddle`
**Local working location:** `C:\Users\17076\Documents\Claude\Mighty Eel OS\Lamprey-WSF-AOG-Saddle`
**Seed repository:** `USS-Parks/Mighty-Eel-OS`, authoritative local source at `C:\Users\17076\Documents\Claude\Mighty Eel OS\mai`
**Decision record:** `PLANNING/SADDLE-INDEPENDENCE-DECISION-2026-07-16.md`
**Source/rename manifest:** `PLANNING/SADDLE-SOURCE-AND-RENAME-MANIFEST.md`
**Architecture/conformance contract:** `PLANNING/SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md`
**Current-state gap matrix:** `PLANNING/SADDLE-CURRENT-STATE-GAP-MATRIX.md`
**Seed reconciliation:** `PLANNING/SADDLE-SEED-RECONCILIATION-2026-07-16.md`
**Current execution status (supersedes the cumulative roll-up below):** **AUTHORIZED FOR FULL STS EXECUTION — SAD-34 COMPLETE; SAD-35 NEXT.**
**Status:** **AUTHORIZED FOR FULL STS EXECUTION — SAD-31 COMPLETE; SAD-32 NEXT.** SAD-00 implementation and remote checkpoint are `d959bf0d8e7e14fdd2c73ff9bf42609a1748bd42`. SAD-01 selected signed published seed `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`; its Saddle remote checkpoint is `7f30ea691f91b3ea8774b7fd121fbc8580b1d69f`, and its open hardening obligations are mapped in `SADDLE-SEED-CHECKPOINT-2026-07-17.md`. SAD-02 generated the deterministic 1,491-path, 37-package manifest at `test-evidence/saddle/SAD-02/source-manifest.json`; its verified remote checkpoint is `d506e80aee79717b1a48817d471ce9e89ca934c2`. SAD-03 proved the 898-path tracked-only staged import with zero unsuppressed findings from both independent scanners at `test-evidence/saddle/SAD-03/no-secret-import-proof.json`; its verified remote checkpoint is `bbb19934c7b1866c44d8719c00fc575b09b43988`. SAD-10 materialized the verified 37-package native closure and passed `cargo metadata --no-deps --locked` with zero external local paths, recorded in `test-evidence/saddle/SAD-10/workspace-import-proof.json`. SAD-11 materialized the remaining 492 raw support/history blobs, retained the Saddle README, and recorded source-scoped formatting preservation in `test-evidence/saddle/SAD-11/support-surface-import-proof.json`. SAD-10 implementation `850628da4cffc92fc17e22811377a7c8eece1101` and SAD-11 implementation `93f2d2f7fb9cba29e27a3bf57fe5554a58de97da` published together at verified remote checkpoint `93f2d2f7fb9cba29e27a3bf57fe5554a58de97da`. SAD-12 removed functional parent-repository coupling, regenerated the 37-package closure lockfile, and passed a clean archive build; its verified remote checkpoint is `0f2dfdf87539736984d59b15dd038982e46d9c06`. SAD-13 passed formatting, locked workspace check, strict all-target clippy, full tests, audit/deny, and docs without import-induced source repair; its verified remote checkpoint is `2459b5a800493e74afde96adf43bcd5d4fe31d5b`. SAD-14 passed the console, Compose, and staging-package gates with generated ephemeral trust material, a bounded 20-path packaging addendum, zero secret findings, and zero active parent references; its verified remote checkpoint is `e7627a474bb7af8119ae7a7825c5d6146e4ba6c2`. SAD-15 passed the complete fresh-checkout M1 source, provenance, secret, no-slop, build, console, Compose, and package gates from published checkpoint `62b076ea480894e177f504a4fbea3ec638a54b3c`; its evidence closeout checkpoint is `8ab9eea32e7ee6859ac1a639449587e2b3febe46`. SAD-20 moved the exact twelve-package orchestration map and the `saddled`, `saddle-noded`, and `saddlectl` binaries with deterministic identity evidence; its implementation commit is `74e09b53038da895dc26dc71283428e25a2bbd82`, and its verification closeout/first verified remote checkpoint is `a6cdb0ed215797870dd4b483aeec868cba8147a2`. SAD-21 moved active protocol, trust, persistence, environment, API, finalizer, deployment, fixture, CI, and operator-document identities to Saddle; its implementation commit is `a9e46f013120e9afc6a4afcb6ed21cebbecfa597`, and deterministic evidence is `test-evidence/saddle/SAD-21/runtime-identity-gate.json`; its verification closeout and first verified remote checkpoint is `04a859d883268a1faa0b7b7b73e21a31d7e16b1e`, its corrective active-identity closure is `5ca45e81c3de44d5cdc1e31e1561195b1da12cc2`, and its corrective closeout/verified remote checkpoint is `3e2fef91581c786f96911b4bb607bf12ef72828a`. SAD-22 added the five-mode versioned legacy-state migration with native store adapters, exact rollback, protected authority/version invariants, and independent receipt-chain continuity; its implementation commit is `edc5b5a8328ce3dd47dfc1fe5ce2d156b63dc1c5`, deterministic evidence is `test-evidence/saddle/SAD-22/legacy-state-migration-gate.json`, and its verification closeout/first verified remote checkpoint is `f7f50efd77813e4f8b76057d38f76a99a610df60`. SAD-23 closed M2 with a count-locked tracked-file, generated-metadata, schema, help, artifact, and UI eradication gate; its implementation commit is `4f733ff7ae0e9bc30a1002838fd116c398637f22`, deterministic evidence is `test-evidence/saddle/SAD-23/active-name-eradication-gate.json`, and its verification/M2 closeout and first verified remote checkpoint is `4de1ec3671d630845fb0b4856130506509801023`. SAD-30 froze the `saddle.bridge/v1` non-forgeable grant contracts; its implementation commit is `9d173b2242720eb21e5f3ea5206022c3c77d05e8`, deterministic evidence is `test-evidence/saddle/SAD-30/bridge-contract-gate.json`, and its verification closeout/first verified remote checkpoint is `163beaeb0d842ff950ce9684ed2fb02d3af08ea5`. SAD-31 wired WSF-authenticated admission through the real Saddle API; its implementation commit is `0b3d7a648c5807d58b4575ff15d2fad9840c837c`, and deterministic evidence is `test-evidence/saddle/SAD-31/admission-gate.json`. Full execution plus commit and push authorization was granted on 2026-07-17.

**Latest verified remote checkpoint:** SAD-33 verification closeout and first verified remote checkpoint are `7a13d765ab0e07db14e698327fa7067ce120e346`.

**SAD-32 closeout:** **COMPLETE; SAD-33 NEXT.** SAD-32 makes heartbeat, anchor-signed node attestation, ring, classification, exact measurement, air-gap/connectivity, provider/model eligibility, and declared CPU/memory/GPU/slot capacity fail-closed predicates before scoring. Its implementation commit is `a87aed1604a81ea5680411dd932bc81ab2a3356e`, deterministic evidence is `test-evidence/saddle/SAD-32/attested-scheduling-gate.json`, and GitHub `main` was live-verified at the checkpoint above.

**SAD-33 closeout:** **COMPLETE; SAD-34 NEXT.** SAD-33 manages gateway, toolproxy, approvals, governed agent, and inference runtimes as Saddle workloads. The real scheduler issues placement-, node-, workload-digest-, tenant-, role-, budget-, caveat-, TTL-, and lineage-bound child capabilities; `NodeRuntime` verifies them immediately before driver start and stops missing, changed, or revoked assignments. The live gate proves start, scale, digest roll, sibling-token rejection, capability-root revocation, and controller-epoch revocation through real controllers, OpenBao, and the process driver. Its implementation commit is `57616b479b66ea582369d85cd9d2a74fe684b09f`, deterministic evidence is `test-evidence/saddle/SAD-33/aog-workload-integration-gate.json`, and GitHub `main` was live-verified at the checkpoint above with the evidence blob matching local Git.

**SAD-34 local closeout:** **IMPLEMENTATION AND GATES COMPLETE; SAD-35 NEXT.** SAD-34 adds a non-forgeable `ActionGate` for exact model/tool/control actions. It binds receipt intent to the request digest, consumes a lineage-scoped nonce, reserves the runtime budget atomically across destinations, commits a metadata-only WSF-ledger authorization proof, then rechecks current revocation and action expiry immediately before invoking the private effect. The adversarial gate proves cross-tenant theft, replay, revocation/expiry races, budget races, receipt mismatch, and unavailable/empty receipt proof cannot reach an effect. Its implementation commit is `3d65900c870e10a812cc1468e3b005cfce96a931`, deterministic evidence is `test-evidence/saddle/SAD-34/action-reauthorization-gate.json`, and remote publication remains pending this closeout commit. The generic enforcement layer is complete; persisted typed `RuntimeGrant` handoff and composition of the real gateway/toolproxy/control consumers remain explicitly assigned to the SAD-35 live two-tenant gate.

---

## 0. Governance

### 0.1 Source of truth and precedence

This PSPR is the canonical plan for the independent Saddle project. It supersedes only the conflicting forward-looking decisions in `SADDLE-FOUNDING-DIRECTION.md`: artifact-only WSF/AOG consumption, seat-only scope, and parked orchestration. It does not rewrite executed Mighty Eel OS history.

Precedence for this initiative:

1. the user's current instruction;
2. `SADDLE-INDEPENDENCE-DECISION-2026-07-16.md`;
3. this PSPR plus its source/rename, architecture/conformance, current-state gap, and seed-reconciliation specifications;
4. the execution DEVLOG;
5. project `AGENTS.md`;
6. imported historical plans and evidence.

Historical material may say Loom. Active project truth says Saddle.

### 0.2 Settled architecture

| Plane | Native source in this repo | Contract |
|---|---:|---|
| WSF trust plane | Yes, complete | Identity, tokens, attenuation, envelopes, revocation, credentials, receipts |
| AOG governance plane | Yes, complete | Gateway, policy, tools, approvals, budgets, metering, agent controls |
| Saddle orchestration plane | Yes, Priority 1 | Desired state, admission, consensus, scheduler, controllers, nodes, HA/DR, federation, conformance |
| Saddle client/seat | Yes, downstream milestone | First-party governed user surface; may not bypass or replace server-side controls |

Saddle binds WSF authority to every AOG workload and action. `saddle-store` holds desired state; the WSF ledger holds proof. Those stores remain physically and semantically separate.

### 0.3 Independence definition

The project is independent only when a clean checkout can build, test, package, and run its required live gates without:

- a local Mighty Eel OS or Lamprey Harness checkout;
- a Git submodule, symlink, or path dependency outside this repository;
- a build-time source download from either parent repository;
- an unpublished internal binary supplied manually; or
- a secret copied from a developer workstation.

Registry dependencies locked in the repository are allowed. Signed third-party and release artifacts remain supported inputs, not substitutes for owned source.

### 0.4 Source completeness definition

“WSF and AOG LOC in their entirety” includes:

- every tracked file under the seed repository's `crates/` product tree, including all `fabric-*`, `wsf-*`, `aog-*`, orchestration, conformance, and `hipaa-pack` crates;
- the complete internal Cargo dependency closure required by those crates (currently observed: `mai-agent`, `mai-compliance`, `mai-core`, and `mai-router`; execution re-computes this at the pinned seed SHA);
- tests, benches, examples, fixtures, schemas, migrations, and build scripts inside those packages;
- WSF/AOG contracts, console/client source, deployment profiles, policy packs, live-gate harnesses, CI, integrity tools, runbooks, and evidence that substantiate product claims; and
- a machine-readable provenance manifest mapping every imported path and hash to the pinned source SHA.

The import gate is coverage-based: every source-like seed file matching the WSF/AOG/Saddle domains must be imported or receive an explicit, reviewed exclusion disposition. A directory-name allowlist alone is insufficient.

### 0.5 Secret boundary

Imports operate on tracked files from a pinned commit, never the working tree. The following are categorically excluded: `.git`, `.env` other than verified placeholder examples, private keys, live tokens, credentials, local OpenBao state, generated certificates, machine identity, caches, logs, `target/`, `node_modules/`, and test runtime output.

Before staging any import:

1. scan the source snapshot and destination with at least two independent secret detectors;
2. scan for PEM private-key markers, cloud/token formats, credential-bearing URLs, high-entropy additions, and forbidden filenames;
3. verify placeholder examples contain no usable values;
4. generate needed test PKI at runtime; and
5. stop for rotation and history-remediation direction if any real credential is found.

“Ignored by Git” is not proof of safety. The staged tree is the final scan target.

### 0.6 Naming and compatibility

Saddle replaces Loom on every active identity surface, including package names, binaries, images, service names, environment variables, headers, SPIFFE paths, OpenBao paths, resource groups/finalizers, metrics, dashboards, deployment directories, tests, and docs.

Historical plans and commit provenance remain immutable. Legacy persisted-state conversion may recognize old identifiers only inside a versioned migration boundary. Normal runtime emits Saddle identities only. Compatibility must never preserve an insecure fallback.

### 0.7 Verification gates

Every implementation prompt must pass its focused tests plus the applicable project gates:

```text
cargo fmt --check
cargo check --workspace --all-targets
cargo clippy --workspace --all-targets -- -D warnings -A clippy::pedantic
cargo test --workspace
cargo deny check
console lint/typecheck/test/build gates when console code is present
secret scans against the staged tree
no-slop and repository integrity hooks
git diff --check
```

Trust-, credential-, policy-, consensus-, scheduling-, and integration-adjacent claims require live evidence; mock-only coverage cannot close them. Windows mTLS tests must run with a verified OpenSSL implementation on `PATH`.

### 0.8 STS and Git authority

Drafting or revising this PSPR was not authorization to execute it. Full STS execution plus commit and push authorization was granted by the owner on 2026-07-17. That authorization is durable for all in-scope prompt commits, verification closeouts, and pushes to `main`; it excludes force-push, history rewriting, deployment, credential rotation, paid services, and unrelated changes.

STS authorizes reversible repository-local edits and verification in roster order. It does not by itself authorize commits or pushes. `Commit and push` is durable authorization for the in-scope publish sequence under the workspace rule. No force-push, history rewrite, production deployment, credential rotation, or unrelated-repository mutation is implied.

### 0.9 Prompt and DEVLOG discipline

- Execute in dependency order, one focused prompt per commit or a narrowly justified bundle.
- Use an isolated worktree for concurrent sessions; never share a Git index.
- Maintain `docs/sessions/SADDLE-DEVLOG.md` with prompt ID, source pin, files, gates, evidence, commit SHA, push state, and next prompt.
- Do not mark a prompt complete until every stated gate passes.
- If a source drift occurs before cutover, record it and re-run the coverage/hash gates.
- After the authority cutover, do not dual-write WSF/AOG/Saddle changes in Mighty Eel OS.

### 0.10 Explicit exclusions

- Rebuilding Kubernetes as a general-purpose container platform.
- Copying unrelated MAI product source that is neither part of WSF/AOG nor in the verified dependency closure.
- Importing Lamprey Harness before the orchestration critical path is independently green.
- Redesigning settled cryptographic primitives without a validated finding.
- Publishing, releasing, or deploying before the relevant milestone gate.

---

## 1. Milestones

| Milestone | Usable cut | Prompts |
|---|---|---|
| M0 — Truth and safe seed | Exact source pin, full coverage ledger, no-secret import mechanism | `SAD-00`–`SAD-03` |
| M1 — Independent source | Complete WSF/AOG/Saddle code builds and tests in this repo | `SAD-10`–`SAD-15` |
| M2 — Saddle identity | Active Loom identity eliminated; versioned legacy migration proven | `SAD-20`–`SAD-23` |
| M3 — WSF↔AOG bridge | WSF authority is mandatory across Saddle admission/scheduling and AOG actions | `SAD-30`–`SAD-35` |
| M4 — Kubernetes-level orchestration | Consensus, reconciliation, scheduling, node runtime, HA/DR/federation, conformance green | `SAD-40`–`SAD-49` |
| M5 — Independent ship | Supply chain, operator install, governed seat, evidence, and release candidate | `SAD-50`–`SAD-56` |

Priority rule: M4 work is the critical path. M5 seat work cannot consume the project lane while any M1–M4 gate is open.

---

## 2. Reuse and migration ledger

| Source area | Treatment | Destination intent |
|---|---|---|
| `crates/fabric-*`, `crates/wsf-*` | Import complete, then own | WSF plane |
| AOG gateway/toolproxy/approvals and related crates | Import complete, then own | AOG plane |
| Existing orchestration crates (`aog-store`, scheduler, node, controller, etc.) | Import complete, then rename and evolve | `saddle-*` plane |
| `crates/hipaa-pack` and policy packs | Import complete | Governed policy/evidence vertical slice |
| `mai-agent`, `mai-compliance`, `mai-core`, `mai-router` | Import complete dependency closure; rename/extract later only with gates | Shared internal support |
| Contracts and schemas | Import complete and version | Stable cross-plane contracts |
| Console/client code with WSF/AOG behavior | Import complete or explicitly disposition by coverage ledger | Operator/client surfaces |
| Deployment/live-conformance assets | Import, scrub, rename, and regenerate runtime PKI | Independent proof harness |
| Security findings, DEVLOG, and relevant evidence | Import as provenance, preserving status | No false reset of open work |
| Lamprey Harness | Parked until M4 | Later one-time snapshot for governed seat; never linked back |
| Unrelated MAI crates | Exclude unless dependency scan proves required | Not silently copied |

Import means a pinned snapshot with hashes and provenance, not an indefinite mirror. Extraction or rename must preserve behavior through characterization tests.

---

## 3. Sequential prompt roster

### Phase 0 — Truth, freeze, and safe import design

- [x] **SAD-00 — Bootstrap execution governance.** Create the isolated worktree, DEVLOG, verification ledger, and toolchain record. Record target HEAD/status and current seed remote SHA.
  **Gate:** clean isolated target worktree; exact SHAs and tools recorded; no code imported.

- [x] **SAD-01 — Resolve the authoritative seed checkpoint.** Reconcile the active Lamprey Saddle security-hardening lane, open findings, and remote main. Select an approved source SHA; do not canonize an incomplete local-only checkpoint accidentally.
  **Gate:** one immutable seed SHA plus a list of open findings/prompts carried into Saddle.

- [x] **SAD-02 — Generate the full source-coverage manifest.** Compute Cargo dependency closure and scan all tracked source-like files for WSF/AOG/orchestration relevance. Produce imported/excluded/dispositioned path lists and per-file hashes.
  **Gate:** regenerate and reconcile `SADDLE-SOURCE-AND-RENAME-MANIFEST.md`; zero undispositioned matching files; manifest reproducible from the seed SHA; `mai-scheduler` reuse candidates explicitly dispositioned.

- [x] **SAD-03 — Prove the no-secret import path.** Build the tracked-file archive/allowlist, run independent secret scanners, identify runtime-generated PKI/state, and define replacement generation scripts.
  **Gate:** staged-import simulation has zero unsuppressed secret findings and contains no private-key material.

### Phase 1 — Complete native source and independent build

- [x] **SAD-10 — Establish the independent workspace.** Import root manifests, lock/toolchain/license files, complete `crates/`, and the verified internal dependency closure at the seed SHA.
  **Gate:** provenance hashes match; `cargo metadata` resolves with no external local paths.

- [x] **SAD-11 — Import contracts, console/client, deployments, CI, tools, docs, and evidence.** Apply the coverage ledger; preserve open finding status and executed history.
  **Gate:** every SAD-02 path imported or dispositioned; documentation does not overclaim closure.

- [x] **SAD-12 — Remove parent-repository coupling.** Replace path assumptions, repository names, release lookups, and build scripts that require Mighty Eel OS.
  **Gate:** clean checkout builds without either parent working copy; recursive scan finds no forbidden external path/submodule/symlink dependency.

- [x] **SAD-13 — Restore the complete Rust gate.** Repair only import-induced workspace issues and run formatting, check, clippy, unit/property/integration tests, deny, and docs.
  **Gate:** complete Rust gate green; failures are not waived as “migration noise.”

- [x] **SAD-14 — Restore console and deployment gates.** Prove client/console build plus Compose and packaging validation with generated ephemeral trust material.
  **Gate:** clean UI build and config validation; no secret or machine-local dependency.

- [x] **SAD-15 — M1 independent-source checkpoint.** Run completeness, hash, license/provenance, secret, no-slop, and full build gates from a fresh checkout.
  **Gate:** M1 evidence bundle proves complete native non-secret source and independent reproducibility.

### Phase 2 — Saddle replacement identity

- [x] **SAD-20 — Rename orchestration packages and binaries.** Move orchestration ownership from active `aog-*`/Loom identities to the settled `saddle-*`, `saddled`, `saddle-noded`, and `saddlectl` surfaces while leaving AOG governance crates clearly AOG.
  **Gate:** the exact package/binary map in `SADDLE-SOURCE-AND-RENAME-MANIFEST.md` is implemented; workspace builds; no duplicate active identity.

- [x] **SAD-21 — Rename protocol, trust, persistence, and deployment identities.** Migrate headers, SPIFFE IDs, resource groups/finalizers, OpenBao paths, environment variables, image/service names, metrics, fixtures, and deployment directories.
  **Gate:** new runtime emits Saddle only; compatibility cannot bypass authorization.

- [x] **SAD-22 — Versioned legacy-state migration.** Provide inspect/dry-run/apply/verify/rollback for persisted identifiers originating in the seed implementation.
  **Gate:** representative estate migrates without authority, receipt-chain, or rollback loss.

- [x] **SAD-23 — Active-name eradication gate.** Scan active source, tests, generated schemas, help text, artifacts, and UI.
  **Gate:** zero unexplained Loom references outside historical provenance and named migration fixtures.

### Phase 3 — Mandatory WSF↔AOG bridge

- [x] **SAD-30 — Establish `saddle-bridge` and freeze cross-plane contracts.** Centralize the non-forgeable verified request, admission grant, placement grant, runtime grant, action grant, revocation, receipt, and error seams defined by the architecture contract. Reuse WSF cryptography and AOG policy; do not duplicate them.
  **Gate:** compatibility matrix and property tests prove non-constructibility from wire JSON, authority narrowing, tenant isolation, replay resistance, and deny/fence semantics.

- [x] **SAD-31 — WSF-authenticated Saddle admission.** Require server-derived WSF identity, current revocation, scope, budget, caveats, final resource identity, and durable audit-before-success on privileged mutations.
  **Gate:** missing/stale/spoofed/cross-tenant authority fails closed through the real API.

- [x] **SAD-32 — WSF-attested scheduling.** Make trust ring, classification ceiling, attestation floor, air-gap compatibility, capacity, and provider eligibility hard predicates.
  **Gate:** no under-attested placement under pressure, failover, or stale cache.

- [x] **SAD-33 — AOG workload integration.** Manage gateway, toolproxy, approvals, and governed agent runtimes as Saddle workloads with least-privilege child capabilities.
  **Gate:** start/scale/roll/revoke paths pass across real controllers and nodes.

- [x] **SAD-34 — Per-action reauthorization and receipts.** Enforce current WSF authority on every AOG model/tool/control action and commit required proof before high-consequence effects.
  **Gate:** token theft, replay, revocation races, budget races, and audit failure cannot produce an allowed unreceipted effect.

- [ ] **SAD-35 — Live two-tenant bridge gate.** Exercise two tenants through live OpenBao, Saddle control plane/nodes, AOG gateway/toolproxy, revocation, policy, restart, and network transition.
  **Gate:** correct isolation, fail-closed behavior, and off-host receipt verification.

### Phase 4 — Priority-1 Kubernetes-level Saddle orchestrator

- [ ] **SAD-40 — Declarative estate and conversion.** Finalize the imported kinds plus `ResourceQuota`, `PriorityClass`, `PlacementGroup`, `DisruptionBudget`, `RuntimeClass`, and `NodeLease`; implement optimistic concurrency, watches, finalizers, sealed sensitive fields, and `saddle.islandmountain.io/v1` conversion.
  **Gate:** round-trip/conversion/fuzz tests preserve authority, UID, generation, resource version, desired state, and legacy-state rollback.

- [ ] **SAD-41 — Consensus truth and fencing.** Prove linearizable writes, leader transitions, snapshots, membership change, bounded-stale watches, and minority fencing.
  **Gate:** Jepsen-style concurrency and partition tests show no stale authoritative allow.

- [ ] **SAD-42 — Level-triggered reconciliation.** Prove idempotency, replay, duplicate/drop tolerance, backoff, resync, finalization, and convergence.
  **Gate:** fault-injected histories converge to the same state.

- [ ] **SAD-43 — Professional scheduler framework and fairness.** Implement the ordered queue-sort through post-bind plugin cycle, coherent snapshots, hard trust/resource/topology filters, weighted dominant-resource fairness, quotas, priority, atomic reserve/unreserve, permit, gang scheduling, deterministic binding, preemption, spread, accelerator topology/locality, budget/ROI scoring, and starvation resistance.
  **Gate:** deterministic property tests plus adversarial multi-tenant/gang load prove no sovereignty bypass, double bind, quota/capacity oversubscription, leaked reservation, or feasible-work starvation.

- [ ] **SAD-44 — Node runtime and attestation liveness.** Harden registration, workload drivers, heartbeats, drift eviction+revocation, local fail-static enforcement, and offline operation.
  **Gate:** drifted workloads are evicted and revoked; stale nodes cannot accept new authority.

- [ ] **SAD-45 — Deterministic rollout and rollback.** Prove progressive rollout, health gates, signed rollback, disruption limits, and failed-update recovery.
  **Gate:** every injected rollout failure returns to the prior signed state.

- [ ] **SAD-46 — HA, DR, and federation.** Prove multi-node control plane, encrypted backup/restore, signed offline snapshots, conflict rules, and air-gap federation.
  **Gate:** destructive-loss drill and cross-boundary verification complete with no live egress requirement.

- [ ] **SAD-47 — Kill switch under scale and partition.** Revoke estate/workload/tool/model authority across replicas, leaders, partitions, offline nodes, and queued work.
  **Gate:** next prohibited action is denied everywhere within the declared SLO; minority partitions fence.

- [ ] **SAD-48 — Scale, chaos, and soak.** Execute the functional, release, and scale profiles plus the initial SLOs in `SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md`; include 24-hour scale soak and at least 100 injected fault cycles.
  **Gate:** raw percentile/SLO report green with no unexplained leak, deadlock, lost intent, orphan grant, double bind, or unreceipted authority.

- [ ] **SAD-49 — Saddle conformance claim.** Preserve the seed eight-bar suite as characterization, then implement SC-01 through SC-20 so every Kubernetes-level correctness, bridge, operations, scale, upgrade, and independent-release claim maps to code and live evidence.
  **Gate:** every required bar passes with zero pending; external wording states the exact AOG workload-domain breadth and avoids claiming general-purpose Kubernetes compatibility.

### Phase 5 — Independent product ship

- [ ] **SAD-50 — Supply chain and release provenance.** Reproducible builds, SBOM, signatures, provenance, license inventory, vulnerability gates, and no-phone-home proof.
  **Gate:** release artifacts verify from a clean trust root.

- [ ] **SAD-51 — Operator install and upgrade.** Standalone, HA, air-gap, backup, upgrade, rollback, and incident runbooks tested by procedure alone.
  **Gate:** clean-room install and N-1 upgrade/rollback drill green.

- [ ] **SAD-52 — Governed seat bootstrap.** Only after M4, import/adapt the approved Lamprey Harness snapshot into a repository-local client app with no direct-provider or governance-bypass path.
  **Gate:** all traffic/actions use the native stack; source separation from the OSS repo remains intact.

- [ ] **SAD-53 — Seamless cloud/local and offline UX.** Route visibility, Ring-3 transition, local denial behavior, receipt continuity, and enrollment.
  **Gate:** cable-pull demo continues locally without broken receipt lineage or hidden fallback.

- [ ] **SAD-54 — Independent security review.** Threat-model refresh, deep scan, dependency review, live abuse cases, and closure ledger.
  **Gate:** zero open Critical/High findings and no unexplained coverage gaps.

- [ ] **SAD-55 — Buyer/operator evidence.** Architecture, trust boundaries, limitations, conformance scope, evidence-pack export, and claim-to-test matrix.
  **Gate:** every external claim maps to current executable evidence.

- [ ] **SAD-56 — Release candidate.** Fresh-checkout full gates, signed artifacts, install/upgrade/DR/conformance replay, release notes, and version tag preparation.
  **Gate:** independently approvable RC bundle; tagging/publishing still requires explicit authorization.

---

## 4. Completion criteria

The initiative is complete only when:

1. `USS-Parks/Lamprey-WSF-AOG-Saddle` contains complete non-secret WSF and AOG source plus the independent dependency closure;
2. the Kubernetes-level scheduler/orchestrator is actively named Saddle everywhere and is the repository's verified Priority-1 system;
3. no release build depends on a parent source checkout, submodule, symlink, or hidden credential;
4. WSF authority is mandatory across Saddle admission/scheduling and every AOG action/workload;
5. consensus, reconciliation, scheduling, node, rollout, HA/DR, federation, kill-switch, scale, chaos, and conformance gates are green;
6. the active security lane and all imported findings have honest dispositions;
7. a fresh checkout reproduces build, test, package, and evidence generation; and
8. the release claim is precise: Kubernetes-level orchestration correctness for the declared AOG workload domain, not a general Kubernetes replacement.

The completion audit must evaluate the full `SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md`; the seed's existing eight-bar conformance report cannot by itself close this project.

Until all eight hold, the project remains in execution and no document may claim the independent stack is complete.
