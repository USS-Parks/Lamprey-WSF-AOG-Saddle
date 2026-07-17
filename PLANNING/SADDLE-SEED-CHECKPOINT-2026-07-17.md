# Saddle Approved Seed Checkpoint

**Prompt:** `SAD-01 — Resolve the authoritative seed checkpoint`

**Decision date:** 2026-07-17

**Status:** PASS — one immutable, published source object is approved for the
tracked, allowlisted Saddle import procedure.

## 1. Approved source object

| Property | Recorded value |
|---|---|
| Seed repository | `https://github.com/USS-Parks/Mighty-Eel-OS.git` |
| Resolved remote ref | `refs/heads/main` |
| Immutable import pin | `fedf005a30ad388ab156dc8bd693a3aa3f0702ea` |
| Commit subject | `docs: close LSH-T6 production tool checkpoint` |
| Parent implementation checkpoint | `5e541e5324269a051d3304e94ae868080d876a25` |
| Signature result | Good SSH signature for `basho.parks@gmail.com`, ED25519 fingerprint `SHA256:PE4Wpbp27IeZC6y4dd97YDNLiFrDvky2KOWSqvdkTEc` |
| Required footer | Exact canonical footer verified on the selected commit |
| Saddle remote checkpoint | `7f30ea691f91b3ea8774b7fd121fbc8580b1d69f` |

The selected object is the current published `origin/main`, not a local branch,
working tree, disposable clone, or partially reconciled history. It contains the
reconciled T5 source checkpoint and the published T6 production-tool checkpoint
and closeout record. All materialization beginning with `SAD-02` and `SAD-03`
must name this exact object.

## 2. Decision boundary

This decision authorizes no direct filesystem copy and no broad repository
mirror. It permits only tracked, path-dispositioned files materialized from the
Git object above after the `SAD-02` coverage ledger and `SAD-03` zero-secret
import gate pass. It does not claim that the seed security roster is complete,
that Saddle has adopted the source, or that a deployable Saddle release exists.

The following are still prohibited at this point:

- importing ignored files, `.git` data, local configuration, generated state,
  caches, logs, OpenBao data, PKI, or private keys;
- accepting a source path merely because it textually mentions WSF, AOG, Loom,
  Saddle, or a fabric crate; and
- downgrading any unresolved seed finding to documentation-only status.

## 3. Carried-forward source hardening obligations

The following source prompts remain open at the selected seed pin. They are
carried forward as non-downgrade obligations: the listed Saddle prompts must
preserve the original acceptance condition and record a source-backed closure
or a stricter Saddle replacement before any corresponding final claim.

| Open seed prompt | Original focus | Saddle owner prompts | Required carry-forward condition |
|---|---|---|---|
| `LSH-D1` | Ring-3 snapshot reachability, endpoint consumers, tenant classification, sealed placeholders (`LSD-001`–`LSD-004`) | `SAD-30`, `SAD-31`, `SAD-35`, `SAD-54` | Trace every reachable WSF path and prove fail-closed activation seams where a caller is absent. |
| `LSH-D2` | Envelope-label routing and truthful downstream stream completion (`LSD-005/006`) | `SAD-33`, `SAD-34`, `SAD-35`, `SAD-54` | Preserve verified label context and truthful termination through real AOG workload paths. |
| `LSH-D3` | Controller grant aggregation, mission grants, counters, restart anti-rollback (`LSD-007/008`) | `SAD-30`, `SAD-42`, `SAD-44`, `SAD-54` | Re-run reachability after bridge/controller changes and close every runtime instance. |
| `LSH-D4` | Tool target binding, cancellation-safe credentials, output framing, scanner bounds (`LSD-009/010`) | `SAD-33`, `SAD-34`, `SAD-35`, `SAD-54` | Revalidate the T6 path under Saddle grants, controller/node lifecycle, and live authority. |
| `LSH-D5` | Remaining selected-file receipts and instance expansion | `SAD-02`, `SAD-49`, `SAD-54` | Reconcile all selected source paths, root-cause families, and newly discovered instances without unowned gaps. |
| `LSH-X1` | Full software gate ladder | `SAD-13`, `SAD-14`, `SAD-50`, `SAD-56` | Run the complete independent-repository build, lint, test, integrity, dependency, and secret gates. |
| `LSH-X2` | Live trust/control/provider suite | `SAD-35`, `SAD-46`, `SAD-49`, `SAD-54` | Use production-equivalent OpenBao, mTLS control plane, AOG gateway/tool, and persistence evidence. |
| `LSH-X3` | Failure injection, restart, and concurrency proof | `SAD-41`–`SAD-48`, `SAD-54` | Exercise revocation, authority, storage, consensus, provider, cancellation, and scheduling failures. |
| `LSH-X4` | Independent WSF/AOG security re-scan | `SAD-54` | Require zero open Critical/High findings and explain every remaining coverage boundary. |
| `LSH-X5` | Documentation and status reconciliation | `SAD-11`, `SAD-55`, `SAD-56` | Map every Saddle claim to current code, regression, live evidence, and ownership. |
| `LSH-X6` | Final go/no-go and handoff | `SAD-56` | Produce the final closure report, residual-risk register, rollback notes, exact revision, and release recommendation. |

`LSH-T6` is not in this table because its production caller, approval,
credential authority, executor, revocation, and receipt gate passed at
`5e541e5324269a051d3304e94ae868080d876a25`. Its live invariants remain
mandatory characterization and bridge evidence for `SAD-33` through `SAD-35`.

## 4. SAD-01 acceptance evidence

1. Live seed remote lookup resolved `refs/heads/main` to
   `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`.
2. The selected object is a Git `commit`, has a good SSH signature, and ends
   with `Authored and reviewed by Basho Parks, copyright 2026`.
3. The checkpoint is published and includes the exact T6 implementation
   checkpoint and DEVLOG closure rather than a local-only T5 branch.
4. Every remaining seed hardening prompt (`LSH-D1` through `LSH-D5` and
   `LSH-X1` through `LSH-X6`) has an explicit Saddle ownership path above.
5. No WSF, AOG, scheduler, deployment, credential, or runtime-state source was
   imported while resolving this checkpoint.

## 5. Next sequential gate

`SAD-02` must generate the full source-coverage manifest from the approved Git
object. It must calculate the Cargo dependency closure, identify every relevant
tracked source-like path, record hashes and dispositions, and explicitly review
the `mai-scheduler` reuse candidates before any path enters this repository.
