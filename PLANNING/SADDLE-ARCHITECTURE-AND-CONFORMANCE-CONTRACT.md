# Saddle Architecture and Conformance Contract

**Purpose:** Define what “Kubernetes-level, professional, independent scheduler/orchestrator bridging WSF and AOG” means in executable terms.
**Authority:** Supporting specification for `SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`.
**Status:** Settled target contract; values may be raised by an approved PSPR addendum but not silently weakened during implementation.

## 1. Product boundary and claim

Saddle is a declarative, highly available orchestration control plane for the AOG workload domain. It is Kubernetes-level in **control-plane and scheduler correctness**, not a claim of Kubernetes API, ecosystem, or arbitrary-workload compatibility.

Saddle must provide:

- versioned declarative resources and optimistic concurrency;
- a linearizable consensus-backed desired-state store;
- authenticated admission as the only authoritative writer;
- level-triggered, idempotent controllers;
- a queueing, plugin-based, multi-tenant scheduler with atomic reservation/bind;
- attested node identity and workload lifecycle management;
- deterministic rollout, rollback, disruption, and self-healing behavior;
- HA, backup/restore, air-gap operation, and signed federation;
- executable conformance, performance, chaos, upgrade, and security evidence; and
- native WSF authority and AOG governance on every relevant path.

Saddle does not promise CNI, CSI, Helm, arbitrary Kubernetes CRDs, general container hosting, or compatibility with `kubectl`. AOG gateways, tool proxies, governed agents, inference services, and their supporting control workloads are the declared domain.

## 2. Three-plane architecture

| Plane | Owns | Must not own |
|---|---|---|
| WSF | Identity, capabilities, attenuation, revocation, envelopes, ephemeral credentials, receipt proof | Desired-state consensus or scheduling policy |
| AOG | Model/tool policy, approvals, budgets, metering, route/tool execution controls | Cluster authority or ungoverned credentials |
| Saddle | Admission, desired state, scheduling, reconciliation, node runtime, rollout, HA/DR, federation | Cryptographic reimplementation or direct-provider bypass |

`saddle-store` holds mutable desired state. `wsf-ledger` holds append-only proof. Saddle may reference receipt IDs; it never turns the desired-state store into the proof ledger.

## 3. Required component set

| Component | Responsibility |
|---|---|
| `saddle-estate` | Versioned resources, validation, defaulting, conversion, status/condition vocabulary |
| `saddle-store` | OpenRaft state machine, CAS, watches, snapshots, membership, compaction |
| `saddle-wire` | Mutually authenticated control-plane transport and canonical peer identity |
| `saddle-apiserver` | Authentication, authorization, admission, conversion, CRUD/watch, audit barrier |
| `saddle-bridge` | The explicit WSF↔Saddle↔AOG authority, attenuation, revocation, and receipt seam |
| `saddle-controller` | Informers, queues, leader-gated reconcilers, finalizers, rollout, lifecycle controllers |
| `saddle-scheduler` | Queueing, filter/score framework, reservations, permits, binding, fairness, preemption |
| `saddle-node` | Node identity, local admission, drivers, probes, attestation liveness, drain/evict |
| `saddle-noded` | Node daemon and control-plane watch/heartbeat client |
| `saddled` | HA control-plane daemon composing store, wire, API, bridge, and controllers |
| `saddle-federation` | Signed offline/imported snapshots, conflict policy, anti-rollback |
| `saddlectl` | Operator CLI with inspect, diff, apply, watch, drain, revoke, backup, restore, migrate |
| `saddle-conformance` | Machine-readable correctness, bridge, live-system, performance, and upgrade reports |

The new `saddle-bridge` crate centralizes the cross-plane seam; it reuses `fabric-*`, `wsf-*`, and AOG contracts and does not reimplement cryptography.

## 4. Resource model

The stored hub version is `saddle.islandmountain.io/v1`. Every object has `api_version`, `kind`, immutable UID, generation, resource version, tenant/estate scope, spec, status, conditions, finalizers, and receipt/capability references where applicable.

### 4.1 Imported resource kinds

`Tenant`, `TrustRing`, `VirtualKey`, `Capability`, `PolicyBundle`, `ProviderPool`, `Workload`, `Placement`, `Node`, `MissionContract`, `ToolGrant`, `RolloutPlan`, and `RevocationIntent` migrate from the seed estate model.

### 4.2 Required professional scheduler resources

- `ResourceQuota`: tenant hard ceilings and optional guaranteed minima for CPU, memory, GPU/NPU, accelerator memory, replicas, spend, and tool/model actions;
- `PriorityClass`: bounded priority and preemption policy, with protected system classes issued only by estate authority;
- `PlacementGroup`: all-or-nothing gang placement for tensor/pipeline/distributed inference and tightly coupled agents;
- `DisruptionBudget`: minimum available / maximum unavailable for rollout, drain, and maintenance;
- `RuntimeClass`: approved process, containerd, or Wasmtime driver and its attestation requirements; and
- `NodeLease`: bounded liveness/renewal state separate from durable node specification.

Unknown kinds, versions, fields at security-sensitive boundaries, and invalid conversions fail closed. Conversion is round-trip tested and cannot widen authority.

## 5. Cross-plane bridge contract

### 5.1 Non-forgeable boundary types

`saddle-bridge` owns non-deserializable types produced only after verification:

- `VerifiedSaddleRequest`: `VerifiedRequestContext` plus verified token lineage, current revocation epoch/freshness, nonce, and correlation ID;
- `AdmissionGrant`: exact verb, canonical object UID/name/tenant, allowed mutation digest, expiry, and capability scope;
- `PlacementGrant`: workload UID/generation, eligible node set or exact node, resource reservation, trust constraints, and expiry;
- `RuntimeGrant`: placement UID, node identity, workload digest, runtime class, AOG permissions, budget, and revocation lineage; and
- `ActionGrant`: one model/tool/control action, immutable argument/request digest, destination, budget reservation, nonce, expiry, and receipt intent.

None implement `Deserialize`, `Default`, or public field construction. Wire payloads are untrusted inputs; only verified server code can establish these types.

### 5.2 Mutation path

1. Saddle authenticates the caller from mTLS/workload identity and a signed WSF capability.
2. It verifies signature, audience, issuer/trust bundle, expiry, nonce/replay, tenant, caveats, budget, and current monotonic revocation.
3. Server routing and lookup resolve the final canonical resource.
4. `VerifiedRequestContext` binds principal, exact operation, and resolved resource.
5. Saddle policy evaluates deny-wins; mutation/defaulting may only narrow authority.
6. A durable audit intent records before/after digests and the authorizing lineage.
7. The linearizable store commits with CAS preconditions.
8. The WSF receipt is finalized and linked to the committed revision before success is returned for a high-consequence mutation.

There is no production `system` shortcut. Controllers authenticate as distinct WSF workload identities with exact estate/tenant capabilities. Any seed `admit_system` seam is removed from production or replaced by a non-forgeable, revocation-aware controller grant.

### 5.3 Scheduling and runtime path

1. A `Workload` generation becomes queueable only after admitted desired state exists.
2. The scheduler reads a coherent snapshot, applies hard WSF/Saddle filters, scores only surviving nodes, and records all signal provenance.
3. Reserve performs an atomic CAS against current allocatable resources and quota; no token or credential is minted on an uncommitted reservation.
4. Permit handles gang readiness, approval, or bounded wait without holding leaked resources indefinitely.
5. Bind creates exactly one `Placement` for the workload replica/generation using UID/resource-version preconditions.
6. After binding, WSF attenuates a `RuntimeGrant` to the exact placement, node identity, workload digest, AOG actions, budget, and TTL.
7. The node independently verifies assignment, grant, revocation, digest, runtime class, and local trust posture before start.
8. Every AOG model/tool action reauthorizes through an `ActionGrant`; no standing provider/tool credential is present on the workload.
9. Abort, timeout, preemption, deletion, or drift releases reservations and revokes grants idempotently.

### 5.4 Revocation path

`RevocationIntent` is admitted and durably receipted, indexed into the live control-plane view, signed into monotonic WSF snapshots, and fanned to gateways, tool proxies, nodes, and offline caches. A stale or rolled-back snapshot cannot restore authority. Connected replicas deny within the revocation SLO; offline nodes deny at the next action after receiving a valid newer snapshot and fail static-restrictive when freshness expires.

## 6. Scheduler contract

### 6.1 Scheduling cycle

The framework exposes ordered extension points with immutable per-cycle state:

1. `QueueSort`
2. `PreFilter`
3. `Filter`
4. `PostFilter`
5. `PreScore`
6. `Score` + normalization
7. `Reserve` / `Unreserve`
8. `Permit`
9. `PreBind`
10. `Bind`
11. `PostBind`

Hard filters are deny-wins. A scorer cannot resurrect an ineligible node. Every plugin declares deterministic inputs, timeout, failure posture, and reason codes. Plugin panics/timeouts become failed or pending scheduling, never a permissive result.

### 6.2 Required hard filters

- node readiness and unexpired lease;
- cordon/drain and runtime-class support;
- exact tenant/estate eligibility;
- trust-ring match;
- `workload.classification_ceiling <= node.attestation_floor`;
- fresh verified node attestation and workload-measurement compatibility;
- air-gap/connectivity and destination policy;
- CPU, memory, ephemeral storage, GPU/NPU, accelerator memory, and declared extended resources;
- node selector, taints/tolerations, required affinity/anti-affinity, and topology constraints;
- provider/model availability for workloads that require them;
- `ResourceQuota`, budget, and placement-group feasibility; and
- disruption/preemption constraints.

Missing metrics, capacity, heartbeat, attestation, policy, or revocation state is ineligible. Absence is never treated as healthy or capacious.

### 6.3 Required scoring and selection

- least allocated / balanced resource utilization;
- topology and accelerator-interconnect quality;
- data/model-cache locality without bypassing classification rules;
- topology spread and HA anti-concentration;
- consolidation/power efficiency as an explicit posture, never accidentally combined with opposing spread weights;
- budget/ROI efficiency based on authoritative metering; and
- deterministic stable tie-breaking derived from workload UID/generation, not wall-clock randomness.

The decision receipt records snapshot revision, plugin versions, filter reasons, score breakdown, chosen node, reservation ID, and tie-break input without leaking sensitive workload content.

### 6.4 Queueing, fairness, and preemption

- active, backoff, unschedulable, and permit-wait queues have bounded memory and explicit wake-up triggers;
- weighted dominant-resource fairness applies across tenants, honoring guaranteed minima and hard maxima;
- priority cannot be self-asserted by a tenant;
- starvation age is observable and bounded by policy when a feasible placement exists;
- preemption is a last resort, considers only already-eligible nodes, respects disruption budgets, and never crosses trust/tenant boundaries to manufacture fit;
- victim selection is deterministic, minimizes disruption and wasted work, and is fully receipted; and
- gang scheduling reserves all members or none, with bounded permit expiry and complete rollback.

### 6.5 Concurrency invariants

- two scheduler replicas cannot double-bind one replica/generation;
- concurrent reservations cannot oversubscribe node or tenant quota;
- stale snapshots fail CAS and requeue;
- a lost leader cannot complete a bind after fencing;
- reservation release is idempotent after crash/retry; and
- a placement never becomes runnable without a matching current runtime grant.

## 7. Controller and node contract

- Controllers are level-triggered and converge from current desired/observed state; events are hints, not truth.
- Duplicate, dropped, reordered, and replayed events converge identically.
- Each reconcile is idempotent, bounded, cancellable, and uses exponential backoff with jitter and dead-letter visibility rather than silent drop.
- Informer caches expose revision/freshness; security decisions use linearizable reads or last-known-restrictive state as declared.
- Finalizers prevent destructive deletion until external state and grants are safely withdrawn.
- Rollouts and rollbacks are generation-aware, disruption-budgeted, health/attestation-gated, and reversible to a prior signed state.
- Node drivers share one lifecycle contract: prepare, start, observe, stop, kill, cleanup; cleanup and revocation run after cancellation/panic as well as normal completion.
- Attestation drift evicts and revokes before replacement.
- Node status never fabricates metrics; capacity and health are timestamped observations with source provenance.

## 8. HA, DR, and federation contract

- production control planes use three or five voting members with mutually authenticated transport;
- writes and authority-sensitive reads are linearizable;
- minority partitions and removed members fence;
- membership changes are joint/validated and cannot reduce below safe quorum accidentally;
- snapshots are checksummed, encrypted where sensitive, versioned, and restore-tested;
- committed desired state has RPO 0 under a supported quorum; receipts retain their independent ledger guarantees;
- restore creates a new estate epoch so stale leaders/nodes cannot rejoin as authoritative;
- offline federation artifacts are signed, versioned, monotonic, replay-protected, and conflict-resolved deny-wins for revocation/security policy; and
- no HA/DR/federation path requires cloud egress.

## 9. Conformance profiles

Every report records exact source SHA, build provenance, dependency lock, hardware/OS, topology, profile, start/end time, seed, faults, raw measurements, and artifacts. Simulated components are labeled; simulation cannot prove a live-system bar.

### 9.1 PR functional profile

- 3 control-plane voters;
- 3 node agents;
- 100 desired workload objects across at least two tenants;
- real OpenBao plus the approved cloud emulator where credential paths are exercised; and
- all correctness/security bars at modest scale, excluding explicitly scheduled soak/scale duration.

### 9.2 Release conformance profile

- 5 control-plane voters;
- at least 10 live node agents;
- 1,000 workload objects across at least 10 tenants;
- at least 100 simultaneously running process/container workloads, including AOG gateway and toolproxy;
- live OpenBao, real mTLS identities, real receipt verification, and real network partitions; and
- rolling upgrade, backup/restore, drain, revocation, chaos, and bridge paths.

### 9.3 Scale qualification profile

- 5 control-plane voters;
- 100 node agents;
- 10,000 desired workload objects across at least 50 tenants;
- at least 1,000 active lightweight process workloads and 100 container-driver workloads;
- mixed accelerator/attestation/topology/resource fixtures with traceable observations;
- 24-hour soak after warm-up; and
- at least 100 injected leader, node, network, driver, and storage-pressure fault cycles.

Object-scale simulators may supplement live nodes but cannot replace the live counts above for lifecycle, identity, credential, network, or revocation claims.

## 10. Required conformance bars

| ID | Bar | Required evidence |
|---|---|---|
| SC-01 | API/schema correctness | Validation, defaulting, unknown-field posture, version conversion, round-trip/fuzz |
| SC-02 | Linearizable desired state | Concurrent client history with no lost acknowledged write |
| SC-03 | Watch/cache correctness | Ordered revisions, compaction recovery, reconnect/resync, bounded staleness |
| SC-04 | Reconcile convergence | Duplicate/drop/reorder/replay/fault histories converge identically |
| SC-05 | Hard placement safety | Trust, attestation, tenant, connectivity, runtime, capacity filters never bypassed |
| SC-06 | Atomic reservation/bind | No double bind, oversubscription, quota race, or leaked reservation |
| SC-07 | Multi-tenant fairness | Weighted DRF, quota, priority, starvation, deterministic preemption evidence |
| SC-08 | Gang/topology scheduling | All-or-nothing placement, rollback, accelerator topology and spread correctness |
| SC-09 | Split-brain fencing | Minority and removed members serve no authoritative allow/write/bind |
| SC-10 | Self-healing | Node/workload/controller death recovers within SLO without authority widening |
| SC-11 | Rollout/rollback | Deterministic progress, disruption budget, health/attestation gate, signed rollback |
| SC-12 | WSF admission bridge | Identity, canonical resource, caveat, budget, revocation, audit-before-success live path |
| SC-13 | AOG action bridge | Gateway/toolproxy/approval actions require exact current grants and receipts |
| SC-14 | Kill switch under scale | Revocation halts the next prohibited action across replicas/partitions/offline paths |
| SC-15 | Node/driver custody | mTLS identity, assignment/grant verification, drift eviction+revocation, cleanup |
| SC-16 | HA/DR/federation | Quorum loss, encrypted backup, restore epoch, signed offline exchange, anti-rollback |
| SC-17 | Performance/scale | Release and scale profiles meet declared SLOs with raw percentiles |
| SC-18 | Chaos/soak/resource safety | 24-hour scale soak; no deadlock, leak, lost intent, orphan grant, or unbounded growth |
| SC-19 | Upgrade/version skew | N-1 rolling control plane/node upgrade and rollback without downtime or authority loss |
| SC-20 | Independent secure release | Fresh checkout, no parent source, reproducible build, SBOM/signatures, zero secrets |

The existing eight-bar conformance suite is preserved as characterization evidence, then expanded to SC-01 through SC-20. A report is release-green only when every required bar passes and none is pending.

## 11. Initial service-level objectives

These are measured on the declared release/scale reference profile and may be tightened after baseline. A waiver requires an approved plan addendum and may not waive correctness.

| SLO | Target |
|---|---:|
| Healthy-leader write API latency at release load | p99 ≤ 250 ms |
| Linearizable read latency at release load | p99 ≤ 100 ms |
| Pure scheduler decision, 100 eligible nodes | p99 ≤ 50 ms |
| Queue-to-durable bind at release load | p99 ≤ 1 s for immediately feasible work |
| 1,000-object burst convergence | ≤ 30 s |
| 10,000-object cold convergence | ≤ 5 min |
| Healthy leader loss to new writable leader | p99 ≤ 10 s |
| Connected revocation publication to denial | p99 ≤ 3 s and next prohibited action denied |
| Unexpected node loss to replacement ready | p99 ≤ 30 s for available capacity/image |
| Watch update lag under steady release load | p99 ≤ 2 s |
| Watch reconnect/full resync at 10,000 objects | ≤ 60 s |
| Backup/restore RPO | 0 committed desired-state writes |
| Backup/restore RTO at 10,000 objects | ≤ 15 min |
| 24-hour soak resource behavior | no monotonic FD/task/store leak; post-warm-up quiescent RSS growth ≤ 10% |

If the reference hardware cannot meet a performance SLO, evidence must distinguish algorithmic/product failure from an explicitly published minimum-hardware requirement. Security and consistency bars never become hardware waivers.

## 12. Security and negative evidence

Conformance must actively prove denial of:

- missing, malformed, expired, wrong-audience, replayed, widened, over-budget, or revoked WSF authority;
- caller-supplied principal, tenant, role, canonical resource, node identity, placement, approval actor, or receipt status;
- tenant-to-estate privilege escalation and cross-tenant reads/mutations;
- stale leader writes, stale scheduler binds, double reservations, and rolled-back revocation snapshots;
- under-attested placement, score-over-filter resurrection, and preemption onto an ineligible node;
- unreceipted high-consequence mutation/action and audit-failure success;
- direct provider/tool credential use, credential persistence past action TTL, and cancellation cleanup loss;
- malicious redirects, metadata endpoints, DNS rebinding, oversized/unbounded bodies/streams, and secret-bearing errors;
- unsigned policy/bundle/federation/backup artifacts; and
- source-import secrets, external path dependencies, untracked runtime state, and parent-repository build coupling.

## 13. Completion proof

The architecture target is achieved only when current source and live reports prove every component, invariant, profile, conformance bar, SLO, negative case, and independent-release condition above. Passing the seed's existing modest eight-bar suite is necessary characterization evidence but is not sufficient proof of this contract.
