# SAD-HIST-03 Non-Main Reconciliation

**Source boundary:** the 12 `review-required` commits frozen by SAD-HIST-01

**Review base:** `0e3bd77656601b46cc03d96765d703c3916dbcd3`

**Machine evidence:**
`test-evidence/saddle/SAD-HIST-03/non-main-reconciliation.json`

## Result

Every non-main, non-patch-equivalent Mighty Eel commit has a current
disposition. Nine are superseded by smaller reviewed source-main changes or
later Saddle work, one belongs only in the sanitized archive, one is excluded
from Saddle's source boundary, and one required a focused Saddle-native
transplant.

No source commit was cherry-picked or merged. No historical object or
`history/mighty-eel/...` ref was imported or published.

| Source commit | Scope | Disposition | Controlling result |
|---|---|---|---|
| `02ae597` | GitHub Actions Node runtime | superseded | Saddle `30a30db` uses the current Node 24 action majors and tests the contract. |
| `9684ab5` | AF-001 early parent-authentication patch | superseded | Source-main T1-T7 and later token hardening are broader; Saddle imported and renamed the reviewed state. |
| `7b65774` | AF-001 combined Phase T patch | superseded | Source-main T1-T7 adds context, expiry, revocation, lineage, versioning, and property gates. |
| `fe8f332` | AF-002 authenticated issuance | superseded | Source-main A1-A5 separates principal, authentication, policy, receipts, and the live gate. |
| `9aea8b6` | AF-003 tenant-bound envelopes | superseded | Source-main E1-E7 adds v2 binding, per-tenant Transit keys, migration, and live proof. |
| `d935079` | AF-004 credential-broker confinement | superseded | Source-main B1-B6 covers tenant grants, least privilege, and all three cloud providers. |
| `83742a6` | AF-007 receipt authorization | superseded | Source-main L1-L4 adds tenant isolation, explicit global auditors, and signed export. |
| `e2ddf27` | AF-006 revocation consumers | superseded | Source-main R1-R6 adds anti-rollback state and fail-closed seal/broker/live coverage. |
| `f30164f` | AF-005 MAI vault readiness | exclusion | The implementation is in excluded MAI appliance crates; only historical records belong in Saddle. |
| `fa956e7` | Partial quality/M1 closeout | superseded | Source main intentionally retains the mock server's container bind and completes the later quality/Phase X truth. |
| `92dc928` | Hardened WSF OpenAPI contract | transplant | Saddle `1caaa4f` adapts the intent to current DTOs and adds a CI contract test. |
| `8f27bbe` | Mighty Eel RC1.2 bundle docs | archive | Release-specific binaries, hashes, and tester instructions are historical MAI/Lamprey evidence, not Saddle behavior. |

The full ledger records each candidate's exact source object digest, normalized
patch digest, changed paths, published refs, source-main and Saddle controlling
commits, current evidence-file hashes, anchors, rationale, and verification
commands.

## The one transplant

Source commit `92dc928febb49837b71755ccb75a8eeccbe14b2b`
identified real documentation drift: current Saddle enforced authenticated
issuance, authenticated and monotonic attenuation, tenant-scoped named cloud
grants, and tenant-scoped receipts, while `openapi.json` still described the
older public contract.

The source patch could not be copied verbatim. Its receipt parameters had
drifted to `token_id` and `limit`, while Saddle's current DTO still uses the
generic `field` and `value` pair. The Saddle-native change therefore preserves
the current DTO and documents the actual authority rules and error classes.
`tools/ci_surface_tests/test_wsf_openapi.py` locks those statements to the
active document.

Focused implementation commit:
`1caaa4f8d160bece69aaf0416d57d573e73b2a1d`.

## Reproduction

Run against a local clone of the published Mighty Eel source repository:

```powershell
python tools/reconcile_saddle_history_non_main.py `
  --root . `
  --source-repo C:\path\to\Mighty-Eel-OS `
  --verify
```

The command fails if the SAD-HIST-01 review queue changes, a candidate object
or changed-path set drifts, a cited source-main or Saddle commit is not in the
claimed ancestry, an evidence anchor disappears, or the rendered JSON differs
from the committed evidence.

Focused verification:

```powershell
python tools/ci_surface_tests/test_history_reconciliation.py
python -m unittest tools.ci_surface_tests.test_wsf_openapi -v
cargo test -p fabric-token
cargo test -p fabric-contracts
cargo test -p fabric-revocation
cargo test -p wsf-broker --lib
cargo test -p wsf-seal --lib
cargo test -p wsf-api --test auth_gate --test issuance_perms `
  --test ledger_authz
cargo test -p saddle-apiserver --test seal
cargo test -p saddle-bridge --test contract_properties
```

Live OpenBao tests remain part of the existing trust-plane acceptance surface.
SAD-HIST-03 does not recast an absent live backend as a pass and does not reopen
the already recorded hardware-only AF-005 deferral.

## Next boundary

SAD-HIST-04 remains the only prompt authorized to create or publish the
sanitized `history/mighty-eel/...` refs. It must use the SAD-HIST-02 object map,
incorporate current `main`, and prove the active release dependency graph is
unchanged except for this reviewed OpenAPI transplant and provenance tooling.
