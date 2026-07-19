# Saddle Published-History Reconciliation Addendum

**Initiative:** Preserve and reconcile WSF, AOG, and Saddle work that was
published in `USS-Parks/Mighty-Eel-OS` without rewriting Saddle's independent
`main` timeline.
**Authority:** Supporting addendum to
`SADDLE-WSF-AOG-INDEPENDENT-PROJECT-PSPR.md`.
**Target repository:** `USS-Parks/Lamprey-WSF-AOG-Saddle`.
**Source repository:** `USS-Parks/Mighty-Eel-OS`.
**Original parallel-lane base:** verified Saddle checkpoint
`c436abe6b930c57bc0170c3c13793276f08490d5`.
**Reconciled integration base:** SAD-40 closeout checkpoint
`b789b68ed8e2b9eed1fe75ec1c6532c1961a24ac`.
**Parallel branch:** `session/SAD-HIST-1`.
**Current status:** **SAD-HIST-01 THROUGH SAD-HIST-04 COMPLETE.**

## 1. Governance and boundaries

This lane runs independently from SAD-40. It must not use, modify, clean,
stage, or commit the SAD-40 worktree or index. It must incorporate the latest
verified `main` before final integration and defer the canonical PSPR status
line and `docs/sessions/SADDLE-DEVLOG.md` append until that reconciliation.

The lane preserves two truthful timelines:

1. original published commits retain their object IDs, authors, dates, parents,
   and merge topology under a protected archival namespace when they pass the
   historical secret gate; and
2. new Saddle review, adaptation, verification, and acceptance commits retain
   their real current committer dates and explicitly cite their source objects.

The following are prohibited throughout this lane:

- force-push, rebase of published history, backdating, grafts, or replacement
  refs;
- merging the unrelated Mighty Eel graph into Saddle `main`;
- copying a live source working tree, importing hidden or ignored state, or
  introducing a parent checkout, submodule, symlink, or path dependency;
- pushing any historical object before the full-history secret gate passes;
- treating patch equivalence as proof that a security or behavior obligation
  is closed; and
- silently omitting a published ref or non-main commit.

## 2. Verification gates

A history prompt is complete only when its deterministic evidence regenerates
byte-for-byte from the exact published ref set and every changed file passes
the repository integrity, active-name, no-slop, secret, and applicable test
gates. Every new commit must carry the canonical Basho Parks footer.

Historical source commits remain immutable. Any later transplant is a new,
focused Saddle commit after human review. Bulk transplant commits, copied model
attribution, prompt residue, mechanical narration, and unsupported completion
claims are not accepted.

Archive publication additionally requires:

- two independent full-history secret scanners across every candidate object;
- exact source-ref, object-count, reachability, signature, and old-to-new SHA
  checks;
- protected, non-main archival refs with an immutable provenance ledger; and
- proof that Saddle's active tree and release dependency graph are unchanged.

## 3. Sequential prompt roster

- [x] **SAD-HIST-01 — Inventory published history.** Freeze every published
  source head and tag; inventory every reachable commit, parent, author and
  committer date, signature state, canonical-footer state, changed path,
  seed-manifest relationship, ref reachability, and stable patch equivalence.
  **Gate:** every advertised ref and reachable commit is accounted for; every
  commit not reachable from source `main` is classified as patch-equivalent,
  tree-equivalent, or review-required; regeneration is byte-for-byte
  deterministic; no history is imported or pushed.

- [x] **SAD-HIST-02 — Prove archive safety.** Run two independent secret
  scanners across all candidate commits and deleted blobs; define exact clean
  archive refs or a transparent sanitized rewrite with a complete old-to-new
  object map.
  **Gate:** no secret-bearing object can enter Saddle; every rewrite is
  explained and reproducible; original SHAs remain cited as external
  provenance. **Result:** a sanitized rewrite is required for one blob and one
  commit message; the complete object/ref maps and two-scanner proof reproduce
  locally. All 14 applicable checks passed on review checkpoint
  `509abbed7d47ed1f81bbb9876937ade7422d3873`; the pull-request-only nightly
  integration matrix was correctly skipped.

- [x] **SAD-HIST-03 — Reconcile non-main work.** Review every non-main,
  non-patch-equivalent commit for WSF/AOG/Saddle behavior, security findings,
  tests, documentation, and superseding Saddle implementation. Transplant only
  still-required behavior through focused Saddle-native commits that cite the
  source SHA.
  **Gate:** every commit has an honest reuse, superseded, transplant, archive,
  or exclusion disposition with code and test evidence where applicable.
  **Implementation result:** all 12 review-required commits are dispositioned:
  nine superseded, one archive-only, one excluded from the Saddle source
  boundary, and one adapted transplant. The transplant is the hardened WSF
  OpenAPI contract in Saddle commit
  `1caaa4f8d160bece69aaf0416d57d573e73b2a1d`; the deterministic ledger is
  `test-evidence/saddle/SAD-HIST-03/non-main-reconciliation.json`. No source
  object or archive ref was imported. All 15 applicable GitHub checks passed on
  reviewed checkpoint `56bf5596adc84b2db109dad35830b13a2dc0034d`;
  the pull-request-only nightly and release publication jobs were correctly
  skipped.

- [x] **SAD-HIST-04 — Publish and close history.** Push verified historical
  objects only under protected `history/mighty-eel/...` refs, publish the final
  provenance ledger, incorporate current `main`, run the complete applicable
  gate stack, and merge the reviewed lane without squashing.
  **Gate:** archival refs reproduce the approved object graph, active Saddle
  source is unchanged except for reviewed transplants and provenance tooling,
  every applicable GitHub workflow is green, and the canonical PSPR and DEVLOG
  truthfully record the closeout.
  **Result:** all 38 approved sanitized refs are published beneath protected
  `history/mighty-eel/...` namespace ruleset `19173522`. The reviewed
  implementation head `85b5c0925136ce7ea9865f197e1295db42ed07ca` passed the complete
  applicable GitHub workflow stack in pull request 4 and merged without
  squashing as `2937f6494561fc607519de6c17c259bc7c684e51`. The unrelated archive
  graph remains outside active Saddle ancestry, and SAD-41 remains the next
  canonical implementation prompt.

## 4. Authorization history

The user authorized STS execution of SAD-HIST-01. That authorization covers the
isolated inventory implementation, evidence, focused commit, branch push, and
green review checkpoint. SAD-HIST-01 does not authorize archive-ref publication,
history rewriting, code transplantation, or execution of SAD-HIST-02 through
SAD-HIST-04.

The user authorized STS execution of SAD-HIST-02 on 2026-07-18 from verified
Saddle checkpoint `f66134ef4b3b36c1506f277dbbb9bf61c7d82d7c`. That authorization covers the
isolated two-scanner proof, reproducible sanitized-map definition, focused
branch commits, branch push, and green-workflow closeout. It does not authorize
publication of archive refs, rewriting active Saddle history, source
transplantation, SAD-HIST-03 or SAD-HIST-04, or merge to `main`.

The user authorized SAD-HIST-03 STS for the entirety of the 2026-07-19 session.
That authorization covers the isolated review, the one focused Saddle-native
transplant, deterministic evidence, in-scope commits, branch push, and remote
workflow closeout. It does not authorize archive-ref publication, rewriting or
merging source history, SAD-HIST-04, merge to `main`, deployment, or credential
rotation.

The user authorized SAD-HIST-04 STS for the entirety of the 2026-07-19 session.
That authorization covers exact sanitized archive-ref publication, immutable
namespace protection, deterministic provenance evidence, in-scope commits and
branch pushes, complete applicable GitHub workflow verification, and the
reviewed non-squash merge to `main`. It does not authorize force-push, a merge
of the Mighty Eel source graph into active Saddle history, deployment,
credential rotation, paid services, or unrelated changes.
