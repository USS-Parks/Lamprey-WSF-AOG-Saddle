# Lamprey WSF/AOG Saddle — Claude Code Instructions

> **2026-07-16 superseding direction:** Saddle is the replacement name for Loom and is the Priority-1 Kubernetes-level independent scheduler/orchestrator. This repository owns the complete non-secret WSF + AOG + Saddle source. `PLANNING/SADDLE-INDEPENDENCE-DECISION-2026-07-16.md` and `PLANNING/SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md` override any conflicting artifact-only, seat-only, or “Loom parked” text below.

## What this is
Island Mountain's independent WSF + AOG + Saddle major project. Saddle is the Kubernetes-level scheduler/orchestrator that binds WSF authority to AOG workloads and actions. The governed client/seat remains a downstream application in this repository, not the project boundary and not the Priority-1 critical path.

## Hard separation rules (never violate)
1. **Never use an external parent working copy** from a Saddle session. The separate open-source harness stays free, era-locked, and community-maintained on its own timeline.
2. Harness code may be **copied and adapted into Saddle** (same owner, same author) — copy it, own it here. Never submodule, symlink, or import across repos.
3. WSF/AOG and the existing orchestration implementation are imported in full from the approved seed recorded in Saddle's provenance ledger, scrubbed of secrets, and owned here. No release build may depend on a parent checkout, submodule, symlink, or source fetch.
4. Saddle has its **own version timeline**: independent semver, tags `vX.Y.Z`, no inheritance from either parent.

## Governance
- Global CANON (`~/.claude/CANON.md`) applies in full: plan before work (P-SPR → explicit STS approval → execute), exhaustive verify gate before every commit, push only when told, no slop / no build-process artifacts in committed source.
- Commit footer, verbatim, every commit: `Authored and reviewed by Basho Parks, copyright 2026`. Never an AI co-author trailer.
- Layer-3 enforcement (commit-msg hook, no-slop scan, CI) is first-phase scaffold work — until wired, honor the rules manually.

## Retained founding direction (2026-07-11, as superseded 2026-07-16)
1. **Topology: protocol-first, both.** The seat always speaks the WSF/AOG client protocol (trust tokens, gateway, toolproxy, receipts) with Ring-3 offline semantics; deployment chooses a bundled localhost sidecar (single seat) or an org appliance/server (fleet).
2. **Packaging: separate major project, this repo.** Complete separation from the OSS harness, with native WSF/AOG/Saddle source ownership.
3. **Identity: staged.** v1 admin-issued enrollment token → device/seat identity; v1.5 OIDC/SSO against the client org's IdP → per-user tokens + RBAC.
4. **Model routes: both, seamless cloud⇄local flip.** No configured posture — per-request policy + connectivity decide; the route is visible per turn (trust pill, per-turn route chips); an air-gap flip mid-session is non-disruptive.

Enforcement doctrine: **server-side enforcement for everything that crosses a wire** (gateway/toolproxy verify tokens themselves; the seat holds no standing credentials), **client-side enforcement plus tamper-evident receipts for local execution** (shell/file tools) — bypass is detectable rather than impossible, and buyer docs say exactly that.

## Reference map

Saddle-local provenance, architecture, execution, and verification records are
authoritative for this repository. Do not require or inspect an external parent
working copy to build, test, package, or operate Saddle.

## Current state
The independence decision and canonical PSPR are under authorized full STS execution as of 2026-07-17. SAD-00 through SAD-15 established the safe source boundary, removed parent coupling, restored the Rust, console, deployment, and fresh-checkout M1 gates; SAD-20 is next. Saddle orchestration remains ahead of governed-seat bootstrap in priority. Execution truth is recorded in `docs/sessions/SADDLE-DEVLOG.md` and `docs/verification/SADDLE-VERIFICATION.md`.
