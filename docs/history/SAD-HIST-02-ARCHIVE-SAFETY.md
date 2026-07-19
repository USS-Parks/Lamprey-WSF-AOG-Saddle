# SAD-HIST-02 Archive Safety

**Source:** the 38 Mighty Eel heads frozen by SAD-HIST-01

**Candidate graph:** 762 commits and 10,444 reachable Git objects

**Result:** a sanitized rewrite is required; exact source objects are not safe
to archive unchanged

## Scan boundary

Gitleaks 8.30.1 and TruffleHog 3.95.9 independently scanned a materialized
closure of every unique blob and every commit message reachable from the frozen
heads. The input included 4,885 blobs, 762 commit messages, and 2,173 blobs that
are no longer present in any candidate tip tree. TruffleHog verification was
disabled so candidate values were not sent to an external verifier.

The original graph produced 209 Gitleaks findings and 379 TruffleHog findings.
Two Gitleaks findings are secret-bearing:

- blob `ffb2ea027f2a965cdad277c1ebbde291d3314a36` stored a wrapped OpenBao token in
  `deployment/openbao-staging/openbao-connection.toml`; and
- commit `c75e95f15256b929e382ec58658348502e6a5f83` repeated that token in the
  message that removed the file credential.

The other 586 raw findings are reviewed non-secrets. Three duplicate TruffleHog
emissions reduce this to 583 unique redacted adjudication records. They are
scanner hashes, contract and test fixtures, vendor-defined Lob `test_` keys, a
named placeholder GCP bearer, and invalid-credential URL tests. Their
object-bound dispositions are in
`test-evidence/saddle/SAD-HIST-02/scanner-findings.json`; no raw candidate value
is retained there.

## Reproducible rewrite

`tools/prove_saddle_history_archive_safety.py` replaces the wrapped-token line
in the identified blob with a runtime-injection requirement and redacts the
same value from the identified commit message. It then rebuilds dependent
trees and commits without changing author identity, author date, committer
identity, committer date, message text unrelated to the redaction, parent
topology, or file content unrelated to the redaction.

A rewritten commit cannot retain a valid signature over its old contents. The
generator therefore removes stored signature headers from 235 affected signed
commits. The original signed objects remain the immutable external provenance
and retain their original SHAs. The sanitized graph changes one blob, ten
trees, and 456 commits. The complete 10,444-entry map, including identity maps
for unchanged objects, is
`test-evidence/saddle/SAD-HIST-02/object-map.jsonl`.

The second full scan over the rewritten closure produced 207 Gitleaks findings
and 379 raw TruffleHog findings, all in the reviewed non-secret set. Three
duplicate TruffleHog emissions reduce this to 583 unique records. Neither
secret-bearing source object exists in the self-contained sanitized archive
object database after its alternate is removed and the reachable graph is
repacked.

## Defined archive refs

Each frozen source head maps to
`refs/heads/history/mighty-eel/<source-branch-name>`. The exact original tip,
sanitized tip, and archive ref for all 38 heads are recorded in
`test-evidence/saddle/SAD-HIST-02/archive-safety.json`.

These refs are definitions only. SAD-HIST-02 does not authorize pushing them,
and the generator marks archive publication as unauthorized. A later approved
publication must push the exact listed refs individually and must never use a
mirror push. The active Saddle branch and dependency graph are not rewritten
or populated with Mighty Eel source objects by this prompt.

## Reproduction

On Windows, TruffleHog requires a short scratch path for the materialized
object closure:

```powershell
python tools/prove_saddle_history_archive_safety.py `
  --root . `
  --source-repo '<local USS-Parks/Mighty-Eel-OS clone>' `
  --scratch C:\tmp\sad-hist-02-proof `
  --gitleaks '<gitleaks 8.30.1 executable>' `
  --trufflehog '<checksum-verified TruffleHog 3.95.9 executable>' `
  --verify
```

The proof refuses scanner version drift, a changed inventory, an incomplete
object map, an unexpected finding, a surviving secret object, a changed commit
count, or non-reproducible evidence.
