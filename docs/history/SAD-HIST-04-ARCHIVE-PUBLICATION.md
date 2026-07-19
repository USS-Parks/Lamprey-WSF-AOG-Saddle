# SAD-HIST-04 Archive Publication

**Repository:** `USS-Parks/Lamprey-WSF-AOG-Saddle`

**Namespace:** `refs/heads/history/mighty-eel/...`

**Result:** the 38 approved sanitized history refs are published and protected;
active Saddle history remains separate

## Published boundary

SAD-HIST-04 reproduced the SAD-HIST-02 sanitized archive byte-for-byte from
the 38 frozen Mighty Eel heads. Gitleaks 8.30.1 and TruffleHog 3.95.9 rescanned
the exact original and sanitized closures. The complete proof passed before
any archive ref was created.

The refs were then pushed individually from the isolated bare archive. No
mirror push, source-history merge, replacement ref, graft, tag, or active
Saddle branch update was used. The remote namespace contains exactly the 38
approved refs and tips recorded in
`test-evidence/saddle/SAD-HIST-04/archive-publication.json`.

The published graph contains 762 commits and 10,444 reachable objects: 4,885
blobs, 4,797 trees, and 762 commits. Its deterministic object-metadata digest
is `dc5ce6d06965c2e3bcef43826101d9ee669cdbb1f4a29131edd5ff071aae996d`.
The remote ref digest is
`0ee1e6f6ec666f4a5e9e61f81e5584cc881be6942e1bb0ac1ded60ac35133b26`.

## Sanitization and provenance

The original secret-bearing blob
`ffb2ea027f2a965cdad277c1ebbde291d3314a36` and commit
`c75e95f15256b929e382ec58658348502e6a5f83` are absent from the sanitized
archive. One blob, ten trees, and 456 commits changed. The rewrite removed 235
stored signatures that could not remain valid after their signed objects
changed; the original signed SHAs remain cited as external provenance.

The immutable old-to-new ledger contains all 10,444 objects. Every published
ref record binds its source ref, original tip, sanitized tip, and observed
remote tip. The source safety, scanner, object-map, and SAD-HIST-03
reconciliation digests are also bound into the final evidence.

## Protection

GitHub repository ruleset `19173522`, **Immutable Mighty Eel history archive**,
is active for `refs/heads/history/mighty-eel/**`. It prohibits deletion,
updates, and non-fast-forward changes. It has no bypass actors, and the
publication verifier recorded that the current user cannot bypass it.

## Active Saddle invariants

`origin/main` checkpoint `f66134ef4b3b36c1506f277dbbb9bf61c7d82d7c`
was already an ancestor of the reviewed lane before publication. The only
active product changes in the complete history lane are the reviewed
SAD-HIST-03 WSF OpenAPI adaptation and its bounded no-phone-home scanner
repair. `Cargo.toml` and `Cargo.lock` are byte-identical to the reconciled
base, so the active dependency graph did not change. Archive refs are not
parents of Saddle `main` and were not fetched into its active history.

## Evidence and reproduction

- `test-evidence/saddle/SAD-HIST-04/archive-publication.json`, SHA-256
  `520427f410b6e28045b3951e5f5b15572e8c57632001ae5be2e6b860a482f1f9`;
- `tools/verify_saddle_history_publication.py`, SHA-256
  `a21862c3c89f70b5ac93136dc6f6690e97c1e4a36d3948de882de87f9d9e20a2`;
- SAD-HIST-02 object map, SHA-256
  `146a43b93caa86538e1ec70c53dabc2622b774a86a92384d1fb683f2b36499fe`;
- SAD-HIST-02 normalized scanner findings, SHA-256
  `404ac5048b8d538a76480fbf16d934b3edd84473ee4756d1852baba1fa7369d7`;
  and
- SAD-HIST-03 reconciliation ledger, SHA-256
  `539ade15d9d6e993750e9832bcfdb4c548edbfb4952cd5f8556fea2be1583c0e`.

Live deterministic verification uses the isolated sanitized bare repository:

```powershell
python tools\verify_saddle_history_publication.py `
  --root . `
  --archive-repo '<sanitized-archive.git>' `
  --ruleset-id 19173522 `
  --verify
```

CI and clean checkouts can verify the recorded proof without importing archive
objects or requiring repository-administration credentials:

```powershell
python tools\verify_saddle_history_publication.py --root . --verify-recorded
```

Archive publication and reviewed-lane integration are complete. Implementation
head `85b5c0925136ce7ea9865f197e1295db42ed07ca` passed the complete applicable
GitHub workflow stack in pull request
[#4](https://github.com/USS-Parks/Lamprey-WSF-AOG-Saddle/pull/4) and merged
without squashing as `2937f6494561fc607519de6c17c259bc7c684e51`. The protected
archive graph remains separate from active Saddle ancestry.
