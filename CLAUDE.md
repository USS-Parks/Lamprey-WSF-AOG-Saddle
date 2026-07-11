# Lamprey WSF/AOG Saddle — Claude Code Instructions

## What this is
The client/org-facing agentic harness for Island Mountain: a governed seat over the WSF trust plane + AOG control plane, delivered to contracted organizations. Working name "Saddle" (rename possible before first client delivery). This is NOT the open-source Lamprey Harness — see the separation rules below before doing anything.

## Hard separation rules (never violate)
1. **Never touch the open-source Lamprey Harness repo** (`USS-Parks/lamprey`, local working copy `C:\Users\17076\Documents\Claude\Lamprey Harness`) from a Saddle session. It stays free, era-locked, and community-maintained on its own timeline.
2. Harness code may be **copied and adapted into Saddle** (same owner, same author) — copy it, own it here. Never submodule, symlink, or import across repos.
3. WSF/AOG services come from `USS-Parks/im-mighty-eel-mai` as **signed release artifacts** (cosign, that repo's supply-chain pipeline), version-pinned. Never vendor that source either.
4. Saddle has its **own version timeline**: independent semver, tags `vX.Y.Z`, no inheritance from either parent.

## Governance
- Global CANON (`~/.claude/CANON.md`) applies in full: plan before work (P-SPR → explicit STS approval → execute), exhaustive verify gate before every commit, push only when told, no slop / no build-process artifacts in committed source.
- Commit footer, verbatim, every commit: `Authored and reviewed by Basho Parks, Copyright 2026`. Never an AI co-author trailer.
- Layer-3 enforcement (commit-msg hook, no-slop scan, CI) is first-phase scaffold work — until wired, honor the rules manually.

## Locked direction (2026-07-11 — full record in PLANNING/SADDLE-FOUNDING-DIRECTION.md)
1. **Topology: protocol-first, both.** The seat always speaks the WSF/AOG client protocol (trust tokens, gateway, toolproxy, receipts) with Ring-3 offline semantics; deployment chooses a bundled localhost sidecar (single seat) or an org appliance/server (fleet).
2. **Packaging: separate software, this repo.** Complete separation from the OSS harness (Basho's call, 2026-07-11, revising an earlier same-repo-edition recommendation).
3. **Identity: staged.** v1 admin-issued enrollment token → device/seat identity; v1.5 OIDC/SSO against the client org's IdP → per-user tokens + RBAC.
4. **Model routes: both, seamless cloud⇄local flip.** No configured posture — per-request policy + connectivity decide; the route is visible per turn (trust pill, per-turn route chips); an air-gap flip mid-session is non-disruptive.

Enforcement doctrine: **server-side enforcement for everything that crosses a wire** (gateway/toolproxy verify tokens themselves; the seat holds no standing credentials), **client-side enforcement plus tamper-evident receipts for local execution** (shell/file tools) — bypass is detectable rather than impossible, and buyer docs say exactly that.

## Reference map (external working copies, read-only from Saddle sessions)
| What | Where |
|---|---|
| OSS harness architecture index | `C:\Users\17076\Documents\Claude\Lamprey Harness\CLAUDE.md` (v0.16.0) |
| WSF/AOG working copy | `C:\Users\17076\Documents\Claude\Mighty Eel OS\mai\` |
| WSF/AOG build plan (P-SPR) | `C:\Users\17076\Documents\Claude\Mighty Eel OS\PLANNING\AOG-WSF-SOVEREIGNTY-STACK-PSPR.md` |
| WSF/AOG build log | `C:\Users\17076\Documents\Claude\Mighty Eel OS\mai\docs\sessions\SOVEREIGNTY-DEVLOG.md` |
| Canonical threat model | `C:\Users\17076\Documents\Claude\Mighty Eel OS\mai\docs\architecture\AGENTIC-SECURITY-MAP.md` |

## Current state
Founding docs only (this file, README.md, PLANNING/SADDLE-FOUNDING-DIRECTION.md). **Next artifact: the Saddle build P-SPR** (a new `PLANNING/*.md` here), drafted on explicit request and executed only after explicit STS approval. First P-SPR decisions to settle: codebase bootstrap (recommended: one-time snapshot copy of the harness tree at v0.16.0 as the initial code drop, then weave), hooks + CI wiring, product naming.
