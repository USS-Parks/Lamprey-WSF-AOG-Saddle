# Saddle Current-State Gap Matrix

**Date:** 2026-07-16

**Target repository:** `USS-Parks/Lamprey-WSF-AOG-Saddle`

**Inventory baseline:** Mighty Eel OS `origin/main` at `df119fb6321e60e8cfffc1b36281ba95f9f5004a`

**Governing plan:** `SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`

**Architecture contract:** `SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md`

## 1. Verdict

The baseline contains a serious, reusable distributed control-plane foundation. It does **not** yet constitute the independent Saddle project, the complete WSF-AOG bridge, or the Kubernetes-level scheduler/orchestrator defined by the governing contract.

At the target scope, **0 of 20 Saddle conformance bars are complete**. This is not a finding that the baseline has no value. It means that existing evidence was produced for a different repository identity, narrower resource model, smaller conformance profile, incomplete authorization bridge, and simpler scheduling lifecycle. Evidence may be reused, but it must be reproduced after the source import and Saddle rename and must satisfy the stronger acceptance bars.

No seed product source has been imported into the target repository as of the
SAD-02 assessment. The target now contains committed governance, a pinned
source decision, and a deterministic tracked-path/hash ledger; it remains a
planning-and-evidence repository until the SAD-03 no-secret import gate passes.

## 2. Status Vocabulary

| Status | Meaning |
|---|---|
| Present | The baseline has a usable implementation of the capability, but independent-repository verification may still be required. |
| Partial | A meaningful implementation exists, but one or more contract requirements or proof obligations are absent. |
| Missing | No implementation matching the target contract was found. |
| Blocked | Work depends on an unresolved source, security, or governance gate. |

No row marked Present or Partial is automatically accepted for Saddle. The governing PSPR gate remains authoritative.

## 3. Project and Component Matrix

| Area | Baseline status | Evidence and gap | Required Saddle work |
|---|---|---|---|
| Independent source tree | Missing | Target repository contains no imported product source. | Import the complete tracked, non-secret WSF/AOG dependency closure from an approved Git object. |
| Saddle identity | Complete | SAD-20 moved the canonical package/binary set; SAD-21 moved active runtime identities with no aliases; SAD-22 proved versioned migration and exact rollback; SAD-23 scanned 952 tracked files plus generated metadata, schemas, help, artifacts, and UI with zero unexplained active matches. | Preserve the count-locked historical/migration classification registry as later prompts add surfaces. |
| Durable store | Partial | `aog-store` provides OpenRaft consensus, snapshots, watches, and compare-and-swap behavior. Target scale, upgrade, recovery, and independent-repo evidence are absent. | Rename to `saddle-store`; prove linearizability, quorum safety, restore, upgrade, and target profiles. |
| Wire and transport security | Partial | `saddle-wire` enforces `spiffe://saddle/node/<id>` identities and the real three-node mutual-TLS trust-boundary tests pass. Target release/scale profiles and broader grant continuity remain absent. | Preserve exact Saddle node identity while proving the target profile, rotation, partition, and end-to-end grant boundaries. |
| API and admission | Partial | SAD-31 wires every HTTP mutation through server-derived `SaddleAdmission` context, a current signed monotonic revocation snapshot, current bundle, budget/caveat checks, one-use nonce, exact tenant/resource scope, deny-wins AOG decision, and a durable pre-mutation audit outbox carrying the exact admission grant. The real API adversarial suite passes. `admit_system` and `Principal::system` remain an explicit internal-controller seam. | In SAD-33, replace or strictly test-confine the internal system seam with authenticated workload identity and grants on every production controller path. |
| WSF-AOG bridge | Partial | SAD-30 froze the non-deserializable request/admission/placement/runtime/action contracts. SAD-31 consumes `VerifiedSaddleRequest` and `AdmissionGrant` through real CRUD. SAD-32 makes anchor-signed node attestation, heartbeat/attestation/provider freshness, ring, classification, measurement, air-gap, provider/model, and full declared capacity hard scheduling predicates. | Replace the internal controller seam, bind `PlacementGrant`/`RuntimeGrant` into controller-node handoff, add per-action enforcement, and prove the live two-tenant path in SAD-33 through SAD-35. |
| Controller manager | Partial | `aog-controller` has leader-gated reconciliation, work queues, backoff, finalizers, rollout, node, revocation, and maintenance controllers. The expanded resource model and bridge-bound grants are absent. | Rename; add all new reconcilers and make controller actions incapable of bypassing WSF authority. |
| Scheduler | Partial | `saddle-scheduler` has deny-wins freshness, ring, anchor-signed attestation, measurement, air-gap/connectivity, provider/model, and CPU/memory/GPU/slot capacity filters; utilization/spread scorers; traceable signals; deterministic selection; and limited preemption. SAD-32 proves pressure, failover, and stale cache cannot relax them. It remains a filter-score selector, not the complete required framework. | Implement the full extension cycle, fairness, reservations, permits, gang semantics, quotas, topology, disruption policy, grant-aware filtering, and atomic binding. |
| Node runtime | Partial | `aog-node` has workload drivers, process and containerd execution paths, attestation, and mode gating. Explicit Saddle runtime grants and lease semantics are absent. | Rename; enforce RuntimeGrant at the last responsible moment and implement NodeLease behavior. |
| Federation | Partial | Existing federation concepts are reusable. Cross-estate authorization, failure isolation, and target conformance are not established. | Rename; bind federation to Saddle grants and prove partition and recovery behavior. |
| CLI and operator UX | Partial | `aogctl` provides a starting surface. The command, configuration, diagnostics, and output identity remain AOG-oriented. | Rename to `saddlectl`; add health, scheduling trace, resource, drain, upgrade, and recovery workflows. |
| Conformance harness | Partial | The baseline has an eight-bar live suite and a smaller five-control-plane/five-edge, 100-object profile. It does not cover the 20 Saddle bars or target release and scale profiles. | Rename and expand the harness; preserve old bars as characterization evidence only. |
| Operations and release | Missing | No independent Saddle artifact provenance, upgrade matrix, disaster-recovery proof, or signed release exists. | Build reproducible releases, SBOM/provenance, upgrade/rollback, recovery, and operator runbooks in the target repo. |

## 4. Scheduler Contract Matrix

| Scheduler requirement | Status | Current evidence | Contract gap |
|---|---|---|---|
| Hard feasibility filters | Partial | SAD-32 hardens heartbeat and attestation freshness, exact ring/classification/measurement, air-gap/connectivity, current provider/model eligibility, and declared CPU/memory/GPU/slot capacity. All run before score and fail closed on missing state. | Add tenant/estate, quota, runtime-class, topology, placement-group, disruption, lease, and grant-aware filtering. |
| Pluggable scoring | Partial | Utilization and spread scorers implement weighted signals. | Add formal PreScore/Score phases, normalization, configuration validation, and contract-level determinism. |
| QueueSort | Missing | No scheduler queue extension point was found. | Add tenant-, priority-, age-, and gang-aware queue ordering. |
| PreFilter and PostFilter | Missing | No extension lifecycle exists around filters. | Add precomputation and structured unschedulable/preemption processing. |
| Reserve and Unreserve | Missing | No reservation phase or rollback contract was found. | Atomically reserve resources and unwind every failed Permit/PreBind/Bind path. |
| Permit | Missing | No wait/approve/reject scheduling phase was found. | Support gang admission and asynchronous policy approval without leaking reservations. |
| PreBind, Bind, and PostBind | Missing | Placement selection is not an explicit transactional bind lifecycle. | Bind against coherent resource versions and publish auditable outcomes. |
| Coherent snapshot scheduling | Partial | Store revisions and controller reconciliation provide useful primitives. | Define and test the exact snapshot/revision contract across queue, filter, reserve, and bind. |
| Deterministic tie-breaking | Partial | The baseline selects deterministically, including node-name ordering. | Tie-break on stable identity plus generation/revision and prove repeatability across replicas. |
| Quotas | Missing | ResourceQuota is absent from the estate model. | Implement hard tenant/project quotas with admission and scheduler enforcement. |
| Dominant-resource fairness | Missing | No DRF or starvation-control implementation was found. | Implement weighted DRF across CPU, memory, accelerators, and configured extended resources. |
| Priority and preemption | Partial | Deterministic single-victim lower-priority preemption exists for capacity pressure. | Add PriorityClass, disruption budgets, multi-victim optimization, fairness safeguards, and rollback. |
| Gang scheduling | Missing | No PlacementGroup, min-member, all-or-nothing reserve, or permit flow exists. | Implement atomic group admission and failure-safe release. |
| Topology and accelerator locality | Partial | Some reusable topology/locality work exists outside the control scheduler in `mai-scheduler`. | Extract only suitable infrastructure; keep request-level batching/KV behavior in AOG and add explicit topology resources. |
| Signal provenance | Present | Scheduling signals and decisions are traceable. | Preserve provenance through all new phases and bind it to immutable grant/audit identifiers. |
| Runtime authorization | Missing | Admission context exists, but no explicit RuntimeGrant is required by the scheduler-node handoff. | Make a valid, scoped, unexpired RuntimeGrant structurally mandatory for execution. |

## 5. WSF-AOG Bridge Matrix

| Bridge requirement | Status | Current evidence | Required correction |
|---|---|---|---|
| WSF principal | Present | `fabric-contracts` defines `WsfPrincipal`. | Preserve as the root workload identity and version its serialization contract. |
| Canonical resource identity | Present | `CanonicalResource`, tenant scope, and estate scope exist. | Extend canonical addressing to every new Saddle resource. |
| Verified request context | Present | API admission creates `VerifiedRequestContext` after WSF verification. | Make it an input to an explicit Saddle bridge rather than a locally trusted convention. |
| Per-request WSF verification | Present | API authentication verifies the WSF token for requests. | Prove live issuer, revocation, audience, scope, and clock-failure behavior in Saddle conformance. |
| Typed grant progression | Complete | `saddle.bridge/v1` defines private-field, serialize-only verified request, admission, placement, runtime, and action grants. Compile-fail and adversarial property tests prove construction, narrowing, isolation, replay, revocation, and policy fences. | Preserve this contract while wiring each real producer/consumer; version any incompatible change. |
| Controller workload identity | Missing | A system principal/admission seam exists. | Give each controller a WSF identity and narrowly scoped grants; eliminate production ambient authority. |
| Revocation propagation | Partial | Revocation intent and controllers exist. | Prove bounded propagation through bridge, controller, scheduler, node, gateway, and tool execution. |
| Durable audit handoff | Present | Admission has durable audit outbox/recovery machinery. | Bind records to Saddle request, grant, placement, runtime, and action identifiers. |
| Authorized AOG dispatch | Partial | Gateway authorized-dispatch hardening exists in the seed lineage. | Import only after seed reconciliation and reproduce live WSF-to-AOG authorization evidence. |
| Tool mint and execution | Blocked | T5 is a verified local transplant candidate onto the published T4-plus-repairs baseline, but is not published; no production credential-minter/approval/executor composition exists for T6. | Publish the reconciled T5 state and complete or explicitly transfer the full T6 live gate before approving the import pin. |
| Fail-closed behavior | Partial | Multiple baseline paths fail closed, but the system-admission seam breaks the global claim. | Make absence, expiry, ambiguity, and unavailable trust state deny every privileged production action. |

## 6. Conformance Gap Matrix

The acceptance bar is the target Saddle contract, not merely the presence of a related unit or integration test.

| Bar | Target behavior | Status | Current evidence and missing proof |
|---|---|---|---|
| SC-01 | Resource schemas, defaulting, validation, conversion, and compatibility | Partial | Existing estate resources validate core objects; the six new scheduling resources, conversion webhooks, and compatibility matrix are absent. |
| SC-02 | Linearizable writes and coherent reads at target load | Partial | OpenRaft and compare-and-swap tests are reusable; target release/scale profiles and independent-repo evidence are absent. |
| SC-03 | Watch correctness, compaction, reconnect, and no silent gaps | Partial | Watch primitives exist; target churn, compaction, reconnect, and gap-detection proof is incomplete. |
| SC-04 | Idempotent, convergent reconciliation | Partial | Existing controller conformance covers idempotence at smaller scope; new resources, grants, failure modes, and profiles are untested. |
| SC-05 | Correct filtering with explainable rejection reasons | Partial | Strong baseline filters and trace signals exist; contract-required filters and stable cross-replica explanations are incomplete. |
| SC-06 | Weighted dominant-resource fairness and starvation bounds | Missing | No DRF or formal starvation-bound implementation was found. |
| SC-07 | Priority, preemption, disruption budgets, and safe rollback | Missing | Limited single-victim preemption is not sufficient; PriorityClass and DisruptionBudget do not exist. |
| SC-08 | Atomic gang scheduling and placement-group semantics | Missing | No PlacementGroup resource or reserve/permit lifecycle exists. |
| SC-09 | Leader election, quorum loss, and split-brain safety | Partial | Existing five-control-plane split-brain evidence is useful; target profiles, upgrade interaction, and full Saddle identity remain unproven. |
| SC-10 | Node lease expiry, partition, drain, and recovery | Partial | Node reconciliation and health behavior exist; NodeLease, drain semantics, and bounded recovery proofs are absent. |
| SC-11 | Process and container runtime parity under explicit grants | Partial | Process and containerd drivers exist; RuntimeGrant enforcement and parity at target profiles are missing. |
| SC-12 | End-to-end WSF identity and grant continuity | Partial | SAD-30 proves the isolated `saddle-bridge` grant chain and invariants, but real admission/scheduler/node/AOG consumers are not yet wired and a system bypass remains. |
| SC-13 | Authorized AOG gateway, tool mint, and execution | Blocked | Gateway work is reusable and T5 passes on the repaired baseline, but T5 is not published and the T6 production tool path does not exist. |
| SC-14 | Kill switch and revocation under scale and offline conditions | Partial | A smaller kill-switch-under-scale bar exists; target scale, offline nodes, and end-to-end grant revocation are not proven. |
| SC-15 | Audit completeness, ordering, recovery, and tamper evidence | Partial | Durable audit recovery and broader compliance audit machinery exist; full Saddle causal linkage and target fault proof are absent. |
| SC-16 | Federation partition isolation and safe convergence | Partial | Federation primitives exist; cross-estate grants, partition matrix, and convergence at target scope are incomplete. |
| SC-17 | Release-profile SLOs and capacity targets | Missing | The required 5-control-plane, 10-live-node, 1,000-object, 10-tenant, 100-workload profile has not been certified. |
| SC-18 | Scale profile, 24-hour soak, and 100 injected faults | Missing | The required 100-node, 10,000-object, 50-tenant, 1,000-process, 100-container profile has not been run. |
| SC-19 | N-1 upgrade, rollback, and storage compatibility | Missing | No Saddle release upgrade/rollback matrix or N-1 compatibility evidence exists. |
| SC-20 | Independent, reproducible, signed source and release provenance | Missing | No source is imported; no independent build, SBOM, provenance, signed artifact, or clean-room reproduction exists. |

## 7. Critical Path

1. **Reconcile the seed truth.** Complete: `SAD-01` selected published signed seed `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`, and maps every open source hardening prompt into Saddle.
2. **Perform the safe tracked-source import.** `SAD-02` generated the 1,491-path source/hash/disposition ledger. `SAD-03` must run two independent secret scanners and prove no submodule, ignored file, local working-tree file, or credential enters the target.
3. **Complete the Saddle rename.** Complete: SAD-20 through SAD-23 moved package, binary, runtime, protocol, trust, persistence, deployment, API, fixture, CI, and operator-document identity; proved versioned legacy-state migration with exact rollback; and closed the count-locked active-name eradication gate. Retired terminology remains only in reviewed historical provenance, named migration fixtures, and verifier inputs.
4. **Create the authority bridge.** SAD-30 completed the explicit typed contract and compatibility/property gate; SAD-31 completed real WSF-authenticated admission plus durable grant/audit linkage; SAD-32 completed WSF-attested hard placement feasibility. SAD-33 through SAD-35 must wire controller identities and placement/runtime grants, runtime/action enforcement, the live two-tenant gate, and remove production system bypasses.
5. **Expand the resource and scheduler model.** Add the six scheduling resources and implement the complete queue-to-post-bind lifecycle, DRF, quota, topology, disruption-aware preemption, gangs, reservations, and atomic bind.
6. **Bind controllers and runtimes to grants.** Finish resource reconcilers, lease/drain behavior, and last-moment RuntimeGrant enforcement for process and container execution.
7. **Build and pass conformance.** Run PR, release, and scale profiles; close SC-01 through SC-20; produce upgrade, recovery, provenance, and signed-release evidence.

## 8. Execution Rule

This matrix is inventory and planning evidence. It does not authorize STS execution, source import, commit, or push. Implementation begins only under the authorization rule in the governing PSPR and project `AGENTS.md`.

When execution begins, each PSPR prompt must update this matrix or replace it with linked verification evidence. A capability moves to complete only when its named acceptance gate passes in the independent target repository.
