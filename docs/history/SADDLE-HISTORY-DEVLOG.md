# Saddle History Reconciliation DEVLOG

This ledger belongs to the isolated history lane. It does not modify or infer
the state of the concurrent canonical Saddle execution lane.

## SAD-HIST-01 - Published history inventory

**Status:** complete

**Branch:** `session/SAD-HIST-1`

**Original isolation base:** `c436abe6b930c57bc0170c3c13793276f08490d5`

**Reconciled SAD-40 base:** `b789b68ed8e2b9eed1fe75ec1c6532c1961a24ac`

### Scope

- freeze the history-reconciliation boundary;
- inventory every published Mighty Eel branch and tag without importing refs;
- classify every reachable commit for later archive or migration review; and
- make human review mandatory before any source transplant.

### Evidence

- `test-evidence/saddle/SAD-HIST-01/history-inventory.json`
- `docs/history/SAD-HIST-01-PUBLISHED-HISTORY-INVENTORY.md`

### Publication

No source-history ref was created or pushed. The inventory was published on the
isolated branch through two additive commits; the failed first workflow was
corrected without rewriting either commit:

- implementation: `4dfe0ad93466c61428f6d81e1a4f43478cadff75`;
- independence-evidence correction: `94fad21586ff40e1219195db070e23f217a352aa`;
- draft review: <https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/pull/1>.

The corrected checkpoint passed all 14 applicable GitHub checks. The nightly
integration matrix was correctly skipped because this was a pull-request run:

- [Saddle CI](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29669553801);
- [Saddle Validation](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29669553776);
- [Windows workspace validation](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29669553774);
- [canonical footer check](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29669553795).

All 762 reachable published commits are classified. Historical commit objects
and their messages remain immutable provenance; later reuse requires a new,
focused, human-reviewed Saddle commit. Bulk transplantation, model attribution,
prompt residue, and mechanical narration remain prohibited.

**Next:** SAD-HIST-02 is pending and is not authorized by this closeout.

## SAD-HIST-02 - Archive safety

**Status:** complete

**Branch:** `session/SAD-HIST-2`

**Verified base:** `f66134ef4b3b36c1506f277dbbb9bf61c7d82d7c`

### Scope

- scan every blob and commit message reachable from the 38 frozen Mighty Eel
  heads with Gitleaks 8.30.1 and TruffleHog 3.95.9;
- include blobs deleted from every candidate tip tree;
- identify secret-bearing objects without publishing them; and
- define a reproducible sanitized object graph and exact non-main archive refs.

### Local result

- original closure: 762 commits, 4,885 blobs, 2,173 deleted blobs, and 762
  commit messages;
- confirmed secret-bearing source objects: blob
  `ffb2ea027f2a965cdad277c1ebbde291d3314a36` and commit
  `c75e95f15256b929e382ec58658348502e6a5f83`;
- complete map: 10,444 objects, with one blob, ten trees, and 456 commits
  rewritten; and
- sanitized closure: both scanners report only the 586 reviewed non-secret raw
  findings, represented by 583 unique redacted adjudication records.

### Evidence

- `docs/history/SAD-HIST-02-ARCHIVE-SAFETY.md`
- `test-evidence/saddle/SAD-HIST-02/archive-safety.json`
- `test-evidence/saddle/SAD-HIST-02/object-map.jsonl`
- `test-evidence/saddle/SAD-HIST-02/scanner-findings.json`

### Publication

No historical ref, source object, source file, or active-history rewrite was
published. The focused branch was published through three additive commits;
neither repair rewrote its predecessor:

- implementation and evidence:
  `88bf63a28750b72c5c0db0c9a8439222a0ebc44b`;
- independent-boundary evidence refresh:
  `39d1241ec91ca3a104e9904d221352b511a1b8e1`;
- active-name evidence refresh:
  `509abbed7d47ed1f81bbb9876937ade7422d3873`; and
- draft review: <https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/pull/2>.

### Remote verification

The reviewed implementation checkpoint passed all 14 applicable checks. The
nightly integration matrix was correctly skipped because this was a
pull-request run:

- [Saddle CI](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29676518115);
- [Saddle Validation](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29676518138);
- [Windows workspace validation](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29676518113); and
- [canonical footer check](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29676518126).

SAD-HIST-03 remains pending and is not authorized by this closeout. No merge to
`main` occurred.

## SAD-HIST-03 - Non-main reconciliation

**Status:** complete

**Branch:** `session/SAD-HIST-3`

**Verified base:** `0e3bd77656601b46cc03d96765d703c3916dbcd3`

### Scope

- review all 12 commits classified `review-required` by SAD-HIST-01;
- compare their behavior and tests with approved source main and current Saddle;
- adapt only behavior that is still absent; and
- preserve archive publication as a separate SAD-HIST-04 action.

### Result

- nine commits are superseded by smaller reviewed source-main changes or later
  Saddle work;
- `8f27bbe` is archive-only Mighty Eel RC1.2 release evidence;
- `f30164f` is excluded because its implementation belongs to MAI appliance
  vault crates outside Saddle's selected source closure; and
- `92dc928` exposed real OpenAPI drift and was adapted to current Saddle DTOs in
  focused commit `1caaa4f8d160bece69aaf0416d57d573e73b2a1d`.

No candidate source commit was cherry-picked or merged. No historical object or
`history/mighty-eel/...` ref was created or pushed.

### Evidence

- `docs/history/SAD-HIST-03-NON-MAIN-RECONCILIATION.md`
- `test-evidence/saddle/SAD-HIST-03/non-main-reconciliation.json`
- `tools/reconcile_saddle_history_non_main.py`
- `tools/ci_surface_tests/test_history_reconciliation.py`
- `tools/ci_surface_tests/test_wsf_openapi.py`

### Local verification

- deterministic reconciliation generation and byte-for-byte verification: PASS;
- reconciliation and OpenAPI contract tests: PASS;
- WSF trust primitives (`fabric-contracts`, `fabric-token`,
  `fabric-revocation`, `wsf-broker`, `wsf-seal`): PASS;
- WSF authentication, issuance-permission, and ledger-authorization tests:
  15 passed, 0 failed;
- Saddle server seal tests: 2 passed, 0 failed;
- Saddle bridge property tests: 6 passed, 0 failed;
- console tests: 23 passed, 0 failed; Node 24 production build: PASS; and
- JSON parsing, Python compilation, `git diff --check`, targeted integrity, and
  staged no-slop checks: PASS.

Tests named `live_*` skip when their required backend variables are absent;
this session does not convert those deterministic skips into fresh OpenBao live
proof. The existing AF-005 real-ZFS+TPM deferral also remains unchanged.

### Publication

The focused branch was published through five additive commits. The workflow
repairs did not rewrite their predecessors:

- commit `1caaa4f8d160bece69aaf0416d57d573e73b2a1d` contains the adapted WSF
  OpenAPI transplant;
- reconciliation ledger and deterministic verifier:
  `7c6527e89206a48700b5c41b7d4a55bf94a5af13`;
- zero-phone-home false-positive repair and regression coverage:
  `7ee939765b9a98936de291519142fb9919f724b6`;
- deterministic boundary-evidence refresh:
  `2f5ad2dd2a8e5690c9b8f9ec948c5fd50303fbac`;
- Linux executable-mode correction:
  `56bf5596adc84b2db109dad35830b13a2dc0034d`; and
- draft review: <https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/pull/3>.

The first remote checkpoint exposed a latent static-scanner false positive for
Kubernetes qualified names and private test fixtures. The repair preserved
fail-closed detection for real vendor and unknown public endpoints. A later
tooling run caught the reconciliation generator's Windows-authored executable
mode; the focused mode-only commit restored the Linux entrypoint contract.

### Remote verification

The reviewed checkpoint passed all 15 applicable checks. The nightly
integration matrix and release-only SBOM/signing job were correctly skipped on
this pull-request run:

- [Saddle CI](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29690445079);
- [Saddle Validation](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29690445095);
- [Windows workspace validation](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29690445124);
- [zero-phone-home supply-chain gate](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29690445072); and
- [canonical footer check](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/actions/runs/29690445088).

No merge to `main`, historical object import, or archive-ref publication
occurred. SAD-HIST-04 remains pending and is not authorized by this closeout.

## SAD-HIST-04 - Publish and close history

**Status:** archive publication verified; reviewed-lane integration pending

**Branch:** `session/SAD-HIST-4`

**Reconciled main base:** `f66134ef4b3b36c1506f277dbbb9bf61c7d82d7c`

**Reviewed lane checkpoint:** `8c38d9d47ffe714932c61616c1d236c60159a716`

### Archive publication

- Reproduced the SAD-HIST-02 archive proof byte-for-byte with Gitleaks 8.30.1
  and TruffleHog 3.95.9 before creating a remote archive ref.
- Created active GitHub ruleset `19173522` for
  `refs/heads/history/mighty-eel/**`; deletion, updates, and non-fast-forward
  changes are prohibited and no bypass actor exists.
- Published the 38 approved sanitized tips individually. No mirror push,
  source-history merge, replacement ref, graft, tag, or active `main` update
  occurred.
- Live verification matched all 38 remote tips to the approved ref map and
  proved the 762-commit, 10,444-object sanitized graph.

### Active-tree result

Current `origin/main` was already an ancestor of the reviewed additive lane.
The only active product changes remain the SAD-HIST-03 WSF OpenAPI adaptation
and its bounded no-phone-home scanner repair. `Cargo.toml` and `Cargo.lock` are
byte-identical to the reconciled base. Archive objects are not parents of
active Saddle history.

### Evidence

- `docs/history/SAD-HIST-04-ARCHIVE-PUBLICATION.md`;
- `test-evidence/saddle/SAD-HIST-04/archive-publication.json`;
- `tools/verify_saddle_history_publication.py`; and
- `tools/ci_surface_tests/test_history_publication.py`.

### Remaining gate

The publication implementation must pass the complete applicable local and
GitHub workflow stacks. The reviewed lane must then merge without squashing;
only after that integration may the canonical PSPR and canonical Saddle DEVLOG
record SAD-HIST-04 complete.
