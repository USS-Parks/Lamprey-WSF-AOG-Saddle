# Saddle Independence Decision — 2026-07-16

**Decision owner:** Basho Parks
**Repository:** `USS-Parks/Lamprey-WSF-AOG-Saddle`
**Status:** Locked; supersedes the conflicting parts of the 2026-07-11 founding direction.

## Decision

1. **Saddle replaces Loom, period.** The Kubernetes-level independent scheduler and orchestrator is named Saddle. Active source, packages, binaries, protocols, trust domains, resource identifiers, deployment assets, telemetry, UI, and documentation must not use Loom as the current name.
2. **The Saddle scheduler/orchestrator is Priority 1.** The governed seat remains in project scope, but it cannot displace the independent orchestration engine, conformance work, or WSF↔AOG bridge from the critical path.
3. **Saddle is a separate major project.** It has its own repository, version line, release pipeline, roadmap, threat model, conformance program, and operator lifecycle.
4. **Saddle must bridge WSF and AOG.** WSF supplies identity, capabilities, revocation, envelopes, ephemeral credentials, and receipts. AOG supplies agentic gateway, policy, tool, approval, budget, and metering controls. Saddle admits, schedules, reconciles, and runs AOG workloads under current WSF authority.
5. **Complete non-secret WSF and AOG source belongs here.** The repository must contain the full source and test surface—not only SDKs or signed binaries—plus every internal dependency required to build and verify it independently.
6. **No external-source crutch.** No submodule, symlink, path dependency, or build-time source fetch from Mighty Eel OS or Lamprey Harness may be required for a release build.
7. **No secrets.** Imports are created from tracked allowlisted paths at a pinned commit. Private keys, live credentials, local state, `.env` files, build output, and generated test material are excluded and blocked by scans and CI.

## Superseded 2026-07-11 decisions

The following earlier statements no longer govern:

- WSF/AOG are consumed only as signed release artifacts;
- WSF/AOG source is never vendored or imported;
- the project is seat-only; and
- Loom is parked for a later version.

The following remain in force:

- Lamprey Harness stays an independent open-source project;
- Saddle has independent semantic versioning;
- the client is protocol-first and supports bundled-local and organization-server deployments;
- identity evolves from enrollment to organization OIDC/SSO; and
- cloud/local routing remains policy-driven and seamless.

## Architecture invariant

An AOG action or workload is authoritative only when:

1. the caller and resource are authenticated under WSF;
2. current WSF scope, budget, caveats, revocation, and tenant boundaries authorize it;
3. Saddle admission accepts it and Saddle scheduling places it only on an eligible attested target;
4. AOG policy and tool/model controls allow it; and
5. the required durable receipt is committed before any high-consequence side effect.

Failure or uncertainty at any step is deny/fence, never an ungoverned fallback.

## Naming rule

“Loom” may appear only in immutable historical documents, imported commit provenance, and narrowly scoped migration fixtures that prove legacy-state conversion. New code emits only Saddle identities. The release gate scans active paths for prohibited Loom identity residues.

## Execution authority

This decision authorizes the plan to be drafted. It does not authorize STS execution, commits, pushes, releases, deployments, secret rotation, or changes to another repository. Those actions follow the canonical PSPR and workspace Git rules.
