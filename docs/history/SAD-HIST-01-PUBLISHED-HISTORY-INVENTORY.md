# SAD-HIST-01 Published History Inventory

**Source:** `USS-Parks/Mighty-Eel-OS` published heads and tags

**Approved main:** `fedf005a30ad388ab156dc8bd693a3aa3f0702ea`

**Scope:** read-only inventory; no Git objects, refs, or source changes imported

## Result

The remote advertises 38 branch heads and no tags. Their combined object graph
contains 762 commits: 737 are ancestors of the approved main commit and 25 are
reachable only from another published branch. Every commit has an explicit
migration disposition.

| Disposition | Commits | Meaning |
|---|---:|---|
| Mainline ancestry | 737 | Preserve as source history after the secret gate permits archive publication. |
| Patch-equivalent | 12 | A mainline commit already carries the same stable patch. Do not duplicate it. |
| Tree-equivalent | 1 | The commit changes no tree content relative to its parent. Preserve provenance only. |
| Review required | 12 | Compare the patch and current Saddle state before deciding whether to transplant, record as superseded, or reject. |

The machine-readable inventory is
`test-evidence/saddle/SAD-HIST-01/history-inventory.json`. It records every
advertised ref, reachable commit, parent, tree, author and committer identity,
date, signature status, subject, changed path, stable patch identity, source
manifest relationship, and migration disposition.

## Commits requiring migration review

| Source commit | Date | Published subject | Branch |
|---|---|---|---|
| `8f27bbea2d04` | 2026-05-24 | RC-10 post-review rebundle | `session/RC-10` |
| `02ae59715558` | 2026-07-05 | Move GitHub Actions to Node.js 24 | `session/node24-github-actions` |
| `9684ab5f237e` | 2026-07-07 | Authenticate the parent before token attenuation | `claude/af-001-signature-verify-irpxey` |
| `7b65774afd6b` | 2026-07-07 | Authenticate and constrain attenuation | `claude/repository-security-audit-2trwtq` |
| `fe8f3321724c` | 2026-07-07 | Authenticate WSF issuance | `claude/repository-security-audit-2trwtq` |
| `9aea8b60b29f` | 2026-07-07 | Bind envelopes to tenants | `claude/repository-security-audit-2trwtq` |
| `d935079723f2` | 2026-07-07 | Confine the credential broker | `claude/repository-security-audit-2trwtq` |
| `83742a6e4c29` | 2026-07-07 | Authorize the receipt ledger | `claude/repository-security-audit-2trwtq` |
| `e2ddf278f579` | 2026-07-07 | Consume revocation on WSF paths | `claude/repository-security-audit-2trwtq` |
| `f30164f01835` | 2026-07-07 | Establish production-vault truth | `claude/repository-security-audit-2trwtq` |
| `fa956e788539` | 2026-07-07 | Partial security closure and M1 report | `claude/repository-security-audit-2trwtq` |
| `92dc928febb4` | 2026-07-07 | Reconcile the WSF OpenAPI contract | `claude/repository-security-audit-2trwtq` |

This list is a review queue, not proof that Saddle lacks the behavior. SAD-HIST-03
must compare each patch with the then-current Saddle implementation and tests.

## Humanization and history policy

Published source commits are immutable evidence. Their subjects, authorship,
signatures, and dates will not be rewritten to improve style. Archive refs, if
approved after SAD-HIST-02, will point to those exact objects.

Any patch selected for Saddle in SAD-HIST-03 will receive a fresh, focused
commit after a human review of the code and prose. That review must remove
prompt residue, mechanical narration, obsolete step language, copied model
attribution, and unsupported completion claims. The new commit must use the
canonical Basho Parks footer and pass the staged and full no-slop gates. A bulk
transplant commit is not permitted.

## Integrity observations

- 228 of 762 source commits already end with the current canonical footer.
- Signature state is derived from each immutable commit object rather than the
  machine's trust store. The evidence records presence, format, and a SHA-256
  digest of the stored signature block: 228 SSH-signed, 7 OpenPGP-signed, and
  527 unsigned commits. Trust validation remains a separate security
  disposition.
- The remote currently publishes no tags. Local-only refs are deliberately
  excluded because they are not part of the GitHub timeline.
- The approved main SHA matches the SAD-02 source manifest and the live
  `refs/heads/main` advertisement.

SAD-HIST-02 remains the next history-lane prompt. No archive ref may be pushed
until its full reachable closure passes the secret scan and receives an honest
disposition.
