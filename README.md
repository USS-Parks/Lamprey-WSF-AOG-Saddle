# Lamprey WSF/AOG Saddle

Saddle is Island Mountain's independent orchestration project: the software saddle that binds the Woven Sovereignty Fabric (WSF) trust plane to Agentic Orchestration Governance (AOG) workloads, gateways, tools, approvals, and operator surfaces.

The former orchestration codename **Loom is retired**. The orchestrator, scheduler, reconciliation runtime, node runtime, and conformance surface are **Saddle**. Historical records may retain “Loom” when describing already-executed work, but active product, package, protocol, deployment, and documentation identities must use Saddle.

## Repository authority

This repository is the independent home of the complete non-secret WSF + AOG + Saddle source stack. It will contain:

- the complete `fabric-*` and `wsf-*` trust-plane source;
- the complete AOG gateway, toolproxy, approvals, policy, metering, and integration source;
- the orchestration path formerly called Loom, renamed and owned as Saddle;
- every internal source dependency required to build and test those components without an external path, submodule, or source dependency;
- the governed client/seat and operator surfaces built over the same contracts; and
- tests, contracts, deployment assets, CI, runbooks, and evidence required to substantiate the stack's claims.

No secret, private key, live credential, local state, or generated build artifact may enter this repository.

## Three-plane contract

| Plane | Responsibility |
|---|---|
| **WSF** | Identity, capability tokens, attenuation, envelopes, revocation, ephemeral credentials, and tamper-evident receipts |
| **AOG** | Model gateway, tool governance, approvals, policy decisions, budgets, metering, and agentic execution controls |
| **Saddle** | Desired state, admission, scheduling, reconciliation, node runtime, HA/DR, and federation that weave WSF authority through AOG actions and workloads |

The bridge invariant is simple: **no AOG action or workload becomes authoritative unless Saddle admits it under current WSF authority and produces the required receipt.**

## Lineage and separation

- The initial WSF/AOG/orchestration source is recorded at a pinned, verified seed commit with a file-and-hash provenance ledger. After the cutover gate, this repository becomes authoritative for the imported stack.
- **Lamprey Harness** remains a separate open-source project. Harness source may be copied and adapted into a Saddle client application, but Saddle never becomes a dependency of the community repository and no work flows back automatically.
- Signed release artifacts remain a supported deployment mechanism; they are not a substitute for native source ownership in this repository.

## Status

Direction superseded and locked on 2026-07-16. Full STS execution plus commit and push authorization was granted on 2026-07-17. The canonical build and migration plan is [PLANNING/SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md](PLANNING/SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md), with live execution status in [docs/sessions/SADDLE-DEVLOG.md](docs/sessions/SADDLE-DEVLOG.md) and command-level evidence in [docs/verification/SADDLE-VERIFICATION.md](docs/verification/SADDLE-VERIFICATION.md).

The executable source boundary and rename map are in [PLANNING/SADDLE-SOURCE-AND-RENAME-MANIFEST.md](PLANNING/SADDLE-SOURCE-AND-RENAME-MANIFEST.md). The exact meaning of the Kubernetes-level claim—including the scheduler cycle, WSF↔AOG bridge, live profiles, 20 conformance bars, and initial SLOs—is in [PLANNING/SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md](PLANNING/SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md). The baseline implementation inventory and the honest path from reusable machinery to those acceptance bars are recorded in [PLANNING/SADDLE-CURRENT-STATE-GAP-MATRIX.md](PLANNING/SADDLE-CURRENT-STATE-GAP-MATRIX.md). The published/local seed divergence and the exact safe-pin sequence are resolved in [PLANNING/SADDLE-SEED-RECONCILIATION-2026-07-16.md](PLANNING/SADDLE-SEED-RECONCILIATION-2026-07-16.md).

## Versioning

Independent semantic versioning from day one: tags `vX.Y.Z`, with the first release tag created only after the independent-build, bridge, rename, security, and conformance gates pass.
