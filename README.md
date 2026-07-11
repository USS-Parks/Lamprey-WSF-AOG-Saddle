# Lamprey WSF/AOG Saddle

The software saddle for Island Mountain's AI hardware ([islandmountain.io](https://islandmountain.io)): a client- and organization-facing agentic harness that rides the WSF trust plane and the AOG control plane. Governance is compiled in — there is no ungoverned code path, no settings toggle, no direct-provider fallback. The only deployment choice is where the control plane lives, never whether.

"Saddle" is the working name; the product may be renamed before first client delivery.

## Lineage — two parents, one hard separation rule

| Parent | Where | What Saddle takes |
|---|---|---|
| **Lamprey Harness** (open source) | [USS-Parks/lamprey](https://github.com/USS-Parks/lamprey) | The harness itself: Electron architecture, UX, feature set. Code is copied and adapted **into** this repo; nothing ever flows back. |
| **MAI / WSF / AOG** | [USS-Parks/im-mighty-eel-mai](https://github.com/USS-Parks/im-mighty-eel-mai) | The trust plane (fabric-\*, wsf-\*) and control plane (aog-\*) that Saddle is a client of, consumed as signed release artifacts — never vendored source. |

**Separation doctrine:** Saddle is a separate software product with its own version timeline and naming convention. The open-source Lamprey Harness stays online, free, and maintained for the community that uses it. No Saddle work happens in that repo, and Saddle never becomes a dependency of it.

## Status

Pre-plan. Direction locked 2026-07-11 — see [PLANNING/SADDLE-FOUNDING-DIRECTION.md](PLANNING/SADDLE-FOUNDING-DIRECTION.md). The build P-SPR is the next artifact. No product code exists yet.

## Versioning

Independent semver from day one: tags `vX.Y.Z`, first tag `v0.1.0` at the first shipped scaffold phase. No version inheritance from Lamprey Harness (v0.16.x) or MAI (RC2).
