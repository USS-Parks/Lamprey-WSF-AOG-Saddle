# Lamprey WSF/AOG Saddle — Agent Instructions

## Canonical authority

- Decision: `PLANNING/SADDLE-INDEPENDENCE-DECISION-2026-07-16.md`
- Plan: `PLANNING/SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`
- Source and rename manifest: `PLANNING/SADDLE-SOURCE-AND-RENAME-MANIFEST.md`
- Architecture and conformance contract: `PLANNING/SADDLE-ARCHITECTURE-AND-CONFORMANCE-CONTRACT.md`
- Current-state gap matrix: `PLANNING/SADDLE-CURRENT-STATE-GAP-MATRIX.md`
- Seed reconciliation: `PLANNING/SADDLE-SEED-RECONCILIATION-2026-07-16.md`
- Execution log once started: `docs/sessions/SADDLE-DEVLOG.md`

The plan is drafted, not authorized. Execute only after the user says `run it STS` or approves named prompts.

## Priority and identity

Saddle is the replacement name for Loom, period. Saddle is the Priority-1 Kubernetes-level independent scheduler/orchestrator bridging WSF and AOG. The governed seat is downstream and may not displace open orchestration or conformance gates.

“Loom” is allowed only in immutable historical provenance or explicit legacy-migration fixtures. Active code, packages, protocols, deployments, telemetry, UI, and docs use Saddle.

## Source independence

This repository must own the complete non-secret WSF + AOG + Saddle source and its internal build dependency closure. Do not add submodules, symlinks, external local path dependencies, or build-time source coupling to Mighty Eel OS or Lamprey Harness.

Imports must come from tracked files at a pinned source SHA with a path/hash provenance ledger. Never copy a live working tree wholesale. Never import `.env`, private keys, credentials, local OpenBao state, generated PKI, caches, logs, `target/`, `node_modules/`, or machine-specific material.

## PSPR discipline

- Work in roster order and preserve stable prompt IDs.
- Use an isolated worktree for concurrent sessions.
- Do not mark a prompt complete until its stated gate passes.
- Maintain the DEVLOG with files, verification, evidence, commit SHA, and next prompt.
- Require live evidence for trust, credential, policy, consensus, scheduling, and integration claims.
- Preserve executed history and open findings honestly; do not reset status during import.

## Git

Never commit or push without explicit user authorization. A session instruction such as `commit and push` is durable authorization for all in-scope commits and pushes needed to finish the approved milestone, but not for force-push, history rewrite, deployment, secret rotation, or unrelated changes.

Every commit message must end exactly:

`Authored and reviewed by Basho Parks, copyright 2026`

Never add AI attribution or co-author trailers. Before push, inspect every outgoing commit for the exact footer.
